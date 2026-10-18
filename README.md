# Agent RDV

Secrétaire virtuelle pour un cabinet de médecine générale (prototype, patients fictifs uniquement).

## Démarrage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```

## Structure

| Dossier | Rôle |
|---|---|
| `config/cabinet.yaml` | Règles du cabinet (horaires, durées, délais) |
| `src/agent_rdv/config.py` | Chargement et validation des règles |
| `src/agent_rdv/agenda/` | Calcul des créneaux, réservation (Phases 1-2) |
| `src/agent_rdv/tools/` | Outils appelables par le LLM (Phase 3) |
| `src/agent_rdv/llm/` | Connexion au modèle de langage (Phase 3) |
| `src/agent_rdv/knowledge/` | Base d'informations du cabinet (Phase 4) |
| `src/agent_rdv/channels/` | Telegram / chat web (Phase 5) |
| `data/knowledge/` | Documents du cabinet (horaires, tarifs...) |
| `tests/` | Tests automatiques, dont les 8 conversations types |

## Principes

- Le code applique les règles du cabinet, le modèle de langage ne fait que dialoguer.
- Aucun motif médical n'est collecté ni stocké.
- Urgence détectée = redirection immédiate vers le 15 ou le 112.
