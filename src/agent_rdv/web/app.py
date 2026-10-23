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
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from ..admin.comptes import Comptes
from ..dossiers import VALIDE, DossiersPatients
from ..pdf_documents import construire_pdf, nom_fichier
from ..redaction import RedacteurMedical

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
    except Exception:  # agenda injoignable (ex. Google indisponible) : on n'écroule pas la page
        return '<p class="vide">Agenda momentanément indisponible. Réessayez dans un instant.</p>'
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
    try:
        demandes = journal.lister() if journal else []
    except Exception:
        return '<p class="vide">Demandes momentanément indisponibles.</p>'
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


TYPES_DOC_LISIBLES = {
    "compte_rendu": "Compte-rendu de consultation",
    "ordonnance": "Ordonnance",
}


def _corps_patients(registre) -> str:
    """Liste de tous les patients, avec un lien vers chaque fiche."""
    patients = registre.lister_tous()
    if not patients:
        return '<section><h2>Patients</h2><p class="vide">Aucun patient enregistré.</p></section>'
    lignes = "".join(
        f'<tr><td><a class="lien" href="/medecin/patient/{p.id}">'
        f'{html.escape(p.prenom)} {html.escape(p.nom)}</a></td>'
        f'<td class="heure">{html.escape(p.telephone)}</td></tr>'
        for p in patients
    )
    return (
        '<section><h2>Patients</h2><table><thead><tr><th>Nom</th><th>Téléphone</th>'
        f'</tr></thead><tbody>{lignes}</tbody></table></section>'
    )


def _champ_fige(titre: str, valeur: str) -> str:
    if not valeur:
        return ""
    return f'<label>{titre}</label><div class="fige">{html.escape(valeur)}</div>'


def _bloc_document(d: dict) -> str:
    """Un document : lecture seule s'il est validé, modifiable s'il est en brouillon."""
    type_lisible = html.escape(TYPES_DOC_LISIBLES.get(d["type"], d["type"]))
    date = d["cree_le"][:10]
    if d["statut"] == VALIDE:
        badge = '<span class="badge valide">validé</span>'
        corps = (
            _champ_fige("Observations", d["observations"])
            + _champ_fige("Synthèse / diagnostic", d["synthese"])
            + _champ_fige("Ordonnance", d["ordonnance"])
        ) or '<p class="vide">Document vide.</p>'
    else:
        badge = '<span class="badge brouillon">brouillon</span>'
        corps = (
            f'<form class="inline" method="post" action="/medecin/document/{d["id"]}/modifier">'
            '<label>Observations</label>'
            f'<textarea name="observations">{html.escape(d["observations"])}</textarea>'
            '<label>Synthèse / diagnostic</label>'
            f'<textarea name="synthese">{html.escape(d["synthese"])}</textarea>'
            '<label>Ordonnance</label>'
            f'<textarea name="ordonnance">{html.escape(d["ordonnance"])}</textarea>'
            '<div class="ligne-boutons"><button class="discret" type="submit">Enregistrer</button></div>'
            '</form>'
            '<div class="ligne-boutons">'
            f'<form class="inline" method="post" action="/medecin/document/{d["id"]}/valider">'
            '<button class="valider" type="submit">Valider ce document</button></form>'
            f'<form class="inline" method="post" action="/medecin/document/{d["id"]}/supprimer">'
            '<button class="discret" type="submit">Supprimer</button></form>'
            '</div>'
        )
    telecharger = (
        f'<div class="ligne-boutons"><a class="lien" '
        f'href="/medecin/document/{d["id"]}/pdf">⬇ Télécharger le PDF</a></div>'
    )
    return (
        f'<div class="doc"><h3>{type_lisible} {badge}</h3>'
        f'<p class="meta">Créé le {date}</p>{corps}{telecharger}</div>'
    )


def _corps_fiche(patient, documents: list[dict]) -> str:
    """Fiche d'un patient : en-tête, formulaire de nouveau document, liste des documents."""
    email = f' · E-mail : {html.escape(patient.email)}' if patient.email else ""
    entete = (
        f'<section><h2>{html.escape(patient.prenom)} {html.escape(patient.nom)}</h2>'
        f'<p class="meta">Téléphone : {html.escape(patient.telephone)}{email} · '
        '<a class="lien" href="/medecin/patients">← tous les patients</a></p></section>'
    )
    formulaire = (
        '<section><h2>Nouveau document</h2>'
        '<p class="avert">« Pré-rédiger avec l\'IA » reformule vos observations en une '
        'synthèse (brouillon). L\'IA n\'invente rien et ne rédige pas l\'ordonnance. '
        'Rien n\'est définitif tant que vous n\'avez pas validé.</p>'
        f'<form method="post" action="/medecin/patient/{patient.id}/document">'
        '<label>Type</label>'
        '<select name="type"><option value="compte_rendu">Compte-rendu de consultation</option>'
        '<option value="ordonnance">Ordonnance</option></select>'
        '<label>Observations (ce que vous constatez)</label><textarea name="observations"></textarea>'
        '<label>Synthèse / diagnostic</label><textarea name="synthese"></textarea>'
        '<label>Ordonnance</label><textarea name="ordonnance"></textarea>'
        '<div class="ligne-boutons">'
        '<button class="principal" type="submit" name="action" value="manuel">Créer le brouillon</button>'
        '<button class="valider" type="submit" name="action" value="ia">Pré-rédiger avec l\'IA</button>'
        '</div></form></section>'
    )
    if not documents:
        liste = '<section><h2>Documents</h2><p class="vide">Aucun document pour ce patient.</p></section>'
    else:
        liste = '<section><h2>Documents</h2>' + "".join(_bloc_document(d) for d in documents) + "</section>"
    return entete + formulaire + liste


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


