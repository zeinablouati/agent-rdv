"""Base de connaissances (RAG) : indexe les infos pratiques du cabinet dans
ChromaDB et retrouve les passages pertinents pour une question.

L'embedder (fonction texte -> vecteurs) est INJECTÉ : un vrai modèle
(sentence-transformers) en production, un faux déterministe dans les tests.
On calcule les vecteurs nous-mêmes et on les passe à Chroma : robuste et simple."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

import chromadb

Embedder = Callable[[list[str]], list[list[float]]]


def charger_passages(dossier) -> list[tuple[str, str]]:
    """Découpe les fichiers .md d'un dossier en passages (séparés par une ligne vide)."""
    passages: list[tuple[str, str]] = []
    for fichier in sorted(Path(dossier).glob("*.md")):
        texte = fichier.read_text(encoding="utf-8")
        for i, bloc in enumerate(b.strip() for b in re.split(r"\n\s*\n", texte)):
            if bloc and not bloc.startswith("# "):  # on saute le grand titre
                passages.append((f"{fichier.stem}#{i}", bloc))
    return passages


class BaseConnaissances:
    def __init__(self, embed: Embedder, chemin: Optional[str] = None, nom_collection: str = "cabinet"):
        self.embed = embed
        self.client = chromadb.PersistentClient(path=chemin) if chemin else chromadb.Client()
        self.collection = self.client.get_or_create_collection(nom_collection)

    def indexer(self, passages: list[tuple[str, str]]) -> int:
        if not passages:
            return 0
        ids = [pid for pid, _ in passages]
        docs = [txt for _, txt in passages]
        self.collection.upsert(ids=ids, documents=docs, embeddings=self.embed(docs))
        return len(passages)

    def rechercher(self, question: str, k: int = 3) -> list[str]:
        if self.collection.count() == 0:
            return []
        resultat = self.collection.query(query_embeddings=self.embed([question]), n_results=k)
        return resultat.get("documents", [[]])[0]

    def est_vide(self) -> bool:
        return self.collection.count() == 0


def embedder_sentence_transformers(nom_modele: str = "paraphrase-multilingual-MiniLM-L12-v2") -> Embedder:
    """Charge un modèle d'embeddings multilingue (français compris).
    Import tardif : sentence-transformers n'est requis que si on utilise le RAG."""
    from sentence_transformers import SentenceTransformer

    modele = SentenceTransformer(nom_modele)

    def embed(textes: list[str]) -> list[list[float]]:
        return modele.encode(textes, normalize_embeddings=True).tolist()

    return embed