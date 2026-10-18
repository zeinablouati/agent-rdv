"""La boucle de l'agent : urgence -> LLM -> outils -> réponse.

Le client LLM est passé de l'extérieur (Groq en vrai, un faux client dans les
tests), ce qui rend la boucle testable sans Internet."""

from __future__ import annotations

import json
from typing import Any

from ..agenda.service import ServiceRendezVous
from ..config import Regles
from .outils import Dispatcheur, construire_schemas
from .prompt import systeme
from .securite import MESSAGE_URGENCE, est_urgence

REPLI = (
    "Je suis désolé, je n'ai pas réussi à traiter votre demande. "
    "Je transmets au secrétariat du cabinet, qui vous recontactera."
)


class AgentRDV:
    def __init__(self, service: ServiceRendezVous, regles: Regles, client: Any, modele: str,
                 max_tours: int = 6, trace=None, connaissances=None):
        self.service = service
        self.regles = regles
        self.client = client
        self.modele = modele
        self.max_tours = max_tours
        self.trace = trace  # fonction optionnelle (nom, arguments, resultat) pour le débogage
        self.connaissances = connaissances
        self.avec_infos = connaissances is not None
        self.schemas = construire_schemas(regles, avec_infos=self.avec_infos)
        self.dispatcheur = Dispatcheur(service, connaissances)

    def nouvelle_conversation(self) -> list[dict]:
        contenu = systeme(self.regles, self.service.maintenant(), avec_infos=self.avec_infos)
        return [{"role": "system", "content": contenu}]

    def repondre(self, historique: list[dict], message: str) -> str:
        # 1. Garde-fou urgences : on ne consulte même pas le LLM.
        if est_urgence(message):
            historique.append({"role": "user", "content": message})
            historique.append({"role": "assistant", "content": MESSAGE_URGENCE})
            return MESSAGE_URGENCE

        historique.append({"role": "user", "content": message})

        # 2. Boucle : le LLM répond, ou demande d'exécuter des outils, et on reboucle.
        for _ in range(self.max_tours):
            reponse = self.client.chat.completions.create(
                model=self.modele,
                messages=historique,
                tools=self.schemas,
                tool_choice="auto",
                temperature=0,
            )
            msg = reponse.choices[0].message
            appels = getattr(msg, "tool_calls", None)

            if not appels:
                contenu = msg.content or ""
                historique.append({"role": "assistant", "content": contenu})
                return contenu

            historique.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in appels
                ],
            })

            for tc in appels:
                try:
                    arguments = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                resultat = self.dispatcheur.executer(tc.function.name, arguments)
                if self.trace is not None:
                    self.trace(tc.function.name, arguments, resultat)
                historique.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(resultat, ensure_ascii=False),
                })
                historique.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(resultat, ensure_ascii=False),
                })

        # 3. Trop de tours sans réponse finale : on passe la main.
        historique.append({"role": "assistant", "content": REPLI})
        return REPLI