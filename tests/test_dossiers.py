"""Vague 4a : le stockage des dossiers patients (comptes-rendus, ordonnances)."""

import pytest

from agent_rdv.agenda.erreurs import DonneesInvalides
from agent_rdv.dossiers import BROUILLON, VALIDE, DossiersPatients


@pytest.fixture
def dossiers():
    return DossiersPatients()


def test_un_document_naît_en_brouillon(dossiers):
    doc_id = dossiers.ajouter(patient_id=1, observations="Toux depuis 3 jours")
    doc = dossiers.obtenir(doc_id)
    assert doc["statut"] == BROUILLON
    assert doc["observations"] == "Toux depuis 3 jours"


def test_lister_par_patient_du_plus_recent(dossiers):
    dossiers.ajouter(patient_id=1, observations="premier")
    dernier = dossiers.ajouter(patient_id=1, observations="second")
    dossiers.ajouter(patient_id=2, observations="autre patient")
    liste = dossiers.lister(patient_id=1)
    assert [d["id"] for d in liste] == [dernier, liste[-1]["id"]]
    assert len(liste) == 2  # le patient 2 n'apparaît pas


def test_mettre_a_jour_un_brouillon(dossiers):
    doc_id = dossiers.ajouter(patient_id=1)
    dossiers.mettre_a_jour(doc_id, synthese="Rhinopharyngite probable", ordonnance="Repos, hydratation")
    doc = dossiers.obtenir(doc_id)
    assert doc["synthese"] == "Rhinopharyngite probable"
    assert doc["ordonnance"] == "Repos, hydratation"


def test_valider_fige_le_document(dossiers):
    doc_id = dossiers.ajouter(patient_id=1, synthese="brouillon IA")
    dossiers.valider(doc_id)
    assert dossiers.obtenir(doc_id)["statut"] == VALIDE
    with pytest.raises(DonneesInvalides):  # on ne modifie plus un document validé
        dossiers.mettre_a_jour(doc_id, synthese="modif interdite")


def test_type_inconnu_refuse(dossiers):
    with pytest.raises(DonneesInvalides):
        dossiers.ajouter(patient_id=1, type="n_importe_quoi")


def test_supprimer(dossiers):
    doc_id = dossiers.ajouter(patient_id=1)
    dossiers.supprimer(doc_id)
    assert dossiers.obtenir(doc_id) is None
