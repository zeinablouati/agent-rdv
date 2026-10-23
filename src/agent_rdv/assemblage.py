"""Montage de l'agent réel à partir du .env, réutilisable par tous les canaux
(chat terminal, chat web, voix). Un seul endroit où brancher les vraies pièces."""

from __future__ import annotations

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def charger_connaissances():
    """Charge la base RAG si l'index existe et que sentence-transformers est là."""
    chemin_index = str(RACINE / "data" / "chroma")
    if not os.path.isdir(chemin_index):
        return None
    try:
        from .knowledge.base import BaseConnaissances, embedder_sentence_transformers

        modele_rag = os.getenv("RAG_MODELE", "paraphrase-multilingual-MiniLM-L12-v2")
        base = BaseConnaissances(embedder_sentence_transformers(modele_rag), chemin=chemin_index)
        return None if base.est_vide() else base
    except Exception as erreur:
        print(f"(RAG indisponible : {erreur})")
        return None


def construire_agent_reel(trace=None):
    """Construit l'AgentRDV complet. Nécessite GROQ_API_KEY dans l'environnement."""
    from dotenv import load_dotenv
    from groq import Groq

    from .agenda.fabrique import construire_agenda
    from .agenda.registre import RegistrePatients
    from .agenda.service import ServiceRendezVous
    from .config import charger_regles
    from .demandes import JournalDemandes
    from .llm.agent import AgentRDV
    from .notifications.base import construire_notificateur

    load_dotenv()
    cle = os.getenv("GROQ_API_KEY")
    if not cle:
        raise RuntimeError("GROQ_API_KEY est absent du .env.")
    modele = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

    regles = charger_regles()
    service = ServiceRendezVous(
        regles,
        construire_agenda(regles),
        RegistrePatients(os.getenv("REGISTRE_FICHIER", "data/patients.sqlite")),
        notificateur=construire_notificateur(),
        journal=JournalDemandes(os.getenv("DEMANDES_FICHIER", "data/demandes.sqlite")),
    )
    return AgentRDV(
        service, regles, Groq(api_key=cle), modele,
        trace=trace, connaissances=charger_connaissances(),
    )
