"""Phase 6 : les 8 conversations types du cadrage, rejouées à travers le vrai
agent (boucle + outils + RAG + journal) avec un FAUX LLM qui joue les décisions.
Déterministe et hors ligne. Aujourd'hui = vendredi 16 octobre 2026, 15h00."""

import json
from uuid import uuid4

import pytest

from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.demandes import JournalDemandes
from agent_rdv.knowledge.base import BaseConnaissances
from agent_rdv.llm.agent import AgentRDV
from agent_rdv.llm.securite import MESSAGE_URGENCE

from conftest import Horloge, paris
from test_agent import FauxClient, msg_outil, msg_texte
from test_connaissances import PASSAGES, faux_embed
from test_notifications import FauxNotificateur

SARA = ("Sara", "Ben Ali", "0612345678")


def construire(reponses):
    """Un agent complètement câblé, avec un LLM scénarisé."""
    from agent_rdv.config import charger_regles

    regles = charger_regles()
    agenda = AgendaLocal(fuseau=regles.fuseau)
    registre = RegistrePatients()
    journal = JournalDemandes()
    notif = FauxNotificateur()
    base = BaseConnaissances(faux_embed, nom_collection=f"scenario_{uuid4().hex}")
    base.indexer(PASSAGES)
    service = ServiceRendezVous(regles, agenda, registre, Horloge(), notificateur=notif, journal=journal)
    agent = AgentRDV(service, regles, FauxClient(reponses), "faux", connaissances=base)
    return agent, service, journal, notif


def messages_outil(historique):
    return [json.loads(m["content"]) for m in historique if m.get("role") == "tool"]


# 1. Prise de rendez-vous simple
def test_scenario_1_prise_de_rdv(regles):
    agent, service, _, notif = construire([
        msg_outil("premiers_creneaux", {"type_consultation": "nouveau_patient"}),
        msg_texte("Je peux vous proposer lundi 19/10 à 09:00."),
        msg_outil("reserver", {
            "type_consultation": "nouveau_patient", "debut": "2026-10-19T09:00:00",
            "prenom": "Sara", "nom": "Ben Ali", "telephone": "0612345678", "email": "sara@example.com",
        }),
        msg_texte("Votre rendez-vous est confirmé lundi 19/10 à 09:00."),
    ])
    h = agent.nouvelle_conversation()
    agent.repondre(h, "Je suis nouvelle patiente, un rendez-vous au plus tôt ?")
    agent.repondre(h, "Lundi 9h, Sara Ben Ali, 0612345678, sara@example.com")

    rdvs = service.retrouver_rdv("Ben Ali", "0612345678")
    assert len(rdvs) == 1 and rdvs[0].debut == paris(2026, 10, 19, 9, 0)
    assert len(notif.envoyes) == 1  # confirmation envoyée


# 2. Aucun créneau disponible (samedi)
def test_scenario_2_aucun_creneau(regles):
    agent, _, _, _ = construire([
        msg_outil("chercher_creneaux", {"type_consultation": "standard", "date_debut": "2026-10-17"}),
        msg_texte("Le cabinet est fermé samedi ; je peux vous proposer lundi."),
    ])
    h = agent.nouvelle_conversation()
    agent.repondre(h, "Un rendez-vous samedi ?")
    resultat = messages_outil(h)[0]
    assert resultat["ok"] is True and resultat["nombre_total"] == 0


# 3. Annulation
def test_scenario_3_annulation(regles):
    agent, service, _, _ = construire([
        msg_outil("retrouver_rdv", {"nom": "Ben Ali", "telephone": "0612345678"}),
        msg_texte("J'ai trouvé votre rendez-vous. Confirmez-vous l'annulation ?"),
        msg_outil("annuler", {"rdv_id": "1", "nom": "Ben Ali", "telephone": "0612345678"}),
        msg_texte("C'est annulé."),
    ])
    service.reserver("standard", paris(2026, 10, 22, 10, 0), *SARA)  # rdv id 1
    h = agent.nouvelle_conversation()
    agent.repondre(h, "Je veux annuler mon rendez-vous, Ben Ali 0612345678")
    agent.repondre(h, "Oui, annulez")
    assert service.retrouver_rdv("Ben Ali", "0612345678") == []


# 4. Déplacement
def test_scenario_4_deplacement(regles):
    agent, service, _, _ = construire([
        msg_outil("retrouver_rdv", {"nom": "Ben Ali", "telephone": "0612345678"}),
        msg_texte("Quel nouveau créneau ?"),
        msg_outil("deplacer", {
            "rdv_id": "1", "nouveau_debut": "2026-10-21T11:00:00",
            "nom": "Ben Ali", "telephone": "0612345678",
        }),
        msg_texte("Votre rendez-vous est déplacé."),
    ])
    service.reserver("standard", paris(2026, 10, 22, 10, 0), *SARA)
    h = agent.nouvelle_conversation()
    agent.repondre(h, "Je veux décaler mon rendez-vous, Ben Ali 0612345678")
    agent.repondre(h, "Mercredi 11h")
    rdvs = service.retrouver_rdv("Ben Ali", "0612345678")
    assert len(rdvs) == 1 and rdvs[0].debut == paris(2026, 10, 21, 11, 0)


# 5. Question pratique (RAG)
def test_scenario_5_question_pratique(regles):
    agent, _, _, _ = construire([
        msg_outil("chercher_infos", {"question": "tarif remboursement"}),
        msg_texte("La consultation est à 30 euros."),
    ])
    h = agent.nouvelle_conversation()
    agent.repondre(h, "Quels sont vos tarifs ?")
    resultat = messages_outil(h)[0]
    assert resultat["ok"] is True
    assert any("30 euros" in p for p in resultat["passages"])


# 6. Urgence
def test_scenario_6_urgence(regles):
    agent, _, _, _ = construire([])  # le LLM ne doit pas être sollicité
    h = agent.nouvelle_conversation()
    reponse = agent.repondre(h, "J'ai très mal à la poitrine")
    assert reponse == MESSAGE_URGENCE
    assert agent.client.appels == []
    assert messages_outil(h) == []  # aucun outil appelé


# 8. Patient mécontent -> demande de rappel
def test_scenario_8_demande_de_rappel(regles):
    agent, _, journal, _ = construire([
        msg_outil("demander_rappel", {"nom": "Sara Ben Ali", "telephone": "0612345678", "motif": "mécontente"}),
        msg_texte("Je transmets votre demande au secrétariat, qui vous rappellera."),
    ])
    h = agent.nouvelle_conversation()
    agent.repondre(h, "Ça fait 3 fois que mon RDV est annulé ! Sara Ben Ali 0612345678")
    assert len(journal.lister()) == 1
    assert journal.lister()[0]["nom"] == "Sara Ben Ali"