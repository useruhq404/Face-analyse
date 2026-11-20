"""Lancement LOCAL du serveur FACE ANALYSE, en une commande.

    python start_local.py

Au premier lancement, ce script :
  * génère une clé secrète stable et un compte administrateur (vous),
  * les enregistre dans fa_server_data/local_config.json (gardé en local),
  * démarre le serveur et affiche tout ce qu'il faut (URL du panel, identifiants,
    et l'adresse à coller dans l'application de bureau).

Pour tester depuis un autre appareil du même réseau (téléphone, autre PC) :
    FA_HOST=0.0.0.0 python start_local.py
puis utilisez l'adresse « réseau local » affichée.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DATA_DIR = Path(os.environ.get("FA_DATA_DIR", HERE / "fa_server_data"))
CONFIG = DATA_DIR / "local_config.json"


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def load_or_create_config() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    cfg = {
        "secret_key": secrets.token_urlsafe(48),
        "admin_email": "admin@local",
        "admin_password": secrets.token_urlsafe(9),
        "admin_pseudo": "owner",
    }
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG, 0o600)
    except OSError:
        pass
    return cfg


def banner(cfg: dict, host: str, port: int) -> None:
    url_local = f"http://localhost:{port}"
    lan = local_ip()
    line = "═" * 62
    print(f"""
╔{line}╗
   FACE ANALYSE · SERVEUR LOCAL — prêt
╚{line}╝

  Panneau d'administration (ouvrez dans un navigateur) :
      {url_local}/admin

  Connexion administrateur (vous) :
      e-mail      : {cfg['admin_email']}
      mot de passe: {cfg['admin_password']}

  Dans l'application FACE ANALYSE → SETTINGS → « Serveur de comptes »,
  collez cette adresse :
      {url_local}
""")
    if host == "0.0.0.0":
        print(f"  Depuis un autre appareil du même réseau (Wi-Fi) :\n"
              f"      http://{lan}:{port}      (panel : http://{lan}:{port}/admin)\n")
    print("  Identifiants enregistrés dans :")
    print(f"      {CONFIG}")
    print("  (Arrêtez le serveur avec Ctrl+C.)\n")
    print("─" * 64)


def main() -> None:
    cfg = load_or_create_config()
    host = os.environ.get("FA_HOST", "127.0.0.1")
    port = int(os.environ.get("FA_PORT", "8000"))

    # Variables lues par le serveur (ne pas écraser ce que l'utilisateur force).
    os.environ.setdefault("FA_SECRET_KEY", cfg["secret_key"])
    os.environ.setdefault("FA_ADMIN_EMAIL", cfg["admin_email"])
    os.environ.setdefault("FA_ADMIN_PASSWORD", cfg["admin_password"])
    os.environ.setdefault("FA_ADMIN_PSEUDO", cfg.get("admin_pseudo", "owner"))
    os.environ.setdefault("FA_DATA_DIR", str(DATA_DIR))
    os.environ.setdefault("FA_PUBLIC_URL", f"http://localhost:{port}")

    banner(cfg, host, port)

    import uvicorn

    uvicorn.run("faceanalyse_server.app:app", host=host, port=port, proxy_headers=True, log_level="info")


if __name__ == "__main__":
    main()
