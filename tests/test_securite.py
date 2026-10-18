"""Phase 3, vague 1 : le garde-fou urgences détecte bien les urgences
et ne se déclenche pas sur des messages normaux."""

import pytest

from agent_rdv.llm.securite import est_urgence


@pytest.mark.parametrize(
    "message",
    [
        "J'ai très mal à la poitrine et du mal à respirer",
        "mon mari a fait un malaise, il ne répond plus",
        "je pense faire un infarctus",
        "DOULEUR THORACIQUE depuis ce matin",
        "j'étouffe",
        "j'ai envie de mourir",
    ],
)
def test_detecte_les_urgences(message):
    assert est_urgence(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "Bonjour, je voudrais un rendez-vous jeudi après-midi",
        "Est-ce que vous ouvrez le samedi ?",
        "Je dois annuler mon rendez-vous de mardi",
        "J'ai un petit rhume, rien d'urgent",
    ],
)
def test_ne_se_declenche_pas_sur_un_message_normal(message):
    assert est_urgence(message) is False