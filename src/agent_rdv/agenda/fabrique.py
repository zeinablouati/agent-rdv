"""Fabrique d'agenda : choisit l'agenda local ou Google selon la variable
d'environnement AGENDA (.env). Le reste du code ne sait pas lequel est utilisé."""

from __future__ import annotations

import os

from ..config import Regles
from .base import Agenda
from .local import AgendaLocal


def construire_agenda(regles: Regles) -> Agenda:
    choix = os.getenv("AGENDA", "local").strip().lower()

    if choix == "google":
        from .google import AgendaGoogle  # import tardif : n'exige Google que si on l'utilise

        calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        if not calendar_id:
            raise RuntimeError("AGENDA=google mais GOOGLE_CALENDAR_ID est absent du .env.")
        fichier_cle = os.getenv("GOOGLE_CREDENTIALS_FILE", "secrets/google_credentials.json")
        return AgendaGoogle(calendar_id, fichier_cle, regles.fuseau)

    if choix == "local":
        chemin = os.getenv("AGENDA_LOCAL_FICHIER", ":memory:")
        return AgendaLocal(chemin, fuseau=regles.fuseau)

    raise RuntimeError(f"Valeur AGENDA inconnue : '{choix}' (attendu : local ou google).")