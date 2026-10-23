"""Oreille réelle : capture micro (sounddevice) + transcription locale (faster-whisper).

Détection de fin de parole simple par énergie : on enregistre tant que ça parle,
puis on coupe après un court silence. Rien ne part sur Internet : la transcription
tourne sur la machine."""

from __future__ import annotations

import numpy as np

from .base import Transcripteur


class TranscripteurWhisper(Transcripteur):
    def __init__(
        self,
        modele: str = "base",
        langue: str = "fr",
        frequence: int = 16000,
        seuil: float = 0.010,       # énergie au-dessus de laquelle on considère qu'il y a parole
        silence_fin: float = 2.0,   # secondes de silence qui terminent la prise de parole
        duree_max: float = 30.0,    # garde-fou : on ne dépasse jamais cette durée
    ):
        from faster_whisper import WhisperModel

        self.modele = WhisperModel(modele, device="cpu", compute_type="int8")
        self.langue = langue
        self.frequence = frequence
        self.seuil = seuil
        self.silence_fin = silence_fin
        self.duree_max = duree_max

    def _enregistrer(self) -> np.ndarray:
        import sounddevice as sd

        pas = 0.1  # blocs de 100 ms
        taille_bloc = int(self.frequence * pas)
        blocs_silence_fin = int(self.silence_fin / pas)
        blocs_max = int(self.duree_max / pas)

        print("🎤 Parlez…", flush=True)
        morceaux: list[np.ndarray] = []
        a_parle = False
        silences = 0
        with sd.InputStream(samplerate=self.frequence, channels=1, dtype="float32") as flux:
            for _ in range(blocs_max):
                donnees, _ = flux.read(taille_bloc)
                signal = donnees[:, 0]
                morceaux.append(signal)
                niveau = float(np.sqrt(np.mean(signal ** 2)))
                if niveau > self.seuil:
                    a_parle = True
                    silences = 0
                elif a_parle:
                    silences += 1
                    if silences >= blocs_silence_fin:
                        break
        if not morceaux:
            return np.zeros(1, dtype="float32")
        return np.concatenate(morceaux)

    def ecouter(self) -> str:
        audio = self._enregistrer()
        segments, _ = self.modele.transcribe(audio, language=self.langue, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
