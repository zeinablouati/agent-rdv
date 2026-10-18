"""Journal des demandes de rappel : quand l'agent passe la main, il y consigne
le nom, le téléphone et le motif, pour que le secrétariat recontacte le patient."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

from .agenda.erreurs import DonneesInvalides
from .agenda.registre import normaliser_telephone


class JournalDemandes:
    def __init__(self, chemin: str = ":memory:"):
        self._verrou = threading.Lock()
        self._cx = sqlite3.connect(chemin, check_same_thread=False)
        self._cx.execute(
            """CREATE TABLE IF NOT EXISTS demandes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horodatage TEXT NOT NULL,
                nom TEXT NOT NULL,
                telephone TEXT NOT NULL,
                motif TEXT,
                traitee INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self._cx.commit()

    def ajouter(self, nom: str, telephone: str, motif: str = "") -> int:
        nom = (nom or "").strip()
        if not nom:
            raise DonneesInvalides("Le nom est obligatoire pour une demande de rappel.")
        tel = normaliser_telephone(telephone)
        horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._verrou:
            curseur = self._cx.execute(
                "INSERT INTO demandes (horodatage, nom, telephone, motif) VALUES (?, ?, ?, ?)",
                (horodatage, nom, tel, (motif or "").strip()),
            )
            self._cx.commit()
            return curseur.lastrowid

    def lister(self, inclure_traitees: bool = False) -> list[dict]:
        requete = "SELECT id, horodatage, nom, telephone, motif, traitee FROM demandes"
        if not inclure_traitees:
            requete += " WHERE traitee = 0"
        requete += " ORDER BY horodatage"
        with self._verrou:
            lignes = self._cx.execute(requete).fetchall()
        return [
            {"id": r[0], "horodatage": r[1], "nom": r[2], "telephone": r[3], "motif": r[4], "traitee": bool(r[5])}
            for r in lignes
        ]

    def marquer_traitee(self, demande_id: int) -> None:
        with self._verrou:
            self._cx.execute("UPDATE demandes SET traitee = 1 WHERE id = ?", (demande_id,))
            self._cx.commit()