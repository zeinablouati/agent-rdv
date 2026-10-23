"""Vague 4c : l'assistant de rédaction (brouillon de synthèse). Aucun réseau."""

import pytest

from agent_rdv.agenda.erreurs import DonneesInvalides
from agent_rdv.redaction import RedacteurMedical

from test_agent import FauxClient, msg_texte


def test_rediger_renvoie_le_brouillon_et_transmet_les_observations():
    client = FauxClient([msg_texte("Patiente vue pour toux depuis 5 jours, apyrétique.")])
    redacteur = RedacteurMedical(client, "faux")
    texte = redacteur.rediger_synthese("toux 5j, pas de fièvre", type_consultation="standard")
    assert "toux" in texte.lower()
    # les observations du médecin sont bien passées au modèle
    envoi = client.appels[0]["messages"][-1]["content"]
    assert "toux 5j" in envoi


def test_observations_vides_refusees():
    redacteur = RedacteurMedical(FauxClient([]), "faux")
    with pytest.raises(DonneesInvalides):
        redacteur.rediger_synthese("   ")


def test_reponse_vide_refusee():
    redacteur = RedacteurMedical(FauxClient([msg_texte("")]), "faux")
    with pytest.raises(DonneesInvalides):
        redacteur.rediger_synthese("toux")
