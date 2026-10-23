"""Vague 4b : l'espace médecin pour les fiches patients (liste, fiche, documents)."""

import pytest
from fastapi.testclient import TestClient

from agent_rdv.admin.comptes import Comptes
from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.config import charger_regles
from agent_rdv.dossiers import DossiersPatients
from agent_rdv.llm.agent import AgentRDV
from agent_rdv.redaction import RedacteurMedical
from agent_rdv.web.app import creer_app

from test_agent import FauxClient, msg_texte


@pytest.fixture
def materiel(regles, horloge):
    registre = RegistrePatients()
    patient = registre.obtenir_ou_creer("Marie", "Durand", "0612345678")
    service = ServiceRendezVous(regles, AgendaLocal(fuseau=regles.fuseau), registre, horloge)
    dossiers = DossiersPatients()
    comptes = Comptes()
    comptes.creer("drtest", "motdepasse")
    agent = AgentRDV(service, regles, FauxClient([msg_texte("ok")]), "faux")
    client = TestClient(creer_app(agent=agent, comptes=comptes, dossiers=dossiers))
    client.post("/medecin/login", data={"utilisateur": "drtest", "mot_de_passe": "motdepasse"})
    return client, patient, dossiers


def test_la_liste_des_patients_demande_le_login(regles):
    # sans session : redirection vers le login
    service = ServiceRendezVous(regles, AgendaLocal(fuseau=regles.fuseau), RegistrePatients())
    agent = AgentRDV(service, regles, FauxClient([msg_texte("ok")]), "faux")
    c = TestClient(creer_app(agent=agent, comptes=Comptes(), dossiers=DossiersPatients()))
    assert c.get("/medecin/patients", follow_redirects=False).status_code == 303


def test_la_liste_affiche_le_patient(materiel):
    client, patient, _ = materiel
    page = client.get("/medecin/patients").text
    assert "Marie Durand" in page
    assert f"/medecin/patient/{patient.id}" in page


def test_la_fiche_affiche_le_patient(materiel):
    client, patient, _ = materiel
    page = client.get(f"/medecin/patient/{patient.id}").text
    assert "Marie Durand" in page and "0612345678" in page
    assert "Nouveau document" in page


def test_creer_un_document_le_fait_apparaitre_en_brouillon(materiel):
    client, patient, dossiers = materiel
    client.post(
        f"/medecin/patient/{patient.id}/document",
        data={"type": "compte_rendu", "observations": "Toux", "synthese": "", "ordonnance": ""},
        follow_redirects=False,
    )
    docs = dossiers.lister(patient.id)
    assert len(docs) == 1 and docs[0]["statut"] == "brouillon"
    page = client.get(f"/medecin/patient/{patient.id}").text
    assert "Toux" in page and "brouillon" in page


def test_valider_un_document_le_fige(materiel):
    client, patient, dossiers = materiel
    doc_id = dossiers.ajouter(patient.id, observations="Fièvre", synthese="Grippe probable")
    client.post(f"/medecin/document/{doc_id}/valider", follow_redirects=False)
    assert dossiers.obtenir(doc_id)["statut"] == "valide"
    page = client.get(f"/medecin/patient/{patient.id}").text
    assert "validé" in page
    assert "Valider ce document" not in page  # plus de bouton de validation


def test_supprimer_un_document(materiel):
    client, patient, dossiers = materiel
    doc_id = dossiers.ajouter(patient.id, observations="erreur de saisie")
    client.post(f"/medecin/document/{doc_id}/supprimer", follow_redirects=False)
    assert dossiers.lister(patient.id) == []


def test_fiche_patient_inconnu_redirige(materiel):
    client, _, _ = materiel
    assert client.get("/medecin/patient/9999", follow_redirects=False).status_code == 303


def test_telecharger_un_document_en_pdf(materiel):
    client, patient, dossiers = materiel
    doc_id = dossiers.ajouter(patient.id, type="ordonnance", ordonnance="Paracétamol 1 g")
    reponse = client.get(f"/medecin/document/{doc_id}/pdf")
    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "application/pdf"
    assert "attachment" in reponse.headers["content-disposition"]
    assert reponse.content[:4] == b"%PDF"  # c'est bien un PDF


def test_le_lien_pdf_est_present_dans_la_fiche(materiel):
    client, patient, dossiers = materiel
    dossiers.ajouter(patient.id, observations="Toux")
    assert "/pdf" in client.get(f"/medecin/patient/{patient.id}").text


def test_prerediger_avec_ia_remplit_la_synthese(regles, horloge):
    registre = RegistrePatients()
    patient = registre.obtenir_ou_creer("Marie", "Durand", "0612345678")
    service = ServiceRendezVous(regles, AgendaLocal(fuseau=regles.fuseau), registre, horloge)
    dossiers = DossiersPatients()
    comptes = Comptes()
    comptes.creer("drtest", "motdepasse")
    agent = AgentRDV(service, regles, FauxClient([msg_texte("ok")]), "faux")
    redacteur = RedacteurMedical(FauxClient([msg_texte("Toux depuis 5 jours, apyrétique.")]), "faux")
    client = TestClient(creer_app(agent=agent, comptes=comptes, dossiers=dossiers, redacteur=redacteur))
    client.post("/medecin/login", data={"utilisateur": "drtest", "mot_de_passe": "motdepasse"})

    client.post(
        f"/medecin/patient/{patient.id}/document",
        data={"type": "compte_rendu", "observations": "toux 5j", "synthese": "",
              "ordonnance": "", "action": "ia"},
        follow_redirects=False,
    )
    docs = dossiers.lister(patient.id)
    assert len(docs) == 1
    assert "apyrétique" in docs[0]["synthese"]  # la synthèse a bien été pré-rédigée par l'IA
    assert docs[0]["statut"] == "brouillon"  # et reste un brouillon à valider
