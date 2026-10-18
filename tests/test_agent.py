"""Phase 3, vague 2 : la boucle de l'agent, testée avec un FAUX client LLM
(aucun appel réseau). On vérifie l'urgence, la réponse directe, et l'enchaînement
LLM -> outil -> réponse.
Aujourd'hui = vendredi 16 octobre 2026, 15h00 (horloge figée via conftest)."""

import json
from types import SimpleNamespace

import pytest

from agent_rdv.llm.agent import AgentRDV
from agent_rdv.llm.securite import MESSAGE_URGENCE


def msg_texte(texte):
    return SimpleNamespace(content=texte, tool_calls=None)


def msg_outil(nom, arguments: dict, appel_id="call_1"):
    fonction = SimpleNamespace(name=nom, arguments=json.dumps(arguments))
    return SimpleNamespace(content=None, tool_calls=[SimpleNamespace(id=appel_id, function=fonction)])


class FauxClient:
    """Rejoue une liste de réponses préparées, comme le ferait Groq."""

    def __init__(self, reponses):
        self._reponses = list(reponses)
        self.appels = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.appels.append(kwargs)
        message = self._reponses.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def construire_agent(service, regles, reponses):
    return AgentRDV(service, regles, FauxClient(reponses), modele="faux")


def test_urgence_court_circuite_le_llm(service, regles):
    agent = construire_agent(service, regles, [])  # aucune réponse : le LLM ne doit pas être appelé
    reponse = agent.repondre(agent.nouvelle_conversation(), "J'ai très mal à la poitrine")
    assert reponse == MESSAGE_URGENCE
    assert agent.client.appels == []  # le LLM n'a pas été sollicité


def test_reponse_directe_sans_outil(service, regles):
    agent = construire_agent(service, regles, [msg_texte("Bonjour, comment puis-je vous aider ?")])
    reponse = agent.repondre(agent.nouvelle_conversation(), "Bonjour")
    assert reponse == "Bonjour, comment puis-je vous aider ?"


def test_enchainement_llm_outil_reponse(service, regles):
    reponses = [
        msg_outil("chercher_creneaux", {"type_consultation": "standard", "date_debut": "2026-10-22", "periode": "matin"}),
        msg_texte("Je peux vous proposer jeudi 22/10 à 09:00. Cela vous convient-il ?"),
    ]
    agent = construire_agent(service, regles, reponses)
    historique = agent.nouvelle_conversation()
    reponse = agent.repondre(historique, "Je voudrais un rendez-vous jeudi matin")
    assert "jeudi 22/10" in reponse
    messages_outil = [m for m in historique if m.get("role") == "tool"]
    assert messages_outil and json.loads(messages_outil[0]["content"])["ok"] is True


def test_repli_si_trop_de_tours(service, regles):
    boucle = [msg_outil("chercher_creneaux", {"type_consultation": "standard", "date_debut": "2026-10-22"}) for _ in range(10)]
    agent = construire_agent(service, regles, boucle)
    reponse = agent.repondre(agent.nouvelle_conversation(), "bonjour")
    assert "secrétariat" in reponse