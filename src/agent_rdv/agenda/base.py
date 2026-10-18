"""Interface d'un agenda. La Phase 1 utilise AgendaLocal (SQLite) ;
la Phase 2 ajoutera AgendaGoogle avec exactement la même interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from .modeles import Rdv


class Agenda(ABC):
    @abstractmethod
    def rdv_entre(self, debut: datetime, fin: datetime) -> list[Rdv]:
        """Rendez-vous qui chevauchent l'intervalle [debut, fin)."""

    @abstractmethod
    def ajouter(self, debut: datetime, fin: datetime, type_consultation: str, patient_id: int, patient=None) -> Rdv:
        """Crée un rendez-vous. `patient` (optionnel) sert à nommer l'événement.
        Lève ConflitCreneau en cas de chevauchement."""

    @abstractmethod
    def deplacer(self, rdv_id: int, debut: datetime, fin: datetime) -> Rdv:
        """Déplace un rendez-vous existant. Lève ConflitCreneau en cas de chevauchement."""

    @abstractmethod
    def supprimer(self, rdv_id: int) -> None:
        ...

    @abstractmethod
    def obtenir(self, rdv_id: int) -> Rdv | None:
        ...

    @abstractmethod
    def rdv_des_patients(self, patient_ids: Sequence[int], a_partir_de: datetime) -> list[Rdv]:
        """Rendez-vous à venir de ces patients, triés par date."""