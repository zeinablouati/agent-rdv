"""Agenda Google Calendar. Même interface que AgendaLocal : interchangeable.

Minimisation des données : le titre de l'événement ne contient qu'un numéro de
patient ; le type de consultation et le numéro de patient sont rangés dans des
propriétés privées de l'événement, pas dans le titre."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Sequence

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import Agenda
from .erreurs import ConflitCreneau, RdvIntrouvable
from .formats import description_evenement, resume_evenement
from .modeles import Rdv

SCOPES = ["https://www.googleapis.com/auth/calendar"]
MARQUEUR = "agent_rdv"  # pour reconnaître nos événements parmi d'autres
HORIZON_RECHERCHE_JOURS = 370


class AgendaGoogle(Agenda):
    def __init__(self, calendar_id: str, fichier_cle: str, fuseau: tzinfo = timezone.utc):
        creds = service_account.Credentials.from_service_account_file(fichier_cle, scopes=SCOPES)
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._calendar_id = calendar_id
        self._fuseau = fuseau

    # --- conversions ---

    def _lire_dt(self, bloc: dict) -> datetime:
        texte = bloc["dateTime"].replace("Z", "+00:00")
        return datetime.fromisoformat(texte).astimezone(self._fuseau)

    def _vers_rdv(self, event: dict) -> Rdv:
        props = event.get("extendedProperties", {}).get("private", {})
        return Rdv(
            id=event["id"],
            debut=self._lire_dt(event["start"]),
            fin=self._lire_dt(event["end"]),
            type_consultation=props.get("type_consultation", "standard"),
            patient_id=int(props.get("patient_id", 0)),
        )

    def _corps(self, debut: datetime, fin: datetime, type_consultation: str, patient_id: int, patient=None) -> dict:
        zone = str(self._fuseau)
        if patient is not None:
            summary = resume_evenement(patient.prenom, patient.nom, type_consultation)
            description = description_evenement(patient.telephone, type_consultation)
        else:
            summary = f"Consultation – Patient {patient_id:04d}"
            description = f"Type : {type_consultation}"
        return {
            "summary": summary,
            "description": description,
            "start": {"dateTime": debut.isoformat(), "timeZone": zone},
            "end": {"dateTime": fin.isoformat(), "timeZone": zone},
            "extendedProperties": {
                "private": {
                    MARQUEUR: "1",
                    "type_consultation": type_consultation,
                    "patient_id": str(patient_id),
                }
            },
        }

    @staticmethod
    def _statut(err: HttpError) -> int:
        statut = getattr(err, "status_code", None)
        if statut is None:
            statut = getattr(err.resp, "status", 0)
        return int(statut)

    def _lister(self, debut: datetime, fin: datetime) -> list[dict]:
        """Événements (hors journée entière) entre deux instants, pagination comprise."""
        items: list[dict] = []
        page = None
        while True:
            reponse = self._service.events().list(
                calendarId=self._calendar_id,
                timeMin=debut.astimezone(timezone.utc).isoformat(),
                timeMax=fin.astimezone(timezone.utc).isoformat(),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page,
            ).execute()
            items.extend(e for e in reponse.get("items", []) if e.get("start", {}).get("dateTime"))
            page = reponse.get("nextPageToken")
            if not page:
                return items

    # --- interface Agenda ---

    def rdv_entre(self, debut: datetime, fin: datetime) -> list[Rdv]:
        return [self._vers_rdv(e) for e in self._lister(debut, fin)]

    def ajouter(self, debut: datetime, fin: datetime, type_consultation: str, patient_id: int, patient=None) -> Rdv:
        if self.rdv_entre(debut, fin):
            raise ConflitCreneau("Ce créneau est déjà pris.")
        cree = self._service.events().insert(
            calendarId=self._calendar_id,
            body=self._corps(debut, fin, type_consultation, patient_id, patient),
        ).execute()
        return self._vers_rdv(cree)

    def deplacer(self, rdv_id: str, debut: datetime, fin: datetime) -> Rdv:
        if self.obtenir(rdv_id) is None:
            raise RdvIntrouvable("Rendez-vous introuvable.")
        if any(str(r.id) != str(rdv_id) for r in self.rdv_entre(debut, fin)):
            raise ConflitCreneau("Ce créneau est déjà pris.")
        zone = str(self._fuseau)
        maj = self._service.events().patch(
            calendarId=self._calendar_id,
            eventId=rdv_id,
            body={
                "start": {"dateTime": debut.isoformat(), "timeZone": zone},
                "end": {"dateTime": fin.isoformat(), "timeZone": zone},
            },
        ).execute()
        return self._vers_rdv(maj)

    def supprimer(self, rdv_id: str) -> None:
        try:
            self._service.events().delete(calendarId=self._calendar_id, eventId=rdv_id).execute()
        except HttpError as err:
            if self._statut(err) in (404, 410):
                raise RdvIntrouvable("Rendez-vous introuvable.") from None
            raise

    def obtenir(self, rdv_id: str) -> Rdv | None:
        try:
            event = self._service.events().get(calendarId=self._calendar_id, eventId=rdv_id).execute()
        except HttpError as err:
            if self._statut(err) in (404, 410):
                return None
            raise
        if event.get("status") == "cancelled" or not event.get("start", {}).get("dateTime"):
            return None
        return self._vers_rdv(event)

    def rdv_des_patients(self, patient_ids: Sequence[int], a_partir_de: datetime) -> list[Rdv]:
        if not patient_ids:
            return []
        cibles = {str(p) for p in patient_ids}
        fin = a_partir_de + timedelta(days=HORIZON_RECHERCHE_JOURS)
        rdvs = []
        for event in self._lister(a_partir_de, fin):
            props = event.get("extendedProperties", {}).get("private", {})
            if props.get("patient_id") in cibles:
                rdvs.append(self._vers_rdv(event))
        return rdvs