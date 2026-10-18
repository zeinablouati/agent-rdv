"""Outils que le LLM peut appeler (function calling), et leur exécution.

- construire_schemas() : décrit les outils au format attendu par le LLM.
- Dispatcheur : exécute un appel d'outil via ServiceRendezVous et renvoie
  TOUJOURS un résultat JSON simple ({"ok": ...}), jamais une exception."""

from __future__ import annotations

from datetime import date, datetime

from ..agenda.creneaux import proposer
from ..agenda.erreurs import ErreurAgenda
from ..agenda.service import ServiceRendezVous
from ..config import Regles

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NB_CRENEAUX_PROPOSES = 5


def joli(dt: datetime) -> str:
    return f"{JOURS[dt.weekday()]} {dt:%d/%m} à {dt:%H:%M}"


def construire_schemas(regles: Regles, avec_infos: bool = False) -> list[dict]:
    types = sorted(regles.types_consultation)
    schemas = [
        {
            "type": "function",
            "function": {
                "name": "chercher_creneaux",
                "description": "Cherche des créneaux libres pour une consultation, sur une date ou une plage de dates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type_consultation": {"type": "string", "enum": types},
                        "date_debut": {"type": "string", "description": "Date ISO AAAA-MM-JJ."},
                        "date_fin": {"type": "string", "description": "Optionnel. Date ISO AAAA-MM-JJ."},
                        "periode": {"type": "string", "enum": ["matin", "apres_midi"], "description": "Optionnel."},
                    },
                    "required": ["type_consultation", "date_debut"],
                },
            },
        },
                {
            "type": "function",
            "function": {
                "name": "premiers_creneaux",
                "description": "Renvoie les créneaux libres les plus proches à partir de maintenant. À utiliser quand le patient veut un rendez-vous le plus tôt possible / dès que possible / rapidement.",
                "parameters": {
                    "type": "object",
                    "properties": {"type_consultation": {"type": "string", "enum": types}},
                    "required": ["type_consultation"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reserver",
                "description": "Réserve un rendez-vous sur un créneau précis proposé au patient.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type_consultation": {"type": "string", "enum": types},
                        "debut": {"type": "string", "description": "Début ISO AAAA-MM-JJTHH:MM (celui d'un créneau proposé)."},
                        "prenom": {"type": "string"},
                        "nom": {"type": "string"},
                        "telephone": {"type": "string"},
                        "email": {"type": "string", "description": "Optionnel. E-mail du patient, pour la confirmation."},

                    },
                    "required": ["type_consultation", "debut", "prenom", "nom", "telephone"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "retrouver_rdv",
                "description": "Retrouve les rendez-vous à venir d'un patient (nécessaire avant d'annuler ou de déplacer).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nom": {"type": "string"},
                        "telephone": {"type": "string"},
                    },
                    "required": ["nom", "telephone"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "annuler",
                "description": "Annule un rendez-vous existant, identifié par son rdv_id (obtenu via retrouver_rdv).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rdv_id": {"type": "string"},
                        "nom": {"type": "string"},
                        "telephone": {"type": "string"},
                    },
                    "required": ["rdv_id", "nom", "telephone"],
                },
            },
        },
                {
            "type": "function",
            "function": {
                "name": "demander_rappel",
                "description": "Enregistre une demande de rappel par le secrétariat, quand tu ne peux pas aider le patient ou qu'il est mécontent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nom": {"type": "string"},
                        "telephone": {"type": "string"},
                        "motif": {"type": "string", "description": "Courte raison de la demande de rappel."},
                    },
                    "required": ["nom", "telephone"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "deplacer",
                "description": "Déplace un rendez-vous existant vers un nouveau créneau.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rdv_id": {"type": "string"},
                        "nouveau_debut": {"type": "string", "description": "Début ISO AAAA-MM-JJTHH:MM."},
                        "nom": {"type": "string"},
                        "telephone": {"type": "string"},
                    },
                    "required": ["rdv_id", "nouveau_debut", "nom", "telephone"],
                },
            },
        },
    ]
    if avec_infos:
        schemas.append({
            "type": "function",
            "function": {
                "name": "chercher_infos",
                "description": "Cherche dans les informations pratiques du cabinet (horaires, adresse, accès, tarifs, remboursement, documents à apporter, carte Vitale) pour répondre à une question du patient.",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                },
            },
        })
    return schemas


