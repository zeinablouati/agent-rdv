"""Amélioration : e-mail de confirmation à la réservation.
Un faux notificateur capture les envois — aucun e-mail réel."""

import pytest

from agent_rdv.agenda.erreurs import DonneesInvalides
from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous
from agent_rdv.notifications.messages import confirmation

from conftest import Horloge, paris


class FauxNotificateur:
    def __init__(self):
        self.envoyes = []

    def envoyer(self, destinataire, sujet, corps):
        self.envoyes.append({"a": destinataire, "sujet": sujet, "corps": corps})


@pytest.fixture
def notificateur():
    return FauxNotificateur()


@pytest.fixture
def service_mail(regles, notificateur):
    return ServiceRendezVous(
        regles, AgendaLocal(fuseau=regles.fuseau), RegistrePatients(), Horloge(), notificateur=notificateur
    )


def test_le_message_de_confirmation_contient_la_date_et_le_cabinet():
    sujet, corps = confirmation("Cabinet Dr Test", "Sara", paris(2026, 10, 19, 9, 0), "standard")
    assert "Cabinet Dr Test" in sujet
    assert "19/10/2026 à 09:00" in corps and "Sara" in corps


def test_reservation_avec_email_envoie_une_confirmation(service_mail, notificateur):
    service_mail.reserver("standard", paris(2026, 10, 19, 9, 0), "Sara", "Ben Ali", "0612345678", "sara@example.com")
    assert len(notificateur.envoyes) == 1
    assert notificateur.envoyes[0]["a"] == "sara@example.com"


def test_reservation_sans_email_n_envoie_rien(service_mail, notificateur):
    service_mail.reserver("standard", paris(2026, 10, 19, 9, 0), "Sara", "Ben Ali", "0612345678")
    assert notificateur.envoyes == []


def test_email_invalide_refuse(service_mail):
    with pytest.raises(DonneesInvalides):
        service_mail.reserver("standard", paris(2026, 10, 19, 9, 0), "Sara", "Ben Ali", "0612345678", "pasunemail")


def test_le_registre_stocke_et_met_a_jour_l_email():
    registre = RegistrePatients()
    p1 = registre.obtenir_ou_creer("Sara", "Ben Ali", "0612345678", "sara@example.com")
    assert p1.email == "sara@example.com"
    p2 = registre.obtenir_ou_creer("Sara", "Ben Ali", "0612345678", "nouveau@example.com")
    assert p2.id == p1.id and p2.email == "nouveau@example.com"
    assert registre.obtenir_par_id(p1.id).email == "nouveau@example.com"