"""Phase 1 : réserver, annuler, déplacer, avec toutes les règles et les garde-fous.
Aujourd'hui = vendredi 16 octobre 2026, 15h00 (horloge figée)."""

from datetime import date

import pytest

from agent_rdv.agenda.erreurs import (
    AnnulationTardive,
    ConflitCreneau,
    CreneauRefuse,
    DonneesInvalides,
    RdvIntrouvable,
    TypeInconnu,
)
from agent_rdv.agenda.registre import normaliser_telephone

from conftest import paris

SARA = ("Sara", "Ben Ali", "06 12 34 56 78")
LUNDI_9H = paris(2026, 10, 19, 9, 0)


def reserver_sara(service, debut=LUNDI_9H, type_consultation="standard"):
    return service.reserver(type_consultation, debut, *SARA)


# --- réserver ---

def test_reservation_simple(service):
    rdv = reserver_sara(service)
    assert rdv.debut == LUNDI_9H
    assert (rdv.fin - rdv.debut).seconds == 20 * 60
    assert rdv.type_consultation == "standard"


def test_le_creneau_reserve_n_est_plus_propose(service):
    reserver_sara(service)
    h = [c.debut.strftime("%H:%M") for c in service.chercher_creneaux("standard", date(2026, 10, 19))]
    assert "09:00" not in h


def test_double_reservation_refusee(service):
    reserver_sara(service)
    with pytest.raises(CreneauRefuse) as erreur:
        service.reserver("standard", LUNDI_9H, "Karim", "Haddad", "0698765432")
    assert erreur.value.code == "creneau_occupe"


def test_chevauchement_refuse_meme_decale(service):
    reserver_sara(service)
    with pytest.raises(CreneauRefuse) as erreur:
        service.reserver("standard", paris(2026, 10, 19, 9, 10), "Karim", "Haddad", "0698765432")
    assert erreur.value.code == "creneau_occupe"


def test_garde_fou_agenda_refuse_un_chevauchement_meme_sans_passer_par_le_service(service, agenda):
    reserver_sara(service)
    with pytest.raises(ConflitCreneau):
        agenda.ajouter(paris(2026, 10, 19, 9, 5), paris(2026, 10, 19, 9, 25), "standard", 99)


@pytest.mark.parametrize(
    "debut, code",
    [
        (paris(2026, 10, 17, 10, 0), "cabinet_ferme"),         # samedi
        (paris(2026, 10, 18, 10, 0), "cabinet_ferme"),         # dimanche
        (paris(2026, 10, 19, 8, 40), "hors_horaires"),         # avant l'ouverture
        (paris(2026, 10, 19, 13, 0), "hors_horaires"),         # pause de midi
        (paris(2026, 10, 19, 18, 20), "hors_horaires"),        # finirait après 18h30
        (paris(2026, 10, 19, 9, 3), "creneau_non_propose"),    # pas sur la grille de 10 min
        (paris(2026, 10, 16, 16, 30), "delai_trop_court"),     # dans 1 h 30
        (paris(2026, 11, 16, 10, 0), "horizon_depasse"),       # J+31
        (paris(2026, 10, 19, 12, 10), "creneau_reserve_urgence"),
        (paris(2026, 10, 19, 18, 10), "creneau_reserve_urgence"),
    ],
)
def test_reservations_refusees_avec_le_bon_motif(service, debut, code):
    with pytest.raises(CreneauRefuse) as erreur:
        reserver_sara(service, debut)
    assert erreur.value.code == code


def test_type_de_consultation_inconnu(service):
    with pytest.raises(TypeInconnu):
        service.reserver("teleconsultation", LUNDI_9H, *SARA)


def test_refus_ne_cree_pas_de_patient_ni_de_rdv(service):
    with pytest.raises(CreneauRefuse):
        reserver_sara(service, paris(2026, 10, 17, 10, 0))
    assert service.retrouver_rdv("Ben Ali", "0612345678") == []


def test_une_date_sans_fuseau_est_lue_en_heure_locale(service):
    from datetime import datetime

    rdv = service.reserver("standard", datetime(2026, 10, 19, 9, 0), *SARA)
    assert rdv.debut == LUNDI_9H


def test_donnees_patient_invalides(service):
    with pytest.raises(DonneesInvalides):
        service.reserver("standard", LUNDI_9H, "Sara", "Ben Ali", "123")
    with pytest.raises(DonneesInvalides):
        service.reserver("standard", LUNDI_9H, "", "Ben Ali", "0612345678")


# --- minimisation des données ---

def test_le_rdv_ne_contient_aucune_donnee_identifiante(service):
    rdv = reserver_sara(service)
    assert rdv.titre == f"Consultation – Patient {rdv.patient_id:04d}"
    for champ in ("nom", "prenom", "telephone", "motif"):
        assert not hasattr(rdv, champ)
    assert "Sara" not in rdv.titre and "Ali" not in rdv.titre


# --- identité ---

@pytest.mark.parametrize(
    "saisie",
    ["06 12 34 56 78", "06.12.34.56.78", "+33 6 12 34 56 78", "0033612345678", "0612345678"],
)
def test_telephone_normalise(saisie):
    assert normaliser_telephone(saisie) == "0612345678"


