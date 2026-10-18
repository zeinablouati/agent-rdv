"""Affiche les demandes de rappel en attente (côté cabinet).

  python scripts/demandes.py          -> demandes non traitées
  python scripts/demandes.py --tout   -> toutes les demandes
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv

from agent_rdv.demandes import JournalDemandes

load_dotenv()

journal = JournalDemandes(os.getenv("DEMANDES_FICHIER", "data/demandes.sqlite"))
demandes = journal.lister(inclure_traitees="--tout" in sys.argv)

if not demandes:
    print("Aucune demande de rappel en attente.")
else:
    print(f"{len(demandes)} demande(s) de rappel :\n")
    for d in demandes:
        etat = "traitée" if d["traitee"] else "à rappeler"
        print(f"  #{d['id']} [{etat}] {d['horodatage']} — {d['nom']} ({d['telephone']})")
        if d["motif"]:
            print(f"        motif : {d['motif']}")