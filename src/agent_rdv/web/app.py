"""Chat web : une API FastAPI + une page de chat.

creer_app(agent=...) permet d'injecter un faux agent dans les tests.
Sans argument, l'agent réel (Groq + agenda + RAG) est construit à la première
requête, pour que l'import du module ne nécessite ni clé ni réseau."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

RACINE = Path(__file__).resolve().parents[3]


class MessageEntrant(BaseModel):
    message: str
    session_id: str | None = None


def _construire_agent_reel():
    """Construit l'agent réel à partir de l'environnement (.env déjà chargé)."""
    from dotenv import load_dotenv
    from groq import Groq

    from ..agenda.fabrique import construire_agenda
    from ..agenda.registre import RegistrePatients
    from ..agenda.service import ServiceRendezVous
    from ..config import charger_regles
    from .charge_rag import charger_connaissances
    from ..llm.agent import AgentRDV
    from ..notifications.base import construire_notificateur
    from ..demandes import JournalDemandes

    load_dotenv()
    cle = os.getenv("GROQ_API_KEY")
    if not cle:
        raise RuntimeError("GROQ_API_KEY est absent du .env.")
    modele = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    regles = charger_regles()
    service = ServiceRendezVous(
        regles,
        construire_agenda(regles),
        RegistrePatients(os.getenv("REGISTRE_FICHIER", "data/patients.sqlite")),
        notificateur=construire_notificateur(),
        journal=JournalDemandes(os.getenv("DEMANDES_FICHIER", "data/demandes.sqlite")),
    )
    return AgentRDV(service, regles, Groq(api_key=cle), modele, connaissances=charger_connaissances())


def creer_app(agent=None) -> FastAPI:
    app = FastAPI(title="Agent RDV")
    sessions: dict[str, list[dict]] = {}
    etat = {"agent": agent}

    def obtenir_agent():
        if etat["agent"] is None:
            etat["agent"] = _construire_agent_reel()
        return etat["agent"]

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (RACINE / "src" / "agent_rdv" / "web" / "page.html").read_text(encoding="utf-8")

    @app.post("/api/chat")
    def chat(entree: MessageEntrant):
        agent = obtenir_agent()
        session_id = entree.session_id or uuid.uuid4().hex
        historique = sessions.setdefault(session_id, agent.nouvelle_conversation())
        try:
            reponse = agent.repondre(historique, entree.message)
        except Exception as erreur:  # en prototype, on renvoie l'erreur comme message
            reponse = f"Désolé, une erreur est survenue : {erreur}"
        return {"reply": reponse, "session_id": session_id}

    return app


app = creer_app()