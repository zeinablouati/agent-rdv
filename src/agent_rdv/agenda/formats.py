"""Mise en forme d'un événement d'agenda.

Choix du cabinet : l'événement porte le nom du patient et le type de rendez-vous,
mais AUCUN motif médical (donnée de santé). Le téléphone va dans la description."""

from __future__ import annotations


def resume_evenement(prenom: str, nom: str, type_consultation: str) -> str:
    """Titre de l'événement : « Prénom Nom – type »."""
    return f"{prenom} {nom} – {type_consultation}"


def description_evenement(telephone: str, type_consultation: str) -> str:
    return (
        f"Téléphone : {telephone}\n"
        f"Type : {type_consultation}\n"
        "Rendez-vous pris via l'assistant en ligne."
    )