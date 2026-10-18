"""Phase 5 : l'API web relaie bien les messages à l'agent et tient une session.
On injecte un agent construit avec un FAUX client LLM : aucun appel réseau."""

import pytest
from fastapi.testclient import TestClient

from agent_rdv.llm.agent import AgentRDV
from agent_rdv.web.app import creer_app

from test_agent import FauxClient, msg_outil, msg_texte


@pytest.fixture
def client(service, regles):
    reponses = [
        msg_outil("chercher_creneaux", {"type_consultation": "standard", "date_debut": "2026-10-22", "periode": "matin"}),
        msg_texte("Je peux vous proposer jeudi 22/10 à 09:00."),
    ]
    agent = AgentRDV(service, regles, FauxClient(reponses), modele="faux")
    return TestClient(creer_app(agent=agent))


def test_la_page_de_chat_se_charge(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "Cabinet Dr Test" in reponse.text


def test_echange_via_l_api(client):
    reponse = client.post("/api/chat", json={"message": "un rdv jeudi matin ?"})
    assert reponse.status_code == 200
    data = reponse.json()
    assert "jeudi 22/10" in data["reply"]
    assert data["session_id"]


def test_la_session_est_reutilisee(client):
    premier = client.post("/api/chat", json={"message": "bonjour"}).json()
    second = client.post("/api/chat", json={"message": "merci", "session_id": premier["session_id"]}).json()
    assert second["session_id"] == premier["session_id"]