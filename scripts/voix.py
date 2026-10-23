"""Parler à l'agent au micro (canal vocal, V2).

  python scripts/voix.py

Nécessite : GROQ_API_KEY dans .env, et les paquets faster-whisper, sounddevice,
pyttsx3 installés. Réglages par variables d'environnement :
  VOIX_MODELE   modèle whisper (base par défaut ; small = plus précis mais plus lent)
Parle après l'accueil. Dis « au revoir » pour raccrocher, ou Ctrl+C pour couper.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_rdv.assemblage import construire_agent_reel
from agent_rdv.voix.base import CanalVocal
from agent_rdv.voix.micro_whisper import TranscripteurWhisper
from agent_rdv.voix.voix_pyttsx import SynthetiseurPyttsx3


def main() -> None:
    try:
        agent = construire_agent_reel()
    except RuntimeError as erreur:
        sys.exit(str(erreur))

    modele = os.getenv("VOIX_MODELE", "base")
    seuil = float(os.getenv("VOIX_SEUIL", "0.010"))       # baisse-le si elle te coupe (ex. 0.006)
    silence = float(os.getenv("VOIX_SILENCE", "2.0"))     # augmente-le si elle te coupe (ex. 2.5)
    print(f"Chargement du modèle vocal « {modele} » (1re fois : téléchargement)…")
    oreille = TranscripteurWhisper(modele=modele, seuil=seuil, silence_fin=silence)
    bouche = SynthetiseurPyttsx3()

    print(f"Agent vocal prêt (agenda {type(agent.service.agenda).__name__}).")
    print("Parle après l'accueil. Dis « au revoir » pour raccrocher.\n")

    canal = CanalVocal(agent, oreille, bouche)
    try:
        canal.boucle()
    except KeyboardInterrupt:
        print("\nAppel interrompu.")


if __name__ == "__main__":
    main()
