"""Finitions, vague 1 : « au plus tôt » part de maintenant.
Aujourd'hui = vendredi 16 octobre 2026, 15h00 (horloge figée)."""

from agent_rdv.llm.outils import Dispatcheur, construire_schemas


def test_premiers_creneaux_partent_d_aujourd_hui(service):
    creneaux = service.premiers_creneaux("standard")
    # Il est 15h00, délai minimum 2 h : le premier créneau est aujourd'hui à 17h00.
    assert creneaux[0].debut.strftime("%d/%m %H:%M") == "16/10 17:00"


def test_premiers_creneaux_sont_tries_et_limites(service):
    creneaux = service.premiers_creneaux("standard", n=3)
    assert len(creneaux) == 3
    debuts = [c.debut for c in creneaux]
    assert debuts == sorted(debuts)


def test_dispatcheur_premiers_creneaux(service):
    res = Dispatcheur(service).executer("premiers_creneaux", {"type_consultation": "standard"})
    assert res["ok"] is True
    assert res["creneaux"][0]["libelle"].startswith("vendredi 16/10")


def test_schemas_incluent_premiers_creneaux(regles):
    noms = {s["function"]["name"] for s in construire_schemas(regles)}
    assert "premiers_creneaux" in noms