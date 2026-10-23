"""Génération PDF d'un document patient (compte-rendu ou ordonnance), avec fpdf2.

Garde-fou : un document encore en brouillon est estampillé « BROUILLON — non
validé », pour qu'un brouillon ne puisse jamais passer pour un document signé."""

from __future__ import annotations

from datetime import date

from fpdf import FPDF

from .dossiers import VALIDE

TITRES = {
    "compte_rendu": "Compte-rendu de consultation",
    "ordonnance": "Ordonnance",
}


def _txt(valeur: str) -> str:
    """Les polices de base de fpdf2 sont en latin-1 ; on remplace ce qui n'y entre pas."""
    return (valeur or "").encode("latin-1", "replace").decode("latin-1")


def _section(pdf: FPDF, titre: str, contenu: str) -> None:
    if not contenu.strip():
        return
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, text=_txt(titre), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, text=_txt(contenu))
    pdf.ln(3)


def construire_pdf(cabinet_nom: str, patient, document: dict) -> bytes:
    """Rend le PDF d'un document sous forme d'octets, prêts à télécharger."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # En-tête cabinet
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, text=_txt(cabinet_nom), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
    pdf.ln(6)

    # Titre + statut
    titre = TITRES.get(document["type"], document["type"])
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, text=_txt(titre), new_x="LMARGIN", new_y="NEXT")
    if document["statut"] != VALIDE:
        pdf.set_text_color(179, 38, 30)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, text="BROUILLON - document non valide", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, text=_txt(f"Date : {document['cree_le'][:10]}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Patient
    email = f" - {patient.email}" if getattr(patient, "email", None) else ""
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, text="Patient", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, text=_txt(f"{patient.prenom} {patient.nom}\n{patient.telephone}{email}"))
    pdf.ln(3)

    # Contenu
    _section(pdf, "Observations", document["observations"])
    _section(pdf, "Synthese / diagnostic", document["synthese"])
    _section(pdf, "Ordonnance", document["ordonnance"])

    # Pied de page
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    mention = (
        "Document genere par l'assistant du cabinet."
        if document["statut"] == VALIDE
        else "Brouillon non valide - a relire et valider par le medecin."
    )
    pdf.multi_cell(0, 5, text=_txt(mention))

    sortie = pdf.output()
    return bytes(sortie)


def nom_fichier(patient, document: dict) -> str:
    """Nom de fichier lisible et sans caractères gênants."""
    base = f"{document['type']}_{patient.nom}_{patient.prenom}_{date.fromisoformat(document['cree_le'][:10])}"
    sûr = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    return f"{sûr}.pdf"
