"""Phase 3, vague 1 : le dispatcheur exécute les outils et renvoie toujours
un dict (succès ou erreur), jamais une exception.
Aujourd'hui = vendredi 16 octobre 2026, 15h00 (horloge figée via conftest)."""

import pytest

from agent_rdv.llm.outils import Dispatcheur, construire_schemas


@pytest.fixture
def dispatcheur(service):
    return Dispatcheur(service)


def test_les_schemas_listent_les_outils(regles):
    noms = {s["function"]["name"] for s in construire_schemas(regles)}
    assert noms == {
        "chercher_creneaux", "premiers_creneaux", "reserver",
        "retrouver_rdv", "annuler", "deplacer", "demander_rappel",
    }


def test_chercher_renvoie_des_creneaux(dispatcheur):
    res = dispatcheur.executer("chercher_creneaux", {
        "type_consultation": "standard", "date_debut": "2026-10-22", "periode": "matin"
    })
    assert res["ok"] is True
    assert res["creneaux"][0]["libelle"].startswith("jeudi 22/10")


def test_reserver_puis_retrouver_puis_annuler(dispatcheur):
    res = dispatcheur.executer("reserver", {
        "type_consultation": "standard", "debut": "2026-10-19T09:00:00",
        "prenom": "Sara", "nom": "Ben Ali", "telephone": "0612345678",
    })
    assert res["ok"] is True
    rdv_id = res["rdv_id"]

    trouve = dispatcheur.executer("retrouver_rdv", {"nom": "Ben Ali", "telephone": "0612345678"})
    assert trouve["ok"] is True
    assert trouve["rdv"][0]["rdv_id"] == rdv_id

    annule = dispatcheur.executer("annuler", {
        "rdv_id": rdv_id, "nom": "Ben Ali", "telephone": "0612345678"
    })
    assert annule["ok"] is True


def test_reserver_un_jour_ferme_renvoie_une_erreur_exploitable(dispatcheur):
    res = dispatcheur.executer("reserver", {
        "type_consultation": "standard", "debut": "2026-10-17T10:00:00",  # samedi
        "prenom": "Sara", "nom": "Ben Ali", "telephone": "0612345678",
    })
    assert res["ok"] is False
    assert res["code"] == "cabinet_ferme"


def test_outil_inconnu(dispatcheur):
    res = dispatcheur.executer("faire_le_cafe", {})
    assert res["ok"] is False
    assert res["code"] == "outil_inconnu"


def test_parametres_invalides_ne_plantent_pas(dispatcheur):
    res = dispatcheur.executer("chercher_creneaux", {"type_consultation": "standard", "date_debut": "pas-une-date"})
    assert res["ok"] is False
    assert res["code"] == "donnees_invalides"