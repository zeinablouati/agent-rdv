"""Phase Admin, vague 2 : connexion médecin et protection du tableau de bord.
On injecte un faux agent et des comptes en mémoire : aucun réseau."""

import pytest
from fastapi.testclient import TestClient

from agent_rdv.admin.comptes import Comptes
from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.demandes import JournalDemandes
from agent_rdv.llm.agent import AgentRDV
from agent_rdv.web.app import creer_app

from conftest import paris
from test_agent import FauxClient, msg_texte


def _connecter(client):
    client.post("/medecin/login", data={"utilisateur": "drtest", "mot_de_passe": "motdepasse"})


@pytest.fixture
def comptes():
    c = Comptes()
    c.creer("drtest", "motdepasse")
    return c


@pytest.fixture
def client(service, regles, comptes):
    agent = AgentRDV(service, regles, FauxClient([msg_texte("ok")]), "faux")
    return TestClient(creer_app(agent=agent, comptes=comptes))


def test_le_dashboard_est_protege(client):
    reponse = client.get("/medecin", follow_redirects=False)
    assert reponse.status_code == 303
    assert "/medecin/login" in reponse.headers["location"]


def test_la_page_de_connexion_s_affiche(client):
    reponse = client.get("/medecin/login")
    assert reponse.status_code == 200
    assert "Espace médecin" in reponse.text


def test_connexion_reussie_donne_acces(client):
    reponse = client.post(
        "/medecin/login", data={"utilisateur": "drtest", "mot_de_passe": "motdepasse"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303 and reponse.headers["location"] == "/medecin"
    # le cookie de session est conservé par le client : accès au dashboard
    assert client.get("/medecin").status_code == 200


def test_mauvais_mot_de_passe_refuse(client):
    reponse = client.post(
        "/medecin/login", data={"utilisateur": "drtest", "mot_de_passe": "faux"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303 and "erreur" in reponse.headers["location"]
    assert client.get("/medecin", follow_redirects=False).status_code == 303  # toujours pas connecté


def test_deconnexion(client):
    client.post("/medecin/login", data={"utilisateur": "drtest", "mot_de_passe": "motdepasse"})
    client.get("/medecin/logout")
    assert client.get("/medecin", follow_redirects=False).status_code == 303


def test_le_chat_patient_reste_public(client):
    assert client.get("/").status_code == 200  # pas de login pour le patient


# ---- Dashboard rempli : RDV du jour + demandes de rappel ----

@pytest.fixture
def client_garni(regles, horloge, comptes):
    """Un service avec un RDV du jour et une demande de rappel, exposé via un faux agent."""
    service = ServiceRendezVous(
        regles, AgendaLocal(fuseau=regles.fuseau), RegistrePatients(), horloge,
        journal=JournalDemandes(),
    )
    service.reserver("standard", paris(2026, 10, 16, 17, 30), "Marie", "Durand", "0612345678")
    service.enregistrer_demande_rappel("Paul Martin", "0699887766", "rappel ordonnance")
    agent = AgentRDV(service, regles, FauxClient([msg_texte("ok")]), "faux")
    c = TestClient(creer_app(agent=agent, comptes=comptes))
    _connecter(c)
    return c, service


def test_le_dashboard_affiche_le_rdv_du_jour(client_garni):
    c, _ = client_garni
    page = c.get("/medecin").text
    assert "Marie Durand" in page and "17:30" in page


def test_le_dashboard_affiche_les_demandes(client_garni):
    c, _ = client_garni
    page = c.get("/medecin").text
    assert "Paul Martin" in page and "rappel ordonnance" in page


def test_marquer_une_demande_traitee(client_garni):
    c, service = client_garni
    demande_id = service.journal.lister()[0]["id"]
    c.post(f"/medecin/demandes/{demande_id}/traiter", follow_redirects=False)
    assert service.journal.lister() == []  # plus aucune demande en attente
    assert "Aucune demande de rappel" in c.get("/medecin").text
