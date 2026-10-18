"""Lance le serveur de chat web (Phase 5).

  python scripts/web.py

Puis ouvre http://127.0.0.1:8000 dans ton navigateur.
Nécessite GROQ_API_KEY dans .env. Le RAG est actif si scripts/indexer.py a été lancé.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn

if __name__ == "__main__":
    print("Serveur de chat : http://127.0.0.1:8000  (Ctrl+C pour arrêter)")
    uvicorn.run("agent_rdv.web.app:app", host="127.0.0.1", port=8000, reload=False)