"""Registre des patients : l'agenda ne contient que des numéros, les identités
(prénom, nom, téléphone, e-mail) vivent ici, séparées."""

from __future__ import annotations

import re
import sqlite3
import threading
import unicodedata

from .erreurs import DonneesInvalides
from .modeles import Patient


def normaliser_nom(texte: str) -> str:
    """'  Ben-Ali ' et 'ben ali' donnent la même clé ; accents et casse ignorés."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return re.sub(r"[\s\-']+", " ", sans_accents).strip().casefold()


def normaliser_telephone(texte: str) -> str:
    """Retourne 10 chiffres (06 12 34 56 78, +33 6 12 34 56 78 et 0033... sont équivalents)."""
    chiffres = re.sub(r"\D", "", texte or "")
    if chiffres.startswith("0033"):
        chiffres = "0" + chiffres[4:]
    elif chiffres.startswith("33") and len(chiffres) == 11:
        chiffres = "0" + chiffres[2:]
    if len(chiffres) != 10 or not chiffres.startswith("0"):
        raise DonneesInvalides("Numéro de téléphone invalide : 10 chiffres attendus (ex. 06 12 34 56 78).")
    return chiffres


def valider_email(email: str | None) -> str | None:
    """Validation légère : None si vide, sinon vérifie la présence d'un @ et d'un domaine."""
    email = (email or "").strip()
    if not email:
        return None
    if "@" not in email or "." not in email.split("@")[-1]:
        raise DonneesInvalides("Adresse e-mail invalide.")
    return email


class RegistrePatients:
    def __init__(self, chemin: str = ":memory:"):
        self._verrou = threading.Lock()
        self._cx = sqlite3.connect(chemin, check_same_thread=False)
        self._cx.execute(
            """CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prenom TEXT NOT NULL,
                nom TEXT NOT NULL,
                prenom_cle TEXT NOT NULL,
                nom_cle TEXT NOT NULL,
                telephone TEXT NOT NULL,
                email TEXT,
                UNIQUE (prenom_cle, nom_cle, telephone)
            )"""
        )
        # Migration : ajoute la colonne email aux bases créées avant cette version.
        colonnes = [ligne[1] for ligne in self._cx.execute("PRAGMA table_info(patients)")]
        if "email" not in colonnes:
            self._cx.execute("ALTER TABLE patients ADD COLUMN email TEXT")
        self._cx.commit()

    @staticmethod
    def _patient(ligne) -> Patient:
        return Patient(id=ligne[0], prenom=ligne[1], nom=ligne[2], telephone=ligne[3], email=ligne[4])

    def obtenir_ou_creer(self, prenom: str, nom: str, telephone: str, email: str | None = None) -> Patient:
        prenom, nom = prenom.strip(), nom.strip()
        if not prenom or not nom:
            raise DonneesInvalides("Le prénom et le nom sont obligatoires.")
        tel = normaliser_telephone(telephone)
        mail = valider_email(email)
        cles = (normaliser_nom(prenom), normaliser_nom(nom), tel)
        with self._verrou:
            ligne = self._cx.execute(
                "SELECT id, prenom, nom, telephone, email FROM patients "
                "WHERE prenom_cle = ? AND nom_cle = ? AND telephone = ?",
                cles,
            ).fetchone()
            if ligne is None:
                curseur = self._cx.execute(
                    "INSERT INTO patients (prenom, nom, prenom_cle, nom_cle, telephone, email) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (prenom, nom, *cles, mail),
                )
                self._cx.commit()
                return Patient(curseur.lastrowid, prenom, nom, tel, mail)
            if mail and mail != ligne[4]:  # met à jour l'e-mail s'il a changé
                self._cx.execute("UPDATE patients SET email = ? WHERE id = ?", (mail, ligne[0]))
                self._cx.commit()
                ligne = (ligne[0], ligne[1], ligne[2], ligne[3], mail)
        return self._patient(ligne)

    def trouver(self, nom: str, telephone: str) -> list[Patient]:
        """Identifie par le téléphone (clé forte), puis vérifie qu'un mot du nom
        fourni correspond au prénom ou au nom. Tolérant au nom complet (« Prénom Nom »).
        Plusieurs résultats possibles : une famille peut partager un téléphone."""
        tel = normaliser_telephone(telephone)
        mots_demandes = set(normaliser_nom(nom).split())
        with self._verrou:
            lignes = self._cx.execute(
                "SELECT id, prenom, nom, telephone, email, prenom_cle, nom_cle "
                "FROM patients WHERE telephone = ?",
                (tel,),
            ).fetchall()
        resultat = []
        for ligne in lignes:
            mots_connus = set(ligne[5].split()) | set(ligne[6].split())
            if mots_demandes & mots_connus:
                resultat.append(self._patient(ligne[:5]))
        return resultat

    def obtenir_par_id(self, patient_id: int) -> Patient | None:
        with self._verrou:
            ligne = self._cx.execute(
                "SELECT id, prenom, nom, telephone, email FROM patients WHERE id = ?",
                (patient_id,),
            ).fetchone()
        return self._patient(ligne) if ligne else None