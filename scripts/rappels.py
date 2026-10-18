"""Envoie les rappels des rendez-vous du lendemain (Phase rappels, vague 2).

  python scripts/rappels.py                 -> rappels pour demain
  python scripts/rappels.py 2026-10-19      -> rappels pour une date précise

À lancer une fois par jour (manuellement, ou via le Planificateur de tâches Windows).
En mode console (SMTP non configuré), les rappels s'affichent dans le terminal.
"""

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv

from agent_rdv.agenda.fabrique import construire_agenda
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.config import charger_regles
from agent_rdv.notifications.base import construire_notificateur

load_dotenv()

jour = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None

regles = charger_regles()
service = ServiceRendezVous(
    regles,
    construire_agenda(regles),
    RegistrePatients(os.getenv("REGISTRE_FICHIER", "data/patients.sqlite")),
    notificateur=construire_notificateur(),
)

nombre = service.envoyer_rappels(jour)
cible = jour.isoformat() if jour else "demain"
print(f"{nombre} rappel(s) envoyé(s) pour {cible}.")