class Dispatcheur:
    """Exécute un appel d'outil du LLM et renvoie un dict JSON-compatible."""

    def __init__(self, service: ServiceRendezVous, connaissances=None):
        self.service = service
        self.connaissances = connaissances

    def executer(self, nom: str, arguments: dict) -> dict:
        handlers = {
            "chercher_creneaux": self._chercher,
            "premiers_creneaux": self._premiers,
            "reserver": self._reserver,
            "retrouver_rdv": self._retrouver,
            "annuler": self._annuler,
            "deplacer": self._deplacer,
            "demander_rappel": self._demander_rappel,
            "chercher_infos": self._chercher_infos,
        }
        handler = handlers.get(nom)
        if handler is None:
            return {"ok": False, "code": "outil_inconnu", "message": f"Outil inconnu : {nom}."}
        try:
            return handler(arguments)
        except ErreurAgenda as erreur:
            return {"ok": False, "code": erreur.code, "message": erreur.message}
        except (ValueError, KeyError, TypeError) as erreur:
            return {"ok": False, "code": "donnees_invalides", "message": f"Paramètres invalides : {erreur}"}

    def _chercher(self, a: dict) -> dict:
        creneaux = self.service.chercher_creneaux(
            a["type_consultation"],
            date.fromisoformat(a["date_debut"]),
            date.fromisoformat(a["date_fin"]) if a.get("date_fin") else None,
            a.get("periode"),
        )
        choix = proposer(creneaux, NB_CRENEAUX_PROPOSES)
        return {
            "ok": True,
            "nombre_total": len(creneaux),
            "creneaux": [{"debut": c.debut.isoformat(), "libelle": joli(c.debut)} for c in choix],
        }
    def _premiers(self, a: dict) -> dict:
        creneaux = self.service.premiers_creneaux(a["type_consultation"])
        return {
            "ok": True,
            "creneaux": [{"debut": c.debut.isoformat(), "libelle": joli(c.debut)} for c in creneaux],
        }
    def _reserver(self, a: dict) -> dict:
        rdv = self.service.reserver(
            a["type_consultation"], datetime.fromisoformat(a["debut"]),
            a["prenom"], a["nom"], a["telephone"], a.get("email"),
        )
        return {"ok": True, "rdv_id": str(rdv.id), "debut": rdv.debut.isoformat(), "libelle": joli(rdv.debut)}

    def _retrouver(self, a: dict) -> dict:
        rdvs = self.service.retrouver_rdv(a["nom"], a["telephone"])
        return {
            "ok": True,
            "rdv": [
                {"rdv_id": str(r.id), "debut": r.debut.isoformat(), "libelle": joli(r.debut),
                 "type_consultation": r.type_consultation}
                for r in rdvs
            ],
        }

    def _annuler(self, a: dict) -> dict:
        rdv = self.service.annuler(a["rdv_id"], a["nom"], a["telephone"])
        return {"ok": True, "annule": joli(rdv.debut)}

    def _deplacer(self, a: dict) -> dict:
        rdv = self.service.deplacer(
            a["rdv_id"], datetime.fromisoformat(a["nouveau_debut"]), a["nom"], a["telephone"]
        )
        return {"ok": True, "rdv_id": str(rdv.id), "debut": rdv.debut.isoformat(), "libelle": joli(rdv.debut)}
    def _demander_rappel(self, a: dict) -> dict:
        identifiant = self.service.enregistrer_demande_rappel(a["nom"], a["telephone"], a.get("motif", ""))
        if identifiant is None:
            return {"ok": False, "code": "indisponible", "message": "Impossible d'enregistrer la demande de rappel."}
        return {"ok": True, "demande_id": identifiant}
    def _chercher_infos(self, a: dict) -> dict:
        if self.connaissances is None:
            return {"ok": False, "code": "indisponible", "message": "Informations pratiques indisponibles."}
        passages = self.connaissances.rechercher(a["question"])
        return {"ok": True, "passages": passages}