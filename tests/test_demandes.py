"""Finitions, vague 2 : enregistrer une demande de rappel."""

import pytest

from agent_rdv.agenda.erreurs import DonneesInvalides
from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.demandes import JournalDemandes
from agent_rdv.llm.outils import Dispatcheur

from conftest import Horloge


def test_le_journal_enregistre_et_liste():
    journal = JournalDemandes()
    journal.ajouter("Sara Ben Ali", "06 12 34 56 78", "Rendez-vous annulé 3 fois")
    demandes = journal.lister()
    assert len(demandes) == 1
    assert demandes[0]["nom"] == "Sara Ben Ali"
    assert demandes[0]["telephone"] == "0612345678"
    assert demandes[0]["traitee"] is False


def test_demande_sans_nom_refusee():
    journal = JournalDemandes()
    with pytest.raises(DonneesInvalides):
        journal.ajouter("", "0612345678", "motif")


def test_marquer_traitee():
    journal = JournalDemandes()
    identifiant = journal.ajouter("Sara", "0612345678", "")
    journal.marquer_traitee(identifiant)
    assert journal.lister() == []
    assert len(journal.lister(inclure_traitees=True)) == 1


@pytest.fixture
def service_journal(regles):
    return ServiceRendezVous(
        regles, AgendaLocal(fuseau=regles.fuseau), RegistrePatients(), Horloge(), journal=JournalDemandes()
    )


def test_dispatcheur_demander_rappel(service_journal):
    res = Dispatcheur(service_journal).executer(
        "demander_rappel", {"nom": "Sara Ben Ali", "telephone": "0612345678", "motif": "mécontente"}
    )
    assert res["ok"] is True
    assert service_journal.journal.lister()[0]["nom"] == "Sara Ben Ali"


def test_demander_rappel_sans_journal_indisponible(service):
    res = Dispatcheur(service).executer("demander_rappel", {"nom": "Sara", "telephone": "0612345678"})
    assert res["ok"] is False
    assert res["code"] == "indisponible"