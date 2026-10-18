"""Erreurs métier. Chaque erreur porte un code stable et un message lisible,
que l'agent pourra transmettre au patient (Phase 3)."""


class ErreurAgenda(Exception):
    code = "erreur"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class TypeInconnu(ErreurAgenda):
    code = "type_inconnu"


class DonneesInvalides(ErreurAgenda):
    code = "donnees_invalides"


class CreneauRefuse(ErreurAgenda):
    """Le créneau demandé ne respecte pas une règle du cabinet.

    Codes possibles : cabinet_ferme, hors_horaires, creneau_non_propose,
    delai_trop_court, horizon_depasse, creneau_reserve_urgence, creneau_occupe.
    """


class ConflitCreneau(CreneauRefuse):
    """Garde-fou de dernière ligne : deux rendez-vous se chevaucheraient."""

    code = "creneau_occupe"


class RdvIntrouvable(ErreurAgenda):
    code = "rdv_introuvable"


class AnnulationTardive(ErreurAgenda):
    """Trop tard pour annuler ou déplacer seul : il faut passer par le secrétariat."""

    code = "annulation_tardive"