def creer_app(
    agent=None,
    comptes: Comptes | None = None,
    dossiers: DossiersPatients | None = None,
    redacteur: RedacteurMedical | None = None,
) -> FastAPI:
    app = FastAPI(title="Agent RDV")
    app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-cle-a-changer"))
    sessions: dict[str, list[dict]] = {}
    etat = {"agent": agent, "redacteur": redacteur}
    comptes = comptes or Comptes(os.getenv("COMPTES_FICHIER", "data/medecins.sqlite"))
    dossiers = dossiers or DossiersPatients(os.getenv("DOSSIERS_FICHIER", "data/dossiers.sqlite"))

    def obtenir_agent():
        if etat["agent"] is None:
            etat["agent"] = _construire_agent_reel()
        return etat["agent"]

    def obtenir_redacteur():
        """Réutilise le client LLM de l'agent pour rédiger les brouillons."""
        if etat["redacteur"] is None:
            ag = obtenir_agent()
            etat["redacteur"] = RedacteurMedical(ag.client, ag.modele)
        return etat["redacteur"]

    def _refuser_si_non_connecte(request: Request):
        """Rend une redirection vers le login si la session n'est pas celle d'un médecin, sinon None."""
        if not request.session.get("medecin"):
            return RedirectResponse("/medecin/login", status_code=303)
        return None

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
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        journal = getattr(obtenir_agent().service, "journal", None)
        if journal:
            journal.marquer_traitee(demande_id)
        return RedirectResponse("/medecin", status_code=303)

    # ---------- Fiches patients (vague 4) ----------

    @app.get("/medecin/patients", response_class=HTMLResponse)
    def page_patients(request: Request):
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        registre = obtenir_agent().service.registre
        return _page("medecin.html").replace("{{TITRE}}", "Patients").replace(
            "{{CORPS}}", _corps_patients(registre)
        )

    @app.get("/medecin/patient/{patient_id}", response_class=HTMLResponse)
    def page_fiche(request: Request, patient_id: int):
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        patient = obtenir_agent().service.registre.obtenir_par_id(patient_id)
        if patient is None:
            return RedirectResponse("/medecin/patients", status_code=303)
        corps = _corps_fiche(patient, dossiers.lister(patient_id))
        return _page("medecin.html").replace(
            "{{TITRE}}", f"{patient.prenom} {patient.nom}"
        ).replace("{{CORPS}}", corps)

    @app.post("/medecin/patient/{patient_id}/document")
    def creer_document(
        request: Request,
        patient_id: int,
        type: str = Form("compte_rendu"),
        observations: str = Form(""),
        synthese: str = Form(""),
        ordonnance: str = Form(""),
        action: str = Form("manuel"),
    ):
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        # Bouton « Pré-rédiger avec l'IA » : on remplace la synthèse par le brouillon généré.
        if action == "ia":
            try:
                synthese = obtenir_redacteur().rediger_synthese(observations, type)
            except Exception:  # IA indisponible : on garde ce que le médecin a saisi
                pass
        try:
            dossiers.ajouter(patient_id, type=type, observations=observations,
                             synthese=synthese, ordonnance=ordonnance)
        except Exception:  # type invalide, etc. : on revient simplement à la fiche
            pass
        return RedirectResponse(f"/medecin/patient/{patient_id}", status_code=303)

    @app.post("/medecin/document/{document_id}/modifier")
    def modifier_document(
        request: Request,
        document_id: int,
        observations: str = Form(""),
        synthese: str = Form(""),
        ordonnance: str = Form(""),
    ):
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        doc = dossiers.obtenir(document_id)
        if doc is None:
            return RedirectResponse("/medecin/patients", status_code=303)
        try:
            dossiers.mettre_a_jour(document_id, observations=observations,
                                   synthese=synthese, ordonnance=ordonnance)
        except Exception:
            pass
        return RedirectResponse(f"/medecin/patient/{doc['patient_id']}", status_code=303)

    @app.post("/medecin/document/{document_id}/valider")
    def valider_document(request: Request, document_id: int):
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        doc = dossiers.obtenir(document_id)
        if doc is None:
            return RedirectResponse("/medecin/patients", status_code=303)
        dossiers.valider(document_id)
        return RedirectResponse(f"/medecin/patient/{doc['patient_id']}", status_code=303)

    @app.post("/medecin/document/{document_id}/supprimer")
    def supprimer_document(request: Request, document_id: int):
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        doc = dossiers.obtenir(document_id)
        if doc is None:
            return RedirectResponse("/medecin/patients", status_code=303)
        dossiers.supprimer(document_id)
        return RedirectResponse(f"/medecin/patient/{doc['patient_id']}", status_code=303)

    @app.get("/medecin/document/{document_id}/pdf")
    def telecharger_pdf(request: Request, document_id: int):
        if (refus := _refuser_si_non_connecte(request)):
            return refus
        doc = dossiers.obtenir(document_id)
        if doc is None:
            return RedirectResponse("/medecin/patients", status_code=303)
        service = obtenir_agent().service
        patient = service.registre.obtenir_par_id(doc["patient_id"])
        if patient is None:
            return RedirectResponse("/medecin/patients", status_code=303)
        pdf = construire_pdf(service.regles.cabinet.nom, patient, doc)
        entetes = {"Content-Disposition": f'attachment; filename="{nom_fichier(patient, doc)}"'}
        return Response(content=pdf, media_type="application/pdf", headers=entetes)

    return app


app = creer_app()
