"""Chargement et validation des règles du cabinet."""

from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, field_validator, model_validator

RACINE = Path(__file__).resolve().parents[2]
CHEMIN_REGLES = RACINE / "config" / "cabinet.yaml"


class Cabinet(BaseModel):
    nom: str
    fuseau_horaire: str


class Reservation(BaseModel):
    creneaux_urgence_par_jour: int
    delai_minimum_heures: int
    horizon_jours: int
    annulation_autonome_heures: int
    pas_creneaux_minutes: int = 10
    teleconsultation: bool = False


class Regles(BaseModel):
    cabinet: Cabinet
    horaires: dict[int, list[tuple[time, time]]]
    types_consultation: dict[str, int]
    reservation: Reservation

    @field_validator("horaires", mode="before")
    @classmethod
    def _lire_horaires(cls, brut):
        return {
            int(jour): [(_heure(debut), _heure(fin)) for debut, fin in plages]
            for jour, plages in brut.items()
        }

    @model_validator(mode="after")
    def _verifier(self):
        pas = self.reservation.pas_creneaux_minutes
        if pas <= 0:
            raise ValueError("pas_creneaux_minutes doit être positif")
        for jour, plages in self.horaires.items():
            if jour not in range(7):
                raise ValueError(f"Jour invalide : {jour} (attendu 0 à 6)")
            for debut, fin in plages:
                if debut >= fin:
                    raise ValueError(f"Plage incohérente le jour {jour} : {debut} >= {fin}")
                if debut.minute % pas or fin.minute % pas:
                    raise ValueError(
                        f"Les horaires du jour {jour} doivent tomber sur un multiple de {pas} min"
                    )
        if any(duree <= 0 for duree in self.types_consultation.values()):
            raise ValueError("Les durées de consultation doivent être positives")
        if "standard" not in self.types_consultation:
            raise ValueError("Le type de consultation 'standard' est obligatoire")
        return self

    @property
    def fuseau(self) -> ZoneInfo:
        return ZoneInfo(self.cabinet.fuseau_horaire)

    def est_ouvert(self, jour_semaine: int) -> bool:
        return bool(self.horaires.get(jour_semaine))


def _heure(texte) -> time:
    if isinstance(texte, time):
        return texte
    heures, minutes = str(texte).split(":")
    return time(int(heures), int(minutes))


def charger_regles(chemin: Path = CHEMIN_REGLES) -> Regles:
    with open(chemin, encoding="utf-8") as fichier:
        return Regles.model_validate(yaml.safe_load(fichier))