"""Le canal vocal et ses deux contrats.

L'agent (le « cerveau ») prend du texte et rend du texte : il est indépendant du
canal. La voix n'ajoute qu'une oreille (Transcripteur) et une bouche
(Synthetiseur) autour de lui. On peut donc tout tester sans micro ni haut-parleur,
en injectant de faux composants."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod


def nettoyer_pour_voix(texte: str) -> str:
    """Retire la mise en forme Markdown : à l'oral, « **9h20** » doit se dire
    « 9h20 », pas « astérisque astérisque 9h20 »."""
    if not texte:
        return ""
    t = re.sub(r"`+", "", texte)                  # code
    t = re.sub(r"\*+", "", t)                     # gras / italique **…** *…*
    t = re.sub(r"__+", "", t)                     # gras souligné __…__
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)       # titres #
    t = re.sub(r"(?m)^\s*[-•·]\s+", "", t)        # puces de liste
    t = t.replace("\n", " ")                      # pas de sauts de ligne à l'oral
    return re.sub(r"\s{2,}", " ", t).strip()


def extraire_email_dicte(texte: str) -> str | None:
    """Reconstruit un email dicté à l'oral : « zeineb point louati arobase gmail
    point com » -> « zeineb.louati@gmail.com ». Ne renvoie une adresse que si un
    « arobase » / « @ » est présent, pour ne jamais se déclencher sur une phrase
    ordinaire contenant le mot « point »."""
    if not texte:
        return None
    t = texte.lower()
    if not re.search(r"@|\b(arobase|arrobase|arobas|at)\b", t):
        return None
    t = re.sub(r"\b(arobase|arrobase|arobas|at)\b", "@", t)
    t = re.sub(r"\b(point|dot)\b", ".", t)
    t = re.sub(r"\b(tiret|trait d'union)\b", "-", t)
    t = re.sub(r"\b(underscore|tiret bas|souligné)\b", "_", t)
    t = re.sub(r"\s*([@.\-_])\s*", r"\1", t)  # on colle ce qui entoure @ . - _
    correspondance = re.search(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", t)
    return correspondance.group(0) if correspondance else None


# Consigne de style ajoutée UNIQUEMENT au canal vocal : on parle, on ne rédige pas.
STYLE_VOIX = (
    "Tu réponds maintenant à l'oral, au téléphone. Parle comme un secrétariat "
    "accueillant : phrases courtes et naturelles, une idée à la fois. "
    "N'utilise aucune mise en forme (pas d'astérisques, de tirets ni de listes). "
    "Donne les horaires simplement (par exemple « neuf heures vingt »). "
    "Reformule brièvement ce que tu as compris et pose une seule question à la fois."
)


class Transcripteur(ABC):
    """L'oreille : écoute une prise de parole et rend le texte (vide si silence)."""

    @abstractmethod
    def ecouter(self) -> str: ...


class Synthetiseur(ABC):
    """La bouche : prononce un texte à voix haute."""

    @abstractmethod
    def dire(self, texte: str) -> None: ...


# Mots qui closent poliment l'appel, prononcés par l'appelant.
MOTS_FIN = ("au revoir", "bonne journée", "c'est tout merci", "merci au revoir")

ACCUEIL = "Bonjour, cabinet médical, je vous écoute."
SILENCE = "Je ne vous ai pas entendu. Je vous écoute."
AU_REVOIR = "Très bien, bonne journée, au revoir."


class CanalVocal:
    """Orchestre un appel : accueil, puis boucle écouter → penser → parler,
    jusqu'à un mot de fin ou trop de silences d'affilée."""

    def __init__(
        self,
        agent,
        transcripteur: Transcripteur,
        synthetiseur: Synthetiseur,
        mots_fin=MOTS_FIN,
        silences_max: int = 2,
        style_voix: str | None = STYLE_VOIX,
    ):
        self.agent = agent
        self.transcripteur = transcripteur
        self.synthetiseur = synthetiseur
        self.mots_fin = tuple(m.lower() for m in mots_fin)
        self.silences_max = silences_max
        self.historique = agent.nouvelle_conversation()
        if style_voix:  # on adapte le ton au canal vocal, sans toucher au cerveau
            self.historique.append({"role": "system", "content": style_voix})

    def _est_fin(self, texte: str) -> bool:
        return any(m in texte.lower() for m in self.mots_fin)

    def un_tour(self) -> dict:
        """Un échange. Rend {entree, reponse, silence, fin}."""
        entree = (self.transcripteur.ecouter() or "").strip()
        if not entree:
            return {"entree": "", "reponse": "", "silence": True, "fin": False}
        email = extraire_email_dicte(entree)
        if email:  # l'appelant dicte son adresse : on la reconstruit proprement
            entree = email
        reponse = self.agent.repondre(self.historique, entree)
        self.synthetiseur.dire(nettoyer_pour_voix(reponse))
        return {"entree": entree, "reponse": reponse, "silence": False, "fin": self._est_fin(entree)}

    def boucle(self, accueil: str = ACCUEIL) -> None:
        """Déroule l'appel du début à la fin (raccrochage)."""
        self.synthetiseur.dire(accueil)
        silences = 0
        while True:
            tour = self.un_tour()
            if tour["silence"]:
                silences += 1
                if silences >= self.silences_max:
                    self.synthetiseur.dire(AU_REVOIR)
                    return
                self.synthetiseur.dire(SILENCE)
                continue
            silences = 0  # une parole remet le compteur à zéro
            if tour["fin"]:
                self.synthetiseur.dire(AU_REVOIR)
                return
