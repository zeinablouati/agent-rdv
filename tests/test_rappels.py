"""Vague 2 : rappel la veille. Faux notificateur, aucun e-mail réel.
Aujourd'hui = vendredi 16 octobre 2026, 15h00 (horloge figée)."""

from datetime import date

from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous

from conftest import Horloge, paris
from test_notifications import FauxNotificateur


def construire(regles, notif):
    return ServiceRendezVous(regles, AgendaLocal(fuseau=regles.fuseau), RegistrePatients(), Horloge(), notificateur=notif)


def test_rappel_pour_le_jour_donne(regles):
    notif = FauxNotificateur()
    service = construire(regles, notif)
    service.reserver("standard", paris(2026, 10, 19, 9, 0), "Sara", "Ben Ali", "0612345678", "sara@example.com")
    notif.envoyes.clear()  # on ignore l'e-mail de confirmation

    nombre = service.envoyer_rappels(jour=date(2026, 10, 19))
    assert nombre == 1
    assert notif.envoyes[0]["a"] == "sara@example.com"
    assert "demain" in notif.envoyes[0]["sujet"].lower()


def test_pas_de_rappel_sans_email(regles):
    notif = FauxNotificateur()
    service = construire(regles, notif)
    service.reserver("standard", paris(2026, 10, 19, 9, 0), "Sara", "Ben Ali", "0612345678")  # pas d'e-mail
    assert service.envoyer_rappels(jour=date(2026, 10, 19)) == 0


def test_aucun_rdv_ce_jour_la(regles):
    notif = FauxNotificateur()
    service = construire(regles, notif)
    service.reserver("standard", paris(2026, 10, 19, 9, 0), "Sara", "Ben Ali", "0612345678", "sara@example.com")
    notif.envoyes.clear()
    assert service.envoyer_rappels(jour=date(2026, 10, 20)) == 0  # rien le mardi