"""Construit l'index RAG à partir de data/knowledge/*.md.

  python scripts/indexer.py

La première fois, télécharge le modèle d'embeddings (quelques centaines de Mo).
À relancer chaque fois que tu modifies les fichiers de data/knowledge/."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv

from agent_rdv.knowledge.base import (
    BaseConnaissances,
    charger_passages,
    embedder_sentence_transformers,
)

load_dotenv()

RACINE = Path(__file__).resolve().parents[1]
dossier = RACINE / "data" / "knowledge"
chemin_index = str(RACINE / "data" / "chroma")
modele = os.getenv("RAG_MODELE", "paraphrase-multilingual-MiniLM-L12-v2")

print(f"Chargement du modèle d'embeddings ({modele})... (long la première fois)")
base = BaseConnaissances(embedder_sentence_transformers(modele), chemin=chemin_index)

base.reinitialiser()  # reconstruction à neuf : on efface l'ancien index d'abord
passages = charger_passages(dossier)
nombre = base.indexer(passages)
print(f"Indexé {nombre} passage(s) depuis {dossier}.")
for pid, _ in passages:
    print("  -", pid)
print("Index prêt dans data/chroma/.")