"""Contenu des e-mails (confirmation et rappel)."""

from __future__ import annotations

from datetime import datetime

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _joli(dt: datetime) -> str:
    return f"{JOURS[dt.weekday()]} {dt:%d/%m/%Y} à {dt:%H:%M}"


def confirmation(cabinet: str, prenom: str, debut: datetime, type_consultation: str) -> tuple[str, str]:
    sujet = f"Confirmation de votre rendez-vous — {cabinet}"
    corps = (
        f"Bonjour {prenom},\n\n"
        f"Votre rendez-vous ({type_consultation}) est confirmé le {_joli(debut)} au {cabinet}.\n\n"
        "En cas d'empêchement, merci de prévenir au moins 24 h à l'avance.\n\n"
        f"À bientôt,\n{cabinet}"
    )
    return sujet, corps


def rappel(cabinet: str, prenom: str, debut: datetime, type_consultation: str) -> tuple[str, str]:
    sujet = f"Rappel : votre rendez-vous demain — {cabinet}"
    corps = (
        f"Bonjour {prenom},\n\n"
        f"Nous vous rappelons votre rendez-vous ({type_consultation}) demain, {_joli(debut)}, au {cabinet}.\n\n"
        f"À demain,\n{cabinet}"
    )
    return sujet, corps