"""Dossiers patients : les documents médicaux rangés par patient
(comptes-rendus de consultation, ordonnances).

ATTENTION — données de santé. Ce stockage local SQLite est un PROTOTYPE.
Une mise en production réelle impose un hébergement certifié HDS et le respect
du RGPD (consentement, durée de conservation, droit à l'effacement).

Garde-fou produit : chaque document porte un STATUT. Tout ce que l'IA rédige
naît en « brouillon » et n'a aucune valeur tant que le médecin ne l'a pas
« validé ». L'IA assiste et met en forme ; elle ne décide jamais seule."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

from .agenda.erreurs import DonneesInvalides

BROUILLON = "brouillon"
VALIDE = "valide"
TYPES = ("compte_rendu", "ordonnance")


def _horodatage() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DossiersPatients:
    def __init__(self, chemin: str = ":memory:"):
        self._verrou = threading.Lock()
        self._cx = sqlite3.connect(chemin, check_same_thread=False)
        self._cx.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                cree_le TEXT NOT NULL,
                maj_le TEXT NOT NULL,
                type TEXT NOT NULL,
                observations TEXT NOT NULL DEFAULT '',
                synthese TEXT NOT NULL DEFAULT '',
                ordonnance TEXT NOT NULL DEFAULT '',
                statut TEXT NOT NULL DEFAULT 'brouillon'
            )"""
        )
        self._cx.commit()

    @staticmethod
    def _document(ligne) -> dict:
        return {
            "id": ligne[0],
            "patient_id": ligne[1],
            "cree_le": ligne[2],
            "maj_le": ligne[3],
            "type": ligne[4],
            "observations": ligne[5],
            "synthese": ligne[6],
            "ordonnance": ligne[7],
            "statut": ligne[8],
        }

    _COLONNES = (
        "id, patient_id, cree_le, maj_le, type, observations, synthese, ordonnance, statut"
    )

    def ajouter(
        self,
        patient_id: int,
        type: str = "compte_rendu",
        observations: str = "",
        synthese: str = "",
        ordonnance: str = "",
    ) -> int:
        """Crée un document, toujours en brouillon."""
        if type not in TYPES:
            raise DonneesInvalides(f"Type de document inconnu : {type!r}.")
        maintenant = _horodatage()
        with self._verrou:
            curseur = self._cx.execute(
                "INSERT INTO documents (patient_id, cree_le, maj_le, type, observations, "
                "synthese, ordonnance, statut) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (patient_id, maintenant, maintenant, type, observations.strip(),
                 synthese.strip(), ordonnance.strip(), BROUILLON),
            )
            self._cx.commit()
            return curseur.lastrowid

    def lister(self, patient_id: int) -> list[dict]:
        """Documents d'un patient, le plus récent d'abord."""
        with self._verrou:
            lignes = self._cx.execute(
                f"SELECT {self._COLONNES} FROM documents WHERE patient_id = ? "
                "ORDER BY cree_le DESC, id DESC",
                (patient_id,),
            ).fetchall()
        return [self._document(l) for l in lignes]

    def obtenir(self, document_id: int) -> dict | None:
        with self._verrou:
            ligne = self._cx.execute(
                f"SELECT {self._COLONNES} FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        return self._document(ligne) if ligne else None

    def mettre_a_jour(
        self,
        document_id: int,
        observations: str | None = None,
        synthese: str | None = None,
        ordonnance: str | None = None,
    ) -> None:
        """Modifie le contenu d'un document. Un document validé est figé : on refuse."""
        doc = self.obtenir(document_id)
        if doc is None:
            raise DonneesInvalides("Document introuvable.")
        if doc["statut"] == VALIDE:
            raise DonneesInvalides("Un document validé ne peut plus être modifié.")
        champs, valeurs = [], []
        for nom, valeur in (("observations", observations), ("synthese", synthese), ("ordonnance", ordonnance)):
            if valeur is not None:
                champs.append(f"{nom} = ?")
                valeurs.append(valeur.strip())
        if not champs:
            return
        champs.append("maj_le = ?")
        valeurs.append(_horodatage())
        valeurs.append(document_id)
        with self._verrou:
            self._cx.execute(f"UPDATE documents SET {', '.join(champs)} WHERE id = ?", valeurs)
            self._cx.commit()

    def valider(self, document_id: int) -> None:
        """Le médecin valide : le document passe de brouillon à définitif."""
        if self.obtenir(document_id) is None:
            raise DonneesInvalides("Document introuvable.")
        with self._verrou:
            self._cx.execute(
                "UPDATE documents SET statut = ?, maj_le = ? WHERE id = ?",
                (VALIDE, _horodatage(), document_id),
            )
            self._cx.commit()

    def supprimer(self, document_id: int) -> None:
        with self._verrou:
            self._cx.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            self._cx.commit()
