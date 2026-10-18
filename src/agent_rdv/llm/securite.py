"""Garde-fou urgences : détection déterministe, indépendante du LLM.

C'est un filet de sécurité. Si le message évoque une urgence, l'agent coupe
tout (pas de prise de rendez-vous) et renvoie vers le 15 / 112. Le prompt du
LLM contient la même règle : ce code en est la version qui ne dépend de rien."""

from __future__ import annotations

import unicodedata

MESSAGE_URGENCE = (
    "⚠️ Ce que vous décrivez peut être une urgence médicale. "
    "Appelez immédiatement le 15 (SAMU) ou le 112. "
    "Ne prenez pas rendez-vous : une aide médicale urgente est nécessaire maintenant."
)

# Expressions (déjà sans accents, en minuscules) qui déclenchent la redirection.
SIGNAUX_URGENCE = (
    "mal a la poitrine",
    "douleur a la poitrine",
    "douleur thoracique",
    "oppression thoracique",
    "du mal a respirer",
    "j'etouffe",
    "je n'arrive plus a respirer",
    "malaise",
    "evanoui",
    "perte de connaissance",
    "inconscient",
    "ne repond plus",
    "avc",
    "infarctus",
    "crise cardiaque",
    "hemorragie",
    "saigne beaucoup",
    "saignement important",
    "convulsion",
    "overdose",
    "envie de mourir",
    "me suicider",
    "suicide",
)


def _normaliser(texte: str) -> str:
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return sans_accents.casefold()


def est_urgence(texte: str) -> bool:
    message = _normaliser(texte or "")
    return any(signal in message for signal in SIGNAUX_URGENCE)