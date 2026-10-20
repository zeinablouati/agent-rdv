"""Service de rendez-vous : les opérations que l'agent appellera comme outils
(Phase 3). Toutes les règles du cabinet passent par ici."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Callable

from ..config import Regles
from .base import Agenda
from .creneaux import creneaux_libres, duree_consultation, motif_refus
from .erreurs import AnnulationTardive, CreneauRefuse, DonneesInvalides, RdvIntrouvable
from .modeles import Creneau, Rdv
from .registre import RegistrePatients


class ServiceRendezVous:
    def __init__(
        self,
        regles: Regles,
        agenda: Agenda,
        registre: RegistrePatients,
        horloge: Callable[[], datetime] | None = None,
        notificateur=None,
        journal=None,
    ):
        self.regles = regles
        self.agenda = agenda
        self.registre = registre
        self.notificateur = notificateur
        self.journal = journal
        self._horloge = horloge or (lambda: datetime.now(regles.fuseau))

    # --- utilitaires ---

    def maintenant(self) -> datetime:
        return self._horloge().astimezone(self.regles.fuseau)

    def _localiser(self, dt: datetime) -> datetime:
        """Une date sans fuseau est lue comme une heure locale du cabinet."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.regles.fuseau)
        return dt.astimezone(self.regles.fuseau)

    def _debut_jour(self, jour: date) -> datetime:
        return datetime.combine(jour, time.min, tzinfo=self.regles.fuseau)

    def _occupes_le(self, jour: date, sauf_id: int | None = None) -> list[Rdv]:
        rdvs = self.agenda.rdv_entre(self._debut_jour(jour), self._debut_jour(jour + timedelta(days=1)))
        return [r for r in rdvs if r.id != sauf_id]

    def _retrouver(self, rdv_id: int, nom: str, telephone: str) -> Rdv:
        """Retrouve un rendez-vous à venir ET vérifie qu'il appartient à cette personne.
        Même erreur dans les deux cas : on ne révèle rien sur les rendez-vous d'autrui."""
        patients = self.registre.trouver(nom, telephone)
        rdvs = self.agenda.rdv_des_patients([p.id for p in patients], self.maintenant())
        for rdv in rdvs:
            if str(rdv.id) == str(rdv_id):
                return rdv
        raise RdvIntrouvable("Je ne trouve aucun rendez-vous à venir correspondant à ces informations.")

    def _exiger_delai_annulation(self, rdv: Rdv) -> None:
        heures = self.regles.reservation.annulation_autonome_heures
        if rdv.debut - self.maintenant() < timedelta(hours=heures):
            raise AnnulationTardive(
                f"Le rendez-vous a lieu dans moins de {heures} h : "
                "merci de contacter directement le secrétariat du cabinet."
            )

    # --- opérations ---

    def chercher_creneaux(
        self,
        type_consultation: str,
        du: date,
        au: date | None = None,
        periode: str | None = None,
    ) -> list[Creneau]:
        au = au or du
        if au < du:
            raise DonneesInvalides("La date de fin est avant la date de début.")
        duree_consultation(self.regles, type_consultation)  # valide le type
        occupes = self.agenda.rdv_entre(self._debut_jour(du), self._debut_jour(au + timedelta(days=1)))
        return creneaux_libres(
            self.regles, type_consultation, du, au, self.maintenant(), occupes, periode
        )

    def premiers_creneaux(self, type_consultation: str, n: int = 3) -> list[Creneau]:
        """Les n créneaux libres les plus proches, à partir de maintenant."""
        aujourdhui = self.maintenant().date()
        horizon = aujourdhui + timedelta(days=self.regles.reservation.horizon_jours)
        creneaux = self.chercher_creneaux(type_consultation, aujourdhui, horizon)
        return creneaux[:n]

    def reserver(
        self,
        type_consultation: str,
        debut: datetime,
        prenom: str,
        nom: str,
        telephone: str,
        email: str | None = None,
    ) -> Rdv:
        debut = self._localiser(debut)
        duree = duree_consultation(self.regles, type_consultation)
        refus = motif_refus(
            self.regles, type_consultation, debut, self.maintenant(), self._occupes_le(debut.date())
        )
        if refus:
            raise CreneauRefuse(refus[1], code=refus[0])
        patient = self.registre.obtenir_ou_creer(prenom, nom, telephone, email)
        rdv = self.agenda.ajouter(debut, debut + duree, type_consultation, patient.id, patient=patient)
        self._notifier_confirmation(patient, rdv, type_consultation)
        return rdv

    def _notifier_confirmation(self, patient, rdv: Rdv, type_consultation: str) -> None:
        """Envoie l'e-mail de confirmation. Un échec d'envoi n'annule jamais la réservation."""
        if not (patient.email and self.notificateur):
            return
        from ..notifications.messages import confirmation

        try:
            sujet, corps = confirmation(self.regles.cabinet.nom, patient.prenom, rdv.debut, type_consultation)
            self.notificateur.envoyer(patient.email, sujet, corps)
        except Exception:
            pass

    def enregistrer_demande_rappel(self, nom: str, telephone: str, motif: str = "") -> int | None:
        """Consigne une demande de rappel. None si aucun journal n'est configuré."""
        if self.journal is None:
            return None
        return self.journal.ajouter(nom, telephone, motif)

    def envoyer_rappels(self, jour: date | None = None) -> int:
        """Envoie un rappel par e-mail pour chaque rendez-vous du jour donné
        (demain par défaut). Renvoie le nombre de rappels envoyés."""
        from ..notifications.messages import rappel

        if jour is None:
            jour = (self.maintenant() + timedelta(days=1)).date()
        rdvs = self.agenda.rdv_entre(self._debut_jour(jour), self._debut_jour(jour + timedelta(days=1)))

        envoyes = 0
        for rdv in rdvs:
            patient = self.registre.obtenir_par_id(rdv.patient_id)
            if not (patient and patient.email and self.notificateur):
                continue
            try:
                sujet, corps = rappel(self.regles.cabinet.nom, patient.prenom, rdv.debut, rdv.type_consultation)
                self.notificateur.envoyer(patient.email, sujet, corps)
                envoyes += 1
            except Exception:
                pass
        return envoyes

    def retrouver_rdv(self, nom: str, telephone: str) -> list[Rdv]:
        patients = self.registre.trouver(nom, telephone)
        return self.agenda.rdv_des_patients([p.id for p in patients], self.maintenant())

    def rdv_du_jour(self, jour: date | None = None) -> list[dict]:
        """Lecture réservée au médecin : les rendez-vous d'un jour, triés par heure,
        avec le patient résolu (nom + téléphone)."""
        jour = jour or self.maintenant().date()
        rdvs = sorted(self._occupes_le(jour), key=lambda r: r.debut)
        return [
            {
                "debut": self._localiser(r.debut),
                "fin": self._localiser(r.fin),
                "type": r.type_consultation,
                "patient": self.registre.obtenir_par_id(r.patient_id),
            }
            for r in rdvs
        ]

    def annuler(self, rdv_id: int, nom: str, telephone: str) -> Rdv:
        rdv = self._retrouver(rdv_id, nom, telephone)
        self._exiger_delai_annulation(rdv)
        self.agenda.supprimer(rdv.id)
        return rdv

    def deplacer(self, rdv_id: int, nouveau_debut: datetime, nom: str, telephone: str) -> Rdv:
        rdv = self._retrouver(rdv_id, nom, telephone)
        self._exiger_delai_annulation(rdv)
        nouveau_debut = self._localiser(nouveau_debut)
        refus = motif_refus(
            self.regles,
            rdv.type_consultation,
            nouveau_debut,
            self.maintenant(),
            self._occupes_le(nouveau_debut.date(), sauf_id=rdv.id),
        )
        if refus:
            raise CreneauRefuse(refus[1], code=refus[0])
        duree = duree_consultation(self.regles, rdv.type_consultation)
        return self.agenda.deplacer(rdv.id, nouveau_debut, nouveau_debut + duree)
