"""Calcul des créneaux : toutes les règles du cabinet sont appliquées ici,
par du code. Le modèle de langage ne décide jamais de la disponibilité."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable

from ..config import Regles
from .erreurs import TypeInconnu
from .modeles import Creneau, Rdv

HEURE_COUPURE = time(13, 0)  # avant = matin, après = après-midi
PERIODES = ("matin", "apres_midi")


def _combiner(jour: date, heure: time, regles: Regles) -> datetime:
    return datetime.combine(jour, heure, tzinfo=regles.fuseau)


def duree_consultation(regles: Regles, type_consultation: str) -> timedelta:
    if type_consultation not in regles.types_consultation:
        types = ", ".join(sorted(regles.types_consultation))
        raise TypeInconnu(f"Type de consultation inconnu : '{type_consultation}' (attendu : {types}).")
    return timedelta(minutes=regles.types_consultation[type_consultation])


def blocs_urgence(regles: Regles, jour: date) -> list[tuple[datetime, datetime]]:
    """Créneaux gardés libres pour les urgences du jour : un bloc de durée
    standard à la fin de chaque plage horaire (fin de matinée, fin de journée)."""
    plages = regles.horaires.get(jour.weekday(), [])
    if not plages:
        return []
    duree = duree_consultation(regles, "standard")
    inverses = list(reversed(plages))
    blocs = []
    for k in range(regles.reservation.creneaux_urgence_par_jour):
        _, fin = inverses[k % len(inverses)]
        tour = k // len(inverses)
        fin_bloc = _combiner(jour, fin, regles) - tour * duree
        blocs.append((fin_bloc - duree, fin_bloc))
    return blocs


def _chevauche(debut_a: datetime, fin_a: datetime, debut_b: datetime, fin_b: datetime) -> bool:
    return debut_a < fin_b and debut_b < fin_a


def motif_refus(
    regles: Regles,
    type_consultation: str,
    debut: datetime,
    maintenant: datetime,
    occupes: Iterable[Rdv],
) -> tuple[str, str] | None:
    """None si le créneau est réservable, sinon (code, message)."""
    duree = duree_consultation(regles, type_consultation)
    res = regles.reservation
    debut = debut.astimezone(regles.fuseau)
    fin = debut + duree
    jour = debut.date()

    plages = regles.horaires.get(jour.weekday())
    if not plages:
        return ("cabinet_ferme", "Le cabinet est fermé ce jour-là.")
    if not any(_combiner(jour, d, regles) <= debut and fin <= _combiner(jour, f, regles) for d, f in plages):
        return ("hors_horaires", "Ce créneau est en dehors des horaires d'ouverture.")
    if debut.second or debut.microsecond or debut.minute % res.pas_creneaux_minutes:
        return ("creneau_non_propose", "Ce créneau ne fait pas partie des créneaux proposés.")
    if debut < maintenant + timedelta(hours=res.delai_minimum_heures):
        return ("delai_trop_court", f"Il faut réserver au moins {res.delai_minimum_heures} h à l'avance.")
    if jour > maintenant.astimezone(regles.fuseau).date() + timedelta(days=res.horizon_jours):
        return ("horizon_depasse", f"On ne peut pas réserver à plus de {res.horizon_jours} jours.")
    if any(_chevauche(debut, fin, b_debut, b_fin) for b_debut, b_fin in blocs_urgence(regles, jour)):
        return ("creneau_reserve_urgence", "Ce créneau est gardé pour les urgences du jour.")
    if any(_chevauche(debut, fin, r.debut, r.fin) for r in occupes):
        return ("creneau_occupe", "Ce créneau est déjà pris.")
    return None


def creneaux_libres(
    regles: Regles,
    type_consultation: str,
    du: date,
    au: date,
    maintenant: datetime,
    occupes: Iterable[Rdv],
    periode: str | None = None,
) -> list[Creneau]:
    """Tous les créneaux réservables entre deux dates incluses, triés."""
    if periode is not None and periode not in PERIODES:
        raise ValueError(f"Période inconnue : {periode} (attendu : {', '.join(PERIODES)})")
    duree = duree_consultation(regles, type_consultation)
    pas = timedelta(minutes=regles.reservation.pas_creneaux_minutes)
    occupes = list(occupes)
    limite = maintenant.astimezone(regles.fuseau).date() + timedelta(days=regles.reservation.horizon_jours)
    au = min(au, limite)

    resultat: list[Creneau] = []
    jour = du
    while jour <= au:
        for debut_plage, fin_plage in regles.horaires.get(jour.weekday(), []):
            t = _combiner(jour, debut_plage, regles)
            fin_p = _combiner(jour, fin_plage, regles)
            while t + duree <= fin_p:
                dans_periode = (
                    periode is None
                    or (periode == "matin") == (t.time() < HEURE_COUPURE)
                )
                if dans_periode and motif_refus(regles, type_consultation, t, maintenant, occupes) is None:
                    resultat.append(Creneau(t, t + duree))
                t += pas
        jour += timedelta(days=1)
    return resultat


def proposer(creneaux: list[Creneau], n: int = 3) -> list[Creneau]:
    """Choisit n créneaux répartis le long de la liste (début, milieu, fin)
    plutôt que les n premiers, pour donner un vrai choix au patient."""
    if n <= 0:
        return []
    if len(creneaux) <= n:
        return list(creneaux)
    if n == 1:
        return [creneaux[0]]
    indices = sorted({round(i * (len(creneaux) - 1) / (n - 1)) for i in range(n)})
    return [creneaux[i] for i in indices]