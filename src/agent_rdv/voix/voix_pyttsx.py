"""Bouche réelle : synthèse vocale hors-ligne avec pyttsx3 (voix Windows SAPI).

Sous Windows, réutiliser le même moteur dans une boucle le rend muet après la
première phrase. On recrée donc un moteur neuf à chaque prise de parole ; la voix
française, elle, n'est cherchée qu'une fois."""

from __future__ import annotations

from .base import Synthetiseur


class SynthetiseurPyttsx3(Synthetiseur):
    def __init__(self, vitesse: int = 175, prefere_francais: bool = True):
        self.vitesse = vitesse
        self._voix_id = self._trouver_voix_francaise() if prefere_francais else None

    @staticmethod
    def _trouver_voix_francaise() -> str | None:
        import pyttsx3

        moteur = pyttsx3.init()
        try:
            for voix in moteur.getProperty("voices"):
                signature = f"{voix.id} {getattr(voix, 'name', '')}".lower()
                langues = " ".join(str(l) for l in getattr(voix, "languages", [])).lower()
                if "fr" in signature or "french" in signature or "fr" in langues:
                    return voix.id
        finally:
            moteur.stop()
        return None

    def dire(self, texte: str) -> None:
        if not texte:
            return
        print(f"🔊 {texte}")
        import pyttsx3

        moteur = pyttsx3.init()  # neuf à chaque phrase : évite le « muet après la 1re »
        moteur.setProperty("rate", self.vitesse)
        if self._voix_id:
            moteur.setProperty("voice", self._voix_id)
        moteur.say(texte)
        moteur.runAndWait()
        moteur.stop()
