"""Test de connexion à Google Calendar (Phase 2).

  python scripts/test_google.py             -> crée un vrai événement de test, demain à 10h00,
                                               et le laisse (va le voir dans ton Google Agenda)
  python scripts/test_google.py --nettoyer  -> supprime les événements de test (patient 9999)

À lancer avec le .venv activé, depuis le dossier agent-rdv.
"""

import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv

from agent_rdv.agenda.google import AgendaGoogle
from agent_rdv.config import charger_regles

PATIENT_TEST = 9999

load_dotenv()
regles = charger_regles()

calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
fichier_cle = os.getenv("GOOGLE_CREDENTIALS_FILE", "secrets/google_credentials.json")

if not calendar_id:
    sys.exit("GOOGLE_CALENDAR_ID est absent du .env.")
if not Path(fichier_cle).exists():
    sys.exit(f"Clé introuvable : {fichier_cle} (dépose le JSON du compte de service ici).")

agenda = AgendaGoogle(calendar_id, fichier_cle, regles.fuseau)
maintenant = datetime.now(regles.fuseau)


def nettoyer():
    rdvs = agenda.rdv_des_patients([PATIENT_TEST], maintenant - timedelta(days=1))
    for rdv in rdvs:
        agenda.supprimer(rdv.id)
    print(f"Supprimé : {len(rdvs)} événement(s) de test.")


if "--nettoyer" in sys.argv:
    nettoyer()
    sys.exit(0)

print("Connexion à Google Calendar...")
demain = maintenant.date() + timedelta(days=1)
debut = datetime.combine(demain, time(10, 0), tzinfo=regles.fuseau)
fin = debut + timedelta(minutes=20)

rdv = agenda.ajouter(debut, fin, "standard", PATIENT_TEST)
print("  Créé    :", rdv.id, "|", rdv.titre, "|", rdv.debut.strftime("%A %d/%m à %H:%M"))

relu = agenda.obtenir(rdv.id)
print("  Relu    :", relu.titre, "|", relu.debut.strftime("%A %d/%m à %H:%M"))

print()
print("Va voir ton Google Agenda : tu dois voir «", rdv.titre, "» demain à 10h00.")
print("Quand tu l'as vu, nettoie avec : python scripts/test_google.py --nettoyer")