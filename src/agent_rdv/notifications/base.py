"""Envoi d'e-mails, « branchable ».

- NotificateurConsole : affiche l'e-mail dans le terminal (par défaut, zéro config).
- NotificateurSMTP : envoie de vrais e-mails via un serveur SMTP (configuré dans .env).
construire_notificateur() choisit l'un ou l'autre selon la présence de SMTP_HOTE."""

from __future__ import annotations

import os
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.message import EmailMessage


class Notificateur(ABC):
    @abstractmethod
    def envoyer(self, destinataire: str, sujet: str, corps: str) -> None:
        ...


class NotificateurConsole(Notificateur):
    def envoyer(self, destinataire: str, sujet: str, corps: str) -> None:
        print(
            "\n----- E-mail (mode console) -----\n"
            f"À      : {destinataire}\n"
            f"Sujet  : {sujet}\n\n"
            f"{corps}\n"
            "---------------------------------\n"
        )


class NotificateurSMTP(Notificateur):
    def __init__(self, hote: str, port: int, utilisateur: str, mot_de_passe: str, expediteur: str):
        self.hote = hote
        self.port = port
        self.utilisateur = utilisateur
        self.mot_de_passe = mot_de_passe
        self.expediteur = expediteur

    def envoyer(self, destinataire: str, sujet: str, corps: str) -> None:
        message = EmailMessage()
        message["From"] = self.expediteur
        message["To"] = destinataire
        message["Subject"] = sujet
        message.set_content(corps)
        with smtplib.SMTP(self.hote, self.port) as serveur:
            serveur.starttls(context=ssl.create_default_context())
            serveur.login(self.utilisateur, self.mot_de_passe)
            serveur.send_message(message)


def construire_notificateur() -> Notificateur:
    hote = os.getenv("SMTP_HOTE")
    if not hote:
        return NotificateurConsole()
    utilisateur = os.getenv("SMTP_UTILISATEUR", "")
    return NotificateurSMTP(
        hote=hote,
        port=int(os.getenv("SMTP_PORT", "587")),
        utilisateur=utilisateur,
        mot_de_passe=os.getenv("SMTP_MOTDEPASSE", ""),
        expediteur=os.getenv("SMTP_EXPEDITEUR", utilisateur),
    )