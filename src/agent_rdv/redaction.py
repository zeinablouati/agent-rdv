"""Assistant de rédaction médicale : il met en forme les observations du médecin
en une synthèse de consultation claire et structurée.

LIGNE ROUGE — l'IA assiste, elle ne soigne pas :
- elle n'invente AUCUNE information absente des observations ;
- elle ne pose JAMAIS de diagnostic de sa propre initiative ; une hypothèse du
  médecin est reformulée comme une hypothèse, pas comme une certitude ;
- elle ne rédige PAS l'ordonnance (prescription = acte réservé au médecin) ;
- son résultat est un BROUILLON, sans valeur tant que le médecin ne l'a pas validé.

Le client LLM est injecté (Groq en vrai, un faux client dans les tests)."""

from __future__ import annotations

from typing import Any

from .agenda.erreurs import DonneesInvalides

SYSTEME = """Tu es l'assistant de rédaction d'un cabinet de médecine générale.
Ton rôle est celui d'un secrétariat augmenté : tu mets en forme, tu n'exerces pas la médecine.

À partir des observations saisies par le médecin, rédige une SYNTHÈSE de consultation
claire, concise et professionnelle, en français, prête à être relue.

Règles impératives :
- N'ajoute AUCUNE information qui ne figure pas dans les observations. N'invente ni
  symptôme, ni antécédent, ni résultat, ni chiffre.
- Ne pose jamais de diagnostic de ta propre initiative. Si le médecin mentionne une
  hypothèse, reformule-la comme une hypothèse (« évoque », « compatible avec »), jamais
  comme une certitude.
- Ne rédige pas d'ordonnance et ne propose pas de traitement ou de posologie.
- Si une information semble manquer, ne la devine pas : reste fidèle au texte fourni.
- Style sobre : phrases courtes, vocabulaire médical usuel, pas de formule de politesse.

Réponds uniquement par le texte de la synthèse, sans titre ni commentaire."""


class RedacteurMedical:
    def __init__(self, client: Any, modele: str):
        self.client = client
        self.modele = modele

    def rediger_synthese(self, observations: str, type_consultation: str | None = None) -> str:
        """Rend un brouillon de synthèse à partir des observations du médecin."""
        observations = (observations or "").strip()
        if not observations:
            raise DonneesInvalides("Aucune observation à reformuler.")

        contexte = f"Type de consultation : {type_consultation}.\n" if type_consultation else ""
        messages = [
            {"role": "system", "content": SYSTEME},
            {"role": "user", "content": f"{contexte}Observations du médecin :\n{observations}"},
        ]
        reponse = self.client.chat.completions.create(
            model=self.modele,
            messages=messages,
            temperature=0.2,  # fidèle au texte, peu de créativité
        )
        texte = (reponse.choices[0].message.content or "").strip()
        if not texte:
            raise DonneesInvalides("La rédaction n'a rien renvoyé.")
        return texte
