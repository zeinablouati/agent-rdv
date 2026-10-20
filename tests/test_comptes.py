"""Phase Admin, vague 1 : comptes médecins et mots de passe hachés."""

import pytest

from agent_rdv.admin.comptes import Comptes, hacher, verifier


def test_le_hachage_est_different_a_chaque_fois():
    # Sel aléatoire : deux hachages du même mot de passe diffèrent...
    assert hacher("secret123") != hacher("secret123")
    # ... mais les deux se vérifient correctement.
    assert verifier("secret123", hacher("secret123"))


def test_verifier_rejette_un_mauvais_mot_de_passe():
    stocke = hacher("bon-mot-de-passe")
    assert verifier("bon-mot-de-passe", stocke) is True
    assert verifier("mauvais", stocke) is False
    assert verifier("", stocke) is False


def test_verifier_tolere_un_hachage_invalide():
    assert verifier("x", "") is False
    assert verifier("x", "pas-un-hachage") is False


def test_creer_et_verifier_identifiants():
    comptes = Comptes()
    comptes.creer("Dr.Test", "motdepasse")
    assert comptes.verifier_identifiants("dr.test", "motdepasse") is True   # casse ignorée
    assert comptes.verifier_identifiants("dr.test", "autre") is False       # mauvais mot de passe
    assert comptes.verifier_identifiants("inconnu", "motdepasse") is False  # compte inexistant


def test_creer_met_a_jour_le_mot_de_passe():
    comptes = Comptes()
    comptes.creer("medecin", "ancien")
    comptes.creer("medecin", "nouveau")  # même identifiant : mise à jour
    assert comptes.verifier_identifiants("medecin", "nouveau") is True
    assert comptes.verifier_identifiants("medecin", "ancien") is False


def test_identifiant_ou_mot_de_passe_vide_refuse():
    comptes = Comptes()
    with pytest.raises(ValueError):
        comptes.creer("", "motdepasse")
    with pytest.raises(ValueError):
        comptes.creer("medecin", "")


def test_existe_au_moins_un():
    comptes = Comptes()
    assert comptes.existe_au_moins_un() is False
    comptes.creer("medecin", "motdepasse")
    assert comptes.existe_au_moins_un() is True