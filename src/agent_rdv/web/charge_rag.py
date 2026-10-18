"""Chargement de la base RAG pour le serveur web (identique au chat terminal)."""

from __future__ import annotations

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]


def charger_connaissances():
    chemin_index = str(RACINE / "data" / "chroma")
    if not os.path.isdir(chemin_index):
        return None
    try:
        from ..knowledge.base import BaseConnaissances, embedder_sentence_transformers

        modele_rag = os.getenv("RAG_MODELE", "paraphrase-multilingual-MiniLM-L12-v2")
        base = BaseConnaissances(embedder_sentence_transformers(modele_rag), chemin=chemin_index)
        return None if base.est_vide() else base
    except Exception as erreur:
        print(f"(RAG indisponible : {erreur})")
        return None