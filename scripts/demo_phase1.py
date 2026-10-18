"""Démonstration de la Phase 1 dans le terminal : python scripts/demo_phase1.py
Utilise un agenda en mémoire et des patients fictifs."""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_rdv.agenda.creneaux import proposer
from agent_rdv.agenda.erreurs import ErreurAgenda
from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.config import charger_regles

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def joli(dt):
    return f"{JOURS[dt.weekday()]} {dt:%d/%m} à {dt:%H:%M}"


def titre(texte):
    print(f"\n=== {texte} ===")


regles = charger_regles()
service = ServiceRendezVous(regles, AgendaLocal(fuseau=regles.fuseau), RegistrePatients())
aujourdhui = service.maintenant().date()

jeudi = aujourdhui + timedelta(days=3)
while jeudi.weekday() != 3:
    jeudi += timedelta(days=1)

titre(f"Aujourd'hui : {joli(service.maintenant())}")

titre(f"Créneaux proposés le jeudi {jeudi:%d/%m}, après-midi")
choix = proposer(service.chercher_creneaux("standard", jeudi, periode="apres_midi"), 3)
for c in choix:
    print("  -", joli(c.debut))

titre("Réservation de Sara Ben Ali sur le premier choix")
rdv = service.reserver("standard", choix[0].debut, "Sara", "Ben Ali", "06 12 34 56 78")
print("  RDV n°", rdv.id, ":", joli(rdv.debut), "->", joli(rdv.fin))
print("  Titre dans l'agenda :", rdv.titre)

titre("Tentatives interdites")
samedi = jeudi + timedelta(days=2)
for texte, debut in [
    ("Même créneau (déjà pris)", choix[0].debut),
    ("Samedi (cabinet fermé)", choix[0].debut.replace(year=samedi.year, month=samedi.month, day=samedi.day)),
    ("Pendant la pause de midi", choix[0].debut.replace(hour=13, minute=0)),
]:
    try:
        service.reserver("standard", debut, "Karim", "Haddad", "0698765432")
    except ErreurAgenda as erreur:
        print(f"  {texte} -> REFUSÉ [{erreur.code}] {erreur.message}")

titre("Déplacement du rendez-vous au lendemain à 11h00")
lendemain = choix[0].debut.replace(hour=11, minute=0) + timedelta(days=1)
nouveau = service.deplacer(rdv.id, lendemain, "ben-ali", "+33612345678")
print("  Nouveau créneau :", joli(nouveau.debut))

titre("Annulation")
service.annuler(rdv.id, "Ben Ali", "0612345678")
print("  Rendez-vous restants pour Sara :", len(service.retrouver_rdv("Ben Ali", "0612345678")))