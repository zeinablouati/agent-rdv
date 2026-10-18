"""Chat avec l'agent dans le terminal (Phases 3 et 4).

  python scripts/chat.py

Nécessite GROQ_API_KEY dans .env. L'agenda dépend de AGENDA (local ou google).
Les infos pratiques (RAG) sont actives si tu as lancé scripts/indexer.py.
Mets DEBUG=1 dans .env pour voir les appels d'outils. Tape 'quit' pour sortir.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
from groq import Groq

from agent_rdv.agenda.fabrique import construire_agenda
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.config import charger_regles
from agent_rdv.llm.agent import AgentRDV

load_dotenv()

cle = os.getenv("GROQ_API_KEY")
if not cle:
    sys.exit("GROQ_API_KEY est absent du .env.")
modele = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def trace(nom, arguments, resultat):
    print(f"   ⤷ outil {nom}({json.dumps(arguments, ensure_ascii=False)}) => {json.dumps(resultat, ensure_ascii=False)}")


debug = os.getenv("DEBUG", "").strip() in {"1", "true", "True"}


def charger_connaissances():
    """Charge la base RAG si l'index existe et sentence-transformers est installé."""
    chemin_index = str(Path(__file__).resolve().parents[1] / "data" / "chroma")
    if not os.path.isdir(chemin_index):
        return None
    try:
        from agent_rdv.knowledge.base import BaseConnaissances, embedder_sentence_transformers
        modele_rag = os.getenv("RAG_MODELE", "paraphrase-multilingual-MiniLM-L12-v2")
        base = BaseConnaissances(embedder_sentence_transformers(modele_rag), chemin=chemin_index)
        return None if base.est_vide() else base
    except Exception as erreur:
        print(f"(RAG indisponible : {erreur})")
        return None


from agent_rdv.notifications.base import construire_notificateur
from agent_rdv.demandes import JournalDemandes

regles = charger_regles()
connaissances = charger_connaissances()
service = ServiceRendezVous(
    regles,
    construire_agenda(regles),
    RegistrePatients(os.getenv("REGISTRE_FICHIER", "data/patients.sqlite")),
    notificateur=construire_notificateur(),
    journal=JournalDemandes(os.getenv("DEMANDES_FICHIER", "data/demandes.sqlite")),
)
agent = AgentRDV(
    service, regles, Groq(api_key=cle), modele,
    trace=trace if debug else None,
    connaissances=connaissances,
)
print("Infos pratiques (RAG) :", "activées" if connaissances else "désactivées (lance scripts/indexer.py)")

historique = agent.nouvelle_conversation()

print(f"Agent prêt (modèle {modele}, agenda {type(service.agenda).__name__}). Tape 'quit' pour sortir.\n")
print("Agent : Bonjour, je suis l'assistant du cabinet. Comment puis-je vous aider ?\n")

while True:
    try:
        message = input("Vous  : ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break
    if message.lower() in {"quit", "exit", "q"}:
        break
    if not message:
        continue
    print("Agent :", agent.repondre(historique, message), "\n")