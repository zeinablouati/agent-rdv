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


EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}


def _lire_fichier(fichier: Path) -> str:
    """Extrait le texte brut d'un fichier (.md, .txt, .pdf, .docx)."""
    suffixe = fichier.suffix.lower()
    if suffixe in {".md", ".txt"}:
        return fichier.read_text(encoding="utf-8")
    if suffixe == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join((page.extract_text() or "") for page in PdfReader(str(fichier)).pages)
    if suffixe == ".docx":
        import docx

        return "\n\n".join(p.text for p in docx.Document(str(fichier)).paragraphs)
    return ""


def _decouper_par_taille(texte: str, taille: int = 800, chevauchement: int = 100) -> list[str]:
    """Découpe un texte en morceaux qui se chevauchent (pour PDF/Word, sans structure nette)."""
    texte = re.sub(r"[ \t]+", " ", texte).strip()
    if not texte:
        return []
    morceaux, debut = [], 0
    while debut < len(texte):
        morceau = texte[debut:debut + taille].strip()
        if morceau:
            morceaux.append(morceau)
        debut += taille - chevauchement
    return morceaux


def _decouper(texte: str, suffixe: str) -> list[str]:
    if suffixe in {".md", ".txt"}:  # structure propre : on coupe aux lignes vides
        return [
            bloc.strip() for bloc in re.split(r"\n\s*\n", texte)
            if bloc.strip() and not bloc.strip().startswith("# ")  # on saute le grand titre
        ]
    return _decouper_par_taille(texte)


def charger_passages(dossier) -> list[tuple[str, str]]:
    """Découpe tous les fichiers pris en charge (.md, .txt, .pdf, .docx) d'un dossier
    en passages prêts à être indexés."""
    passages: list[tuple[str, str]] = []
    for fichier in sorted(Path(dossier).iterdir()):
        if not fichier.is_file() or fichier.suffix.lower() not in EXTENSIONS:
            continue
        texte = _lire_fichier(fichier)
        for i, bloc in enumerate(_decouper(texte, fichier.suffix.lower())):
            passages.append((f"{fichier.name}#{i}", bloc))
    return passages


class BaseConnaissances:
    def __init__(self, embed: Embedder, chemin: Optional[str] = None, nom_collection: str = "cabinet"):
        self.embed = embed
        self.nom_collection = nom_collection
        self.client = chromadb.PersistentClient(path=chemin) if chemin else chromadb.Client()
        self.collection = self.client.get_or_create_collection(nom_collection)

    def reinitialiser(self) -> None:
        """Vide complètement l'index (supprime la collection et la recrée),
        pour une reconstruction propre sans doublons ni passages périmés."""
        try:
            self.client.delete_collection(self.nom_collection)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(self.nom_collection)

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