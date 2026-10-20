"""Crée (ou met à jour) un compte médecin pour l'espace admin.

  python scripts/creer_medecin.py <identifiant>

Le mot de passe est demandé de façon masquée (il n'apparaît pas à l'écran
ni dans l'historique du terminal).
"""

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv

from agent_rdv.admin.comptes import Comptes

load_dotenv()

if len(sys.argv) < 2:
    sys.exit("Usage : python scripts/creer_medecin.py <identifiant>")

identifiant = sys.argv[1]
mot_de_passe = getpass.getpass("Mot de passe : ")
confirmation = getpass.getpass("Confirmer le mot de passe : ")

if mot_de_passe != confirmation:
    sys.exit("Les deux mots de passe ne correspondent pas.")
if len(mot_de_passe) < 6:
    sys.exit("Le mot de passe doit faire au moins 6 caractères.")

comptes = Comptes(os.getenv("COMPTES_FICHIER", "data/medecins.sqlite"))
comptes.creer(identifiant, mot_de_passe)
print(f"Compte médecin « {identifiant.strip().lower()} » créé ou mis à jour.")