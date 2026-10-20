"""Chat web (côté patient) + espace médecin protégé (côté admin).

creer_app(agent=..., comptes=...) permet d'injecter de faux objets dans les tests.
Sans argument, l'agent réel est construit à la première requête (ni clé ni réseau
nécessaires à l'import), et les comptes médecins sont ouverts depuis leur fichier."""

from __future__ import annotations

import html
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from ..admin.comptes import Comptes

RACINE = Path(__file__).resolve().parents[3]
DOSSIER_WEB = RACINE / "src" / "agent_rdv" / "web"


class MessageEntrant(BaseModel):
    message: str
    session_id: str | None = None


def _page(nom: str) -> str:
    return (DOSSIER_WEB / nom).read_text(encoding="utf-8")


TYPES_LISIBLES = {
    "standard": "Consultation",
    "nouveau_patient": "Nouveau patient",
    "suivi": "Suivi",
    "urgence": "Urgence",
}


def _lignes_rdv(service) -> str:
    """Tableau HTML des rendez-vous du jour ; message si la journée est vide."""
    try:
        rdvs = service.rdv_du_jour()
    except Exception as e:  # réseau coupé, Google injoignable…
        print(f"(Agenda indisponible : {type(e).__name__} : {e})")
        return '<p class="vide">Agenda momentanément indisponible. Rechargez la page.</p>'
    if not rdvs:
        return '<p class="vide">Aucun rendez-vous aujourd\'hui.</p>'
    lignes = []
    for r in rdvs:
        p = r["patient"]
        nom = html.escape(f"{p.prenom} {p.nom}") if p else "Patient inconnu"
        tel = html.escape(p.telephone) if p else "—"
        heure = r["debut"].strftime("%H:%M")
        type_lisible = html.escape(TYPES_LISIBLES.get(r["type"], r["type"]))
        lignes.append(
            f'<tr><td class="heure">{heure}</td><td>{nom}</td>'
            f'<td class="heure">{tel}</td><td class="type">{type_lisible}</td></tr>'
        )
    return (
        "<table><thead><tr><th>Heure</th><th>Patient</th><th>Téléphone</th>"
        "<th>Motif</th></tr></thead><tbody>" + "".join(lignes) + "</tbody></table>"
    )


def _lignes_demandes(service) -> str:
    """Tableau HTML des demandes de rappel non traitées, avec un bouton pour les clôturer."""
    journal = getattr(service, "journal", None)
    demandes = journal.lister() if journal else []
    if not demandes:
        return '<p class="vide">Aucune demande de rappel en attente.</p>'
    lignes = []
    for d in demandes:
        nom = html.escape(d["nom"])
        tel = html.escape(d["telephone"])
        motif = html.escape(d["motif"]) if d["motif"] else "—"
        bouton = (
            f'<form class="traiter" method="post" action="/medecin/demandes/{d["id"]}/traiter">'
            '<button class="traiter" type="submit">Marquer traitée</button></form>'
        )
        lignes.append(
            f'<tr><td>{nom}</td><td class="heure">{tel}</td>'
            f'<td>{motif}</td><td>{bouton}</td></tr>'
        )
    return (
        "<table><thead><tr><th>Nom</th><th>Téléphone</th><th>Motif</th>"
        "<th></th></tr></thead><tbody>" + "".join(lignes) + "</tbody></table>"
    )


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


def creer_app(agent=None, comptes: Comptes | None = None) -> FastAPI:
    app = FastAPI(title="Agent RDV")
    app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-cle-a-changer"))
    sessions: dict[str, list[dict]] = {}
    etat = {"agent": agent}
    comptes = comptes or Comptes(os.getenv("COMPTES_FICHIER", "data/medecins.sqlite"))

    def obtenir_agent():
        if etat["agent"] is None:
            etat["agent"] = _construire_agent_reel()
        return etat["agent"]

    # ---------- Côté patient (public) ----------

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _page("page.html")

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

    # ---------- Côté médecin (protégé par mot de passe) ----------

    @app.get("/medecin/login", response_class=HTMLResponse)
    def page_connexion():
        return _page("login.html")

    @app.post("/medecin/login")
    def connexion(request: Request, utilisateur: str = Form(...), mot_de_passe: str = Form(...)):
        if comptes.verifier_identifiants(utilisateur, mot_de_passe):
            request.session["medecin"] = utilisateur.strip().lower()
            return RedirectResponse("/medecin", status_code=303)
        return RedirectResponse("/medecin/login?erreur=1", status_code=303)

    @app.get("/medecin/logout")
    def deconnexion(request: Request):
        request.session.clear()
        return RedirectResponse("/medecin/login", status_code=303)

    @app.get("/medecin", response_class=HTMLResponse)
    def tableau_de_bord(request: Request):
        if not request.session.get("medecin"):
            return RedirectResponse("/medecin/login", status_code=303)
        service = obtenir_agent().service
        page = _page("dashboard.html")
        page = page.replace("{{DATE}}", service.maintenant().strftime("%d/%m/%Y"))
        page = page.replace("{{RDV}}", _lignes_rdv(service))
        page = page.replace("{{DEMANDES}}", _lignes_demandes(service))
        return page

    @app.post("/medecin/demandes/{demande_id}/traiter")
    def traiter_demande(request: Request, demande_id: int):
        if not request.session.get("medecin"):
            return RedirectResponse("/medecin/login", status_code=303)
        journal = getattr(obtenir_agent().service, "journal", None)
        if journal:
            journal.marquer_traitee(demande_id)
        return RedirectResponse("/medecin", status_code=303)

    return app


app = creer_app()
