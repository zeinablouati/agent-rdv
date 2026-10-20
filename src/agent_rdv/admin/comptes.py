"""Comptes médecins (espace admin) : identifiants et mots de passe.

Les mots de passe ne sont JAMAIS stockés en clair : on garde seulement un
« hachage » (empreinte) avec un sel aléatoire, via pbkdf2 (bibliothèque standard).
On ne peut pas retrouver le mot de passe à partir du hachage ; on peut seulement
vérifier qu'un mot de passe saisi correspond."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading

ITERATIONS = 200_000


def hacher(mot_de_passe: str, sel: bytes | None = None) -> str:
    """Retourne « sel$empreinte » (hexadécimal). Un sel aléatoire par mot de passe."""
    sel = sel or secrets.token_bytes(16)
    empreinte = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, ITERATIONS)
    return f"{sel.hex()}${empreinte.hex()}"


def verifier(mot_de_passe: str, stocke: str) -> bool:
    """Vrai si le mot de passe correspond au hachage stocké."""
    if not stocke or "$" not in stocke:
        return False
    sel_hex, _ = stocke.split("$", 1)
    try:
        sel = bytes.fromhex(sel_hex)
    except ValueError:
        return False
    return secrets.compare_digest(hacher(mot_de_passe, sel), stocke)


class Comptes:
    def __init__(self, chemin: str = ":memory:"):
        self._verrou = threading.Lock()
        self._cx = sqlite3.connect(chemin, check_same_thread=False)
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS medecins ("
            "utilisateur TEXT PRIMARY KEY, mot_de_passe TEXT NOT NULL)"
        )
        self._cx.commit()

    @staticmethod
    def _normaliser(utilisateur: str) -> str:
        return (utilisateur or "").strip().lower()

    def creer(self, utilisateur: str, mot_de_passe: str) -> None:
        """Crée (ou met à jour) un compte médecin."""
        utilisateur = self._normaliser(utilisateur)
        if not utilisateur or not mot_de_passe:
            raise ValueError("Identifiant et mot de passe sont obligatoires.")
        with self._verrou:
            self._cx.execute(
                "INSERT OR REPLACE INTO medecins (utilisateur, mot_de_passe) VALUES (?, ?)",
                (utilisateur, hacher(mot_de_passe)),
            )
            self._cx.commit()

    def verifier_identifiants(self, utilisateur: str, mot_de_passe: str) -> bool:
        with self._verrou:
            ligne = self._cx.execute(
                "SELECT mot_de_passe FROM medecins WHERE utilisateur = ?",
                (self._normaliser(utilisateur),),
            ).fetchone()
        return bool(ligne) and verifier(mot_de_passe, ligne[0])

    def existe_au_moins_un(self) -> bool:
        with self._verrou:
            return self._cx.execute("SELECT 1 FROM medecins LIMIT 1").fetchone() is not None