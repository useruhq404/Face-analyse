#!/usr/bin/env bash
# FACE ANALYSE — serveur local (macOS / Linux)
#   ./start_server.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[1/2] Première installation…"
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi

echo "[2/2] Démarrage du serveur…"
exec python start_local.py
