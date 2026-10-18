"""Objets métier. Minimisation des données : un rendez-vous ne contient ni nom,
ni téléphone, ni motif. Il référence seulement un numéro de patient."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Patient:
    id: int
    prenom: str
    nom: str
    telephone: str  # normalisé : 10 chiffres
    email: str | None = None

    @property
    def reference(self) -> str:
        return f"{self.id:04d}"

@dataclass(frozen=True)
class Creneau:
    debut: datetime
    fin: datetime


@dataclass(frozen=True)
class Rdv:
    id: str | int  # identifiant opaque : entier en local, texte chez Google
    debut: datetime
    fin: datetime
    type_consultation: str
    patient_id: int

    @property
    def titre(self) -> str:
        """Titre de l'événement dans l'agenda : aucune donnée identifiante."""
        return f"Consultation – Patient {self.patient_id:04d}"