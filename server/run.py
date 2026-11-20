"""Lance le serveur FACE ANALYSE.

    python run.py            # http://localhost:8000  (/admin pour le panel)

Configuration par variables d'environnement (voir README.md) :
    FA_SECRET_KEY, FA_ADMIN_EMAIL, FA_ADMIN_PASSWORD, FA_PUBLIC_URL,
    FA_DISCORD_CLIENT_ID/SECRET, FA_GOOGLE_CLIENT_ID/SECRET, ...
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import uvicorn  # noqa: E402


def main() -> None:
    host = os.environ.get("FA_HOST", "0.0.0.0")
    port = int(os.environ.get("FA_PORT", "8000"))
    uvicorn.run("faceanalyse_server.app:app", host=host, port=port,
                reload=bool(os.environ.get("FA_RELOAD")), proxy_headers=True)


if __name__ == "__main__":
    main()