def test_retrouver_ignore_casse_accents_et_tirets(service):
    reserver_sara(service)
    assert len(service.retrouver_rdv("BEN-ALI", "+33612345678")) == 1
    assert len(service.retrouver_rdv("ben ali", "0612345678")) == 1


def test_retrouver_avec_un_mauvais_telephone_ne_donne_rien(service):
    reserver_sara(service)
    assert service.retrouver_rdv("Ben Ali", "0600000000") == []


# --- annuler ---

def test_annulation_libere_le_creneau(service):
    rdv = reserver_sara(service)
    service.annuler(rdv.id, "Ben Ali", "0612345678")
    assert service.retrouver_rdv("Ben Ali", "0612345678") == []
    h = [c.debut.strftime("%H:%M") for c in service.chercher_creneaux("standard", date(2026, 10, 19))]
    assert "09:00" in h


def test_annulation_refusee_a_moins_de_24h(service, horloge):
    rdv = reserver_sara(service)
    horloge.maintenant = paris(2026, 10, 18, 10, 0)  # dimanche 10h : RDV dans 23 h
    with pytest.raises(AnnulationTardive):
        service.annuler(rdv.id, "Ben Ali", "0612345678")
    assert len(service.retrouver_rdv("Ben Ali", "0612345678")) == 1  # rien n'a changé


def test_annulation_acceptee_a_exactement_24h(service, horloge):
    rdv = reserver_sara(service)
    horloge.maintenant = paris(2026, 10, 18, 9, 0)  # RDV dans 24 h pile
    service.annuler(rdv.id, "Ben Ali", "0612345678")


def test_annulation_refusee_si_ce_n_est_pas_son_rdv(service):
    rdv = reserver_sara(service)
    with pytest.raises(RdvIntrouvable):
        service.annuler(rdv.id, "Haddad", "0698765432")
    with pytest.raises(RdvIntrouvable):
        service.annuler(rdv.id, "Ben Ali", "0600000000")
    assert len(service.retrouver_rdv("Ben Ali", "0612345678")) == 1


def test_annulation_d_un_rdv_inexistant(service):
    with pytest.raises(RdvIntrouvable):
        service.annuler(999, "Ben Ali", "0612345678")


# --- déplacer ---

def test_deplacement_libere_l_ancien_creneau_et_occupe_le_nouveau(service):
    rdv = reserver_sara(service)
    nouveau = service.deplacer(rdv.id, paris(2026, 10, 21, 11, 0), "Ben Ali", "0612345678")
    assert nouveau.id == rdv.id and nouveau.debut == paris(2026, 10, 21, 11, 0)
    rdvs = service.retrouver_rdv("Ben Ali", "0612345678")
    assert len(rdvs) == 1 and rdvs[0].debut == paris(2026, 10, 21, 11, 0)
    h = [c.debut.strftime("%H:%M") for c in service.chercher_creneaux("standard", date(2026, 10, 19))]
    assert "09:00" in h


def test_deplacement_peut_chevaucher_son_propre_ancien_creneau(service):
    rdv = reserver_sara(service)
    nouveau = service.deplacer(rdv.id, paris(2026, 10, 19, 9, 10), "Ben Ali", "0612345678")
    assert nouveau.debut == paris(2026, 10, 19, 9, 10)


def test_deplacement_vers_un_creneau_pris_laisse_l_ancien_intact(service):
    rdv = reserver_sara(service)
    service.reserver("standard", paris(2026, 10, 21, 11, 0), "Karim", "Haddad", "0698765432")
    with pytest.raises(CreneauRefuse) as erreur:
        service.deplacer(rdv.id, paris(2026, 10, 21, 11, 0), "Ben Ali", "0612345678")
    assert erreur.value.code == "creneau_occupe"
    assert service.retrouver_rdv("Ben Ali", "0612345678")[0].debut == LUNDI_9H


def test_deplacement_vers_un_creneau_interdit(service):
    rdv = reserver_sara(service)
    with pytest.raises(CreneauRefuse) as erreur:
        service.deplacer(rdv.id, paris(2026, 10, 24, 10, 0), "Ben Ali", "0612345678")  # samedi
    assert erreur.value.code == "cabinet_ferme"


def test_deplacement_refuse_a_moins_de_24h(service, horloge):
    rdv = reserver_sara(service)
    horloge.maintenant = paris(2026, 10, 18, 12, 0)
    with pytest.raises(AnnulationTardive):
        service.deplacer(rdv.id, paris(2026, 10, 21, 11, 0), "Ben Ali", "0612345678")


def test_deplacement_conserve_la_duree_du_type(service):
    rdv = reserver_sara(service, type_consultation="nouveau_patient")
    nouveau = service.deplacer(rdv.id, paris(2026, 10, 21, 10, 0), "Ben Ali", "0612345678")
    assert (nouveau.fin - nouveau.debut).seconds == 30 * 60


# --- changement d'heure ---

def test_changement_d_heure_d_automne_reste_coherent(service):
    # Le 25 octobre 2026, passage à l'heure d'hiver. Un RDV le lundi 26 doit rester à 9h locales.
    rdv = service.reserver("standard", paris(2026, 10, 26, 9, 0), *SARA)
    assert rdv.debut.hour == 9
    assert service.retrouver_rdv("Ben Ali", "0612345678")[0].debut.hour == 9