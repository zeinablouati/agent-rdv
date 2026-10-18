"""Outils de test partagés : une horloge figée et un service neuf pour chaque test."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.config import charger_regles

PARIS = ZoneInfo("Europe/Paris")


def paris(annee, mois, jour, heure=0, minute=0) -> datetime:
    return datetime(annee, mois, jour, heure, minute, tzinfo=PARIS)


class Horloge:
    """Horloge réglable : par défaut, vendredi 16 octobre 2026, 15h00."""

    def __init__(self):
        self.maintenant = paris(2026, 10, 16, 15, 0)

    def __call__(self):
        return self.maintenant


@pytest.fixture
def regles():
    return charger_regles()


@pytest.fixture
def horloge():
    return Horloge()


@pytest.fixture
def agenda(regles):
    return AgendaLocal(fuseau=regles.fuseau)


@pytest.fixture
def service(regles, agenda, horloge):
    return ServiceRendezVous(regles, agenda, RegistrePatients(), horloge)