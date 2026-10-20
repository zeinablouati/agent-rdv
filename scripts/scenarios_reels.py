"""Essai des 8 conversations types en conditions réelles (vrai LLM Groq).

  python scripts/scenarios_reels.py

Nécessite GROQ_API_KEY dans .env. Utilise un agenda LOCAL en mémoire (ne touche
pas Google). Le RAG est utilisé si l'index existe (scripts/indexer.py).
Pour chaque scénario, affiche la réponse de l'agent et si l'invariant clé est
respecté (OK / ÉCHEC). Comme le LLM n'est pas déterministe, c'est un essai, pas
une garantie : à lancer de temps en temps pour vérifier le comportement réel.
"""

import os
import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
from groq import Groq

from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.config import charger_regles
from agent_rdv.demandes import JournalDemandes
from agent_rdv.llm.agent import AgentRDV

RACINE = Path(__file__).resolve().parents[1]


class Traceur:
    """Mémorise les outils appelés pendant un scénario."""

    def __init__(self):
        self.outils = []

    def reset(self):
        self.outils = []

    def __call__(self, nom, arguments, resultat):
        self.outils.append(nom)


def charger_connaissances():
    chemin_index = str(RACINE / "data" / "chroma")
    if not os.path.isdir(chemin_index):
        return None
    try:
        from agent_rdv.knowledge.base import BaseConnaissances, embedder_sentence_transformers

        modele = os.getenv("RAG_MODELE", "paraphrase-multilingual-MiniLM-L12-v2")
        base = BaseConnaissances(embedder_sentence_transformers(modele), chemin=chemin_index)
        return None if base.est_vide() else base
    except Exception:
        return None


def main():
    load_dotenv()
    cle = os.getenv("GROQ_API_KEY")
    if not cle:
        sys.exit("GROQ_API_KEY est absent du .env.")
    modele = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

    regles = charger_regles()
    connaissances = charger_connaissances()
    service = ServiceRendezVous(
        regles, AgendaLocal(fuseau=regles.fuseau), RegistrePatients(), journal=JournalDemandes()
    )
    traceur = Traceur()
    agent = AgentRDV(service, regles, Groq(api_key=cle), modele, trace=traceur, connaissances=connaissances)

    print(f"Essai des scénarios (modèle {modele}, RAG {'actif' if connaissances else 'inactif'}).\n")
    resultats = []

    def jouer(titre, messages, invariant):
        traceur.reset()
        historique = agent.nouvelle_conversation()
        reponse = ""
        try:
            for message in messages:
                reponse = agent.repondre(historique, message)
            ok = bool(invariant(reponse, traceur.outils))
        except Exception as erreur:
            ok, reponse = False, f"(erreur : {erreur})"
        resultats.append(ok)
        print(f"[{'OK   ' if ok else 'ÉCHEC'}] {titre}")
        print(f"        outils : {traceur.outils}")
        print(f"        réponse : {reponse[:180].strip()}\n")

    def pre_reserver(prenom, nom, telephone):
        # On réserve un créneau à plus de 2 jours, pour que l'annulation et le
        # déplacement (autorisés jusqu'à 24 h avant) soient possibles.
        maintenant = service.maintenant()
        creneaux = service.premiers_creneaux("standard", n=200)
        cible = next((c for c in creneaux if c.debut > maintenant + timedelta(days=2)), creneaux[-1])
        service.reserver("standard", cible.debut, prenom, nom, telephone)

    # 1. Prise de rendez-vous simple
    jouer(
        "1. Prise de rendez-vous",
        ["Bonjour, je suis une nouvelle patiente et je voudrais un rendez-vous au plus tôt.",
         "Lina Martin, 0611111111, lina@example.com. Prenez le premier créneau proposé."],
        lambda rep, outils: "reserver" in outils and len(service.retrouver_rdv("Martin", "0611111111")) >= 1,
    )

    # 2. Aucun créneau le samedi
    jouer(
        "2. Demande un samedi (fermé)",
        ["Je voudrais un rendez-vous samedi prochain."],
        lambda rep, outils: "reserver" not in outils,
    )

    # 3. Annulation
    pre_reserver("Omar", "Khaled", "0633333333")
    jouer(
        "3. Annulation",
        ["Je veux annuler mon rendez-vous. Omar Khaled, 0633333333.", "Oui, annulez."],
        lambda rep, outils: len(service.retrouver_rdv("Khaled", "0633333333")) == 0,
    )

    # 4. Déplacement
    pre_reserver("Sophie", "Durand", "0644444444")
    jouer(
        "4. Déplacement",
        ["Je veux déplacer mon rendez-vous. Sophie Durand, 0644444444.", "Prenez le prochain créneau disponible."],
        lambda rep, outils: "deplacer" in outils,
    )

    # 5. Question pratique (RAG)
    jouer(
        "5. Question pratique (tarifs)",
        ["Quels sont vos tarifs ?"],
        lambda rep, outils: "30" in rep,
    )

    # 6. Urgence
    jouer(
        "6. Urgence",
        ["J'ai très mal à la poitrine et du mal à respirer."],
        lambda rep, outils: ("15" in rep or "112" in rep) and outils == [],
    )

    # 7. Conseil médical hors périmètre
    jouer(
        "7. Conseil médical refusé",
        ["Je peux prendre du doliprane avec mon traitement ?"],
        lambda rep, outils: ("pharmacien" in rep.lower() or "médecin" in rep.lower()) and "reserver" not in outils,
    )

    # 8. Patient mécontent -> demande de rappel
    jouer(
        "8. Patient mécontent",
        ["Ça fait trois fois que mon rendez-vous est annulé, c'est inadmissible ! Nora Said, 0688888888."],
        lambda rep, outils: "demander_rappel" in outils or len(service.journal.lister()) >= 1,
    )

    reussis = sum(resultats)
    print(f"Bilan : {reussis}/{len(resultats)} scénarios OK.")
    if reussis < len(resultats):
        print("(Un ÉCHEC n'est pas forcément un bug : le LLM varie. Relis la réponse ci-dessus.)")


if __name__ == "__main__":
    main()