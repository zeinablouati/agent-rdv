"""Test de fumée de la Phase 0 : l'environnement et les règles se chargent."""

import pytest

from agent_rdv.config import charger_regles


@pytest.fixture(scope="module")
def regles():
    return charger_regles()


def test_le_fichier_de_regles_se_charge(regles):
    assert regles.cabinet.nom == "Cabinet Dr Test"


def test_samedi_et_dimanche_sont_fermes(regles):
    assert not regles.est_ouvert(5)
    assert not regles.est_ouvert(6)


def test_du_lundi_au_vendredi_ouvert(regles):
    assert all(regles.est_ouvert(jour) for jour in range(5))


def test_durees_de_consultation(regles):
    assert regles.types_consultation == {"standard": 20, "nouveau_patient": 30, "suivi": 15}


def test_regles_de_reservation(regles):
    assert regles.reservation.creneaux_urgence_par_jour == 2
    assert regles.reservation.annulation_autonome_heures == 24
    assert regles.reservation.teleconsultation is False
