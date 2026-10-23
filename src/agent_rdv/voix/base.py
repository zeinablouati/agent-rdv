"""Le canal vocal et ses deux contrats.

L'agent (le « cerveau ») prend du texte et rend du texte : il est indépendant du
canal. La voix n'ajoute qu'une oreille (Transcripteur) et une bouche
(Synthetiseur) autour de lui. On peut donc tout tester sans micro ni haut-parleur,
en injectant de faux composants."""

from __future__ import annotations

from abc import ABC, abstractmethod


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
    ):
        self.agent = agent
        self.transcripteur = transcripteur
        self.synthetiseur = synthetiseur
        self.mots_fin = tuple(m.lower() for m in mots_fin)
        self.silences_max = silences_max
        self.historique = agent.nouvelle_conversation()

    def _est_fin(self, texte: str) -> bool:
        return any(m in texte.lower() for m in self.mots_fin)

    def un_tour(self) -> dict:
        """Un échange. Rend {entree, reponse, silence, fin}."""
        entree = (self.transcripteur.ecouter() or "").strip()
        if not entree:
            return {"entree": "", "reponse": "", "silence": True, "fin": False}
        reponse = self.agent.repondre(self.historique, entree)
        self.synthetiseur.dire(reponse)
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
