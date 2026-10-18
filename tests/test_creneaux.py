"""Phase 1 : calcul des créneaux libres (une règle du cabinet = un test).
Aujourd'hui = vendredi 16 octobre 2026, 15h00 (horloge figée)."""

from datetime import date, datetime

from agent_rdv.agenda.creneaux import blocs_urgence, creneaux_libres, proposer

from conftest import paris

JEUDI = date(2026, 10, 22)
SAMEDI = date(2026, 10, 17)
DIMANCHE = date(2026, 10, 18)
LUNDI = date(2026, 10, 19)


def heures(creneaux):
    return [c.debut.strftime("%H:%M") for c in creneaux]


def test_samedi_et_dimanche_aucun_creneau(service):
    assert service.chercher_creneaux("standard", SAMEDI) == []
    assert service.chercher_creneaux("standard", DIMANCHE) == []


def test_jeudi_matin_commence_a_9h_et_finit_avant_le_creneau_urgence(service):
    h = heures(service.chercher_creneaux("standard", JEUDI, periode="matin"))
    assert h[0] == "09:00"
    assert h[-1] == "11:50"  # 12:10-12:30 est gardé pour les urgences
    assert "12:10" not in h


def test_jeudi_apres_midi_commence_a_14h_et_finit_avant_le_creneau_urgence(service):
    h = heures(service.chercher_creneaux("standard", JEUDI, periode="apres_midi"))
    assert h[0] == "14:00"
    assert h[-1] == "17:50"  # 18:10-18:30 est gardé pour les urgences


def test_aucun_creneau_pendant_la_pause_de_midi(service):
    h = heures(service.chercher_creneaux("standard", JEUDI))
    assert not any("12:30" <= x < "14:00" for x in h)


def test_les_creneaux_urgence_sont_deux_par_jour(regles):
    blocs = blocs_urgence(regles, JEUDI)
    assert len(blocs) == 2
    assert sorted(b[0].strftime("%H:%M") for b in blocs) == ["12:10", "18:10"]
    assert blocs_urgence(regles, SAMEDI) == []


def test_duree_selon_le_type_de_consultation(service):
    standard = service.chercher_creneaux("standard", JEUDI)[0]
    nouveau = service.chercher_creneaux("nouveau_patient", JEUDI)[0]
    suivi = service.chercher_creneaux("suivi", JEUDI)[0]
    assert (standard.fin - standard.debut).seconds == 20 * 60
    assert (nouveau.fin - nouveau.debut).seconds == 30 * 60
    assert (suivi.fin - suivi.debut).seconds == 15 * 60


def test_nouveau_patient_30_min_respecte_aussi_le_creneau_urgence(service):
    h = heures(service.chercher_creneaux("nouveau_patient", JEUDI, periode="matin"))
    assert h[-1] == "11:40"  # 11:40 + 30 min = 12:10, pile avant le bloc urgence


def test_delai_minimum_de_2_heures_le_jour_meme(service):
    # Il est 15h00 : le premier créneau possible aujourd'hui est 17h00.
    h = heures(service.chercher_creneaux("standard", date(2026, 10, 16)))
    assert h[0] == "17:00"
    assert h[-1] == "17:50"


def test_horizon_de_30_jours(service):
    assert service.chercher_creneaux("standard", date(2026, 11, 13)) != []  # J+28
    assert service.chercher_creneaux("standard", date(2026, 11, 16)) == []  # J+31


def test_un_rdv_existant_bloque_son_creneau_et_ceux_qui_le_chevauchent(service):
    service.reserver("standard", paris(2026, 10, 22, 10, 0), "Sara", "Ben Ali", "0612345678")
    h = heures(service.chercher_creneaux("standard", JEUDI, periode="matin"))
    # 10:00-10:20 pris : 9:50 (fin 10:10) et 10:10 chevauchent, 9:40 et 10:20 sont libres.
    assert "09:40" in h and "10:20" in h
    assert not {"09:50", "10:00", "10:10"} & set(h)


def test_periode_inconnue_refusee(service):
    import pytest

    with pytest.raises(ValueError):
        service.chercher_creneaux("standard", JEUDI, periode="soir")


def test_creneaux_tries_et_sans_doublon(service):
    creneaux = service.chercher_creneaux("standard", LUNDI, date(2026, 10, 23))
    debuts = [c.debut for c in creneaux]
    assert debuts == sorted(debuts)
    assert len(debuts) == len(set(debuts))
    assert all(c.debut.weekday() < 5 for c in creneaux)


def test_proposer_repartit_les_choix(service):
    tous = service.chercher_creneaux("standard", JEUDI, periode="apres_midi")
    choix = proposer(tous, 3)
    assert len(choix) == 3
    assert choix[0] == tous[0] and choix[-1] == tous[-1]
    assert proposer(tous[:2], 3) == tous[:2]
    assert proposer([], 3) == []