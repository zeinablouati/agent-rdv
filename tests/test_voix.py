"""Vague Voix V1 : l'orchestration du canal vocal, avec de faux micro/voix.
Aucun micro, aucun haut-parleur, aucun réseau."""

from agent_rdv.voix.base import (
    ACCUEIL,
    AU_REVOIR,
    SILENCE,
    CanalVocal,
    Synthetiseur,
    Transcripteur,
    extraire_email_dicte,
    nettoyer_pour_voix,
)


class FauxMicro(Transcripteur):
    """Rejoue des phrases préparées ; une chaîne vide = un silence."""

    def __init__(self, phrases):
        self._phrases = list(phrases)

    def ecouter(self) -> str:
        return self._phrases.pop(0) if self._phrases else ""


class FausseVoix(Synthetiseur):
    def __init__(self):
        self.dits = []

    def dire(self, texte: str) -> None:
        self.dits.append(texte)


class FauxAgent:
    """Cerveau minimal : renvoie une réponse qui reprend l'entrée."""

    def nouvelle_conversation(self):
        return []

    def repondre(self, historique, message):
        historique.append({"role": "user", "content": message})
        return f"Vous avez dit : {message}"


def test_un_tour_detecte_la_fin():
    canal = CanalVocal(FauxAgent(), FauxMicro(["au revoir"]), FausseVoix())
    tour = canal.un_tour()
    assert tour["fin"] is True and tour["reponse"].startswith("Vous avez dit")


def test_un_tour_silence():
    canal = CanalVocal(FauxAgent(), FauxMicro([""]), FausseVoix())
    tour = canal.un_tour()
    assert tour["silence"] is True and tour["reponse"] == ""


def test_la_boucle_accueille_repond_puis_raccroche():
    voix = FausseVoix()
    canal = CanalVocal(FauxAgent(), FauxMicro(["je voudrais un rendez-vous", "au revoir"]), voix)
    canal.boucle()
    assert voix.dits[0] == ACCUEIL
    assert "Vous avez dit : je voudrais un rendez-vous" in voix.dits
    assert voix.dits[-1] == AU_REVOIR


def test_deux_silences_raccrochent():
    voix = FausseVoix()
    canal = CanalVocal(FauxAgent(), FauxMicro(["", ""]), voix, silences_max=2)
    canal.boucle()
    assert SILENCE in voix.dits  # relance après le 1er silence
    assert voix.dits[-1] == AU_REVOIR  # raccroche au 2e


def test_nettoyer_retire_le_markdown():
    sale = "**Parfait**, je vous propose *9h20* :\n- lundi\n- mardi"
    propre = nettoyer_pour_voix(sale)
    assert "*" not in propre and "-" not in propre.split()  # plus de puces ni d'astérisques
    assert "9h20" in propre and "\n" not in propre


class AgentMarkdown(FauxAgent):
    def repondre(self, historique, message):
        return "**Très bien**, rendez-vous à *9h20*."


def test_la_voix_ne_prononce_pas_les_asterisques():
    voix = FausseVoix()
    canal = CanalVocal(AgentMarkdown(), FauxMicro(["un rendez-vous"]), voix)
    canal.un_tour()
    assert voix.dits and "*" not in voix.dits[-1]


def test_extraire_email_dicte():
    assert extraire_email_dicte("zeineb point louati arobase gmail point com") == "zeineb.louati@gmail.com"
    assert extraire_email_dicte("mon adresse est jean arobase exemple point fr") == "jean@exemple.fr"
    # une phrase ordinaire avec « point » mais sans arobase : on ne déclenche rien
    assert extraire_email_dicte("à quel point c'est loin") is None


def test_un_tour_reconstruit_l_email_avant_le_cerveau():
    agent = FauxAgent()
    canal = CanalVocal(agent, FauxMicro(["zeineb point louati arobase gmail point com"]), FausseVoix())
    tour = canal.un_tour()
    # le cerveau a reçu l'adresse propre, pas les mots dictés
    assert "zeineb.louati@gmail.com" in tour["reponse"]


def test_le_cerveau_garde_le_contexte_entre_les_tours():
    agent = FauxAgent()
    canal = CanalVocal(agent, FauxMicro(["premier", "second", "au revoir"]), FausseVoix())
    canal.boucle()
    # l'historique partagé a bien accumulé les deux prises de parole utiles
    dits = [m["content"] for m in canal.historique if m["role"] == "user"]
    assert "premier" in dits and "second" in dits
