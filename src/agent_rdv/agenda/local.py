"""Agenda local (SQLite). Sert de base de développement et de tests :
aucun compte Google nécessaire."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, tzinfo
from typing import Sequence

from .base import Agenda
from .erreurs import ConflitCreneau, RdvIntrouvable
from .modeles import Rdv

_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _vers_db(dt: datetime) -> str:
    """Stockage en UTC : la comparaison de texte reste fiable malgré l'heure d'été."""
    if dt.tzinfo is None:
        raise ValueError("Une date avec fuseau horaire est obligatoire")
    return dt.astimezone(timezone.utc).strftime(_FORMAT)


class AgendaLocal(Agenda):
    def __init__(self, chemin: str = ":memory:", fuseau: tzinfo = timezone.utc):
        self._fuseau = fuseau
        self._verrou = threading.Lock()
        self._cx = sqlite3.connect(chemin, check_same_thread=False, isolation_level=None)
        self._cx.execute(
            """CREATE TABLE IF NOT EXISTS rdv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debut TEXT NOT NULL,
                fin TEXT NOT NULL,
                type_consultation TEXT NOT NULL,
                patient_id INTEGER NOT NULL
            )"""
        )

    @contextmanager
    def _transaction(self):
        with self._verrou:
            self._cx.execute("BEGIN IMMEDIATE")
            try:
                yield self._cx
            except BaseException:
                self._cx.execute("ROLLBACK")
                raise
            else:
                self._cx.execute("COMMIT")

    def _rdv(self, ligne) -> Rdv:
        id_, debut, fin, type_consultation, patient_id = ligne
        def lire(texte: str) -> datetime:
            return datetime.strptime(texte, _FORMAT).replace(tzinfo=timezone.utc).astimezone(self._fuseau)
        return Rdv(id_, lire(debut), lire(fin), type_consultation, patient_id)

    @staticmethod
    def _chevauchement(cx, debut: datetime, fin: datetime, sauf_id: int | None = None) -> bool:
        requete = "SELECT 1 FROM rdv WHERE debut < ? AND fin > ?"
        parametres: list = [_vers_db(fin), _vers_db(debut)]
        if sauf_id is not None:
            requete += " AND id != ?"
            parametres.append(sauf_id)
        return cx.execute(requete + " LIMIT 1", parametres).fetchone() is not None

    def rdv_entre(self, debut: datetime, fin: datetime) -> list[Rdv]:
        with self._verrou:
            lignes = self._cx.execute(
                "SELECT * FROM rdv WHERE debut < ? AND fin > ? ORDER BY debut",
                (_vers_db(fin), _vers_db(debut)),
            ).fetchall()
        return [self._rdv(ligne) for ligne in lignes]

    def ajouter(self, debut: datetime, fin: datetime, type_consultation: str, patient_id: int, patient=None) -> Rdv:
        with self._transaction() as cx:
            if self._chevauchement(cx, debut, fin):
                raise ConflitCreneau("Ce créneau est déjà pris.")
            curseur = cx.execute(
                "INSERT INTO rdv (debut, fin, type_consultation, patient_id) VALUES (?, ?, ?, ?)",
                (_vers_db(debut), _vers_db(fin), type_consultation, patient_id),
            )
            return self._rdv(
                (curseur.lastrowid, _vers_db(debut), _vers_db(fin), type_consultation, patient_id)
            )

    def deplacer(self, rdv_id: int, debut: datetime, fin: datetime) -> Rdv:
        with self._transaction() as cx:
            ligne = cx.execute("SELECT * FROM rdv WHERE id = ?", (rdv_id,)).fetchone()
            if ligne is None:
                raise RdvIntrouvable("Rendez-vous introuvable.")
            if self._chevauchement(cx, debut, fin, sauf_id=rdv_id):
                raise ConflitCreneau("Ce créneau est déjà pris.")
            cx.execute(
                "UPDATE rdv SET debut = ?, fin = ? WHERE id = ?",
                (_vers_db(debut), _vers_db(fin), rdv_id),
            )
            return self._rdv((rdv_id, _vers_db(debut), _vers_db(fin), ligne[3], ligne[4]))

    def supprimer(self, rdv_id: int) -> None:
        with self._transaction() as cx:
            if cx.execute("DELETE FROM rdv WHERE id = ?", (rdv_id,)).rowcount == 0:
                raise RdvIntrouvable("Rendez-vous introuvable.")

    def obtenir(self, rdv_id: int) -> Rdv | None:
        with self._verrou:
            ligne = self._cx.execute("SELECT * FROM rdv WHERE id = ?", (rdv_id,)).fetchone()
        return self._rdv(ligne) if ligne else None

    def rdv_des_patients(self, patient_ids: Sequence[int], a_partir_de: datetime) -> list[Rdv]:
        if not patient_ids:
            return []
        marques = ",".join("?" * len(patient_ids))
        with self._verrou:
            lignes = self._cx.execute(
                f"SELECT * FROM rdv WHERE patient_id IN ({marques}) AND debut >= ? ORDER BY debut",
                [*patient_ids, _vers_db(a_partir_de)],
            ).fetchall()
        return [self._rdv(ligne) for ligne in lignes]