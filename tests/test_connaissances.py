"""Phase 4 : la base de connaissances (RAG) retrouve le bon passage.
On utilise un FAUX embedder déterministe : aucun téléchargement, aucun réseau."""

import pytest

from agent_rdv.knowledge.base import BaseConnaissances
from agent_rdv.llm.outils import Dispatcheur, construire_schemas

VOCAB = ["tarif", "remboursement", "horaire", "samedi", "adresse",
         "metro", "parking", "document", "vitale", "ordonnance", "nouveau"]


def faux_embed(textes):
    """Vecteur = nombre d'occurrences de chaque mot du vocabulaire (sans accents)."""
    vecteurs = []
    for texte in textes:
        t = texte.lower()
        vecteurs.append([float(t.count(mot)) for mot in VOCAB])
    return vecteurs


PASSAGES = [
    ("tarifs", "Les tarifs : la consultation est à 30 euros, remboursement par la carte vitale."),
    ("horaires", "Les horaires : ouvert en semaine, fermé le samedi et le dimanche."),
    ("acces", "Adresse et acces : metro ligne 12, un parking public a cote."),
]


@pytest.fixture
def base():
    b = BaseConnaissances(faux_embed, nom_collection="test_cabinet")
    b.indexer(PASSAGES)
    return b


def test_vide_puis_rempli():
    b = BaseConnaissances(faux_embed, nom_collection="test_vide")
    assert b.est_vide() is True
    b.indexer(PASSAGES)
    assert b.est_vide() is False


def test_question_tarif_retrouve_le_passage_tarifs(base):
    passages = base.rechercher("quels sont vos tarifs et le remboursement ?", k=1)
    assert "30 euros" in passages[0]


def test_question_acces_retrouve_le_passage_acces(base):
    passages = base.rechercher("comment venir, y a-t-il un parking ?", k=1)
    assert "metro" in passages[0]


def test_dispatcheur_chercher_infos(service, base):
    disp = Dispatcheur(service, connaissances=base)
    res = disp.executer("chercher_infos", {"question": "vos horaires le samedi ?"})
    assert res["ok"] is True
    assert any("samedi" in p for p in res["passages"])


def test_dispatcheur_sans_rag_renvoie_indisponible(service):
    disp = Dispatcheur(service)  # pas de base de connaissances
    res = disp.executer("chercher_infos", {"question": "vos tarifs ?"})
    assert res["ok"] is False
    assert res["code"] == "indisponible"


def test_schemas_incluent_chercher_infos_seulement_si_demande(regles):
    sans = {s["function"]["name"] for s in construire_schemas(regles)}
    avec = {s["function"]["name"] for s in construire_schemas(regles, avec_infos=True)}
    assert "chercher_infos" not in sans
    assert "chercher_infos" in avec