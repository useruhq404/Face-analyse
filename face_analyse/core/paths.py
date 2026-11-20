"""Résolution des chemins, compatible Windows, Linux, macOS et PyInstaller.

* Les **ressources** (modèles ONNX, images) sont en lecture seule et
  embarquées avec l'application (dossier ``_MEIPASS`` une fois compilée).
* Les **données utilisateur** (base SQLite, clé de chiffrement, journaux,
  rapports) sont écrites dans ``%LOCALAPPDATA%\\FaceAnalyse`` sous Windows,
  ``~/.local/share/FaceAnalyse`` ailleurs. La variable d'environnement
  ``FACE_ANALYSE_HOME`` permet de forcer un autre dossier (tests, mode portable).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "FaceAnalyse"


def resource_root() -> Path:
    """Dossier contenant ``resources/`` (source ou bundle PyInstaller)."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "face_analyse"
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath("resources", *parts)


def models_dir() -> Path:
    return resource_path("models")


def user_data_dir() -> Path:
    override = os.environ.get("FACE_ANALYSE_HOME")
    if override:
        base = Path(override)
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_DIR_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def user_subdir(name: str) -> Path:
    path = user_data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return user_data_dir() / "face_analyse.db"


def logs_dir() -> Path:
    return user_subdir("logs")


def reports_dir() -> Path:
    return user_subdir("reports")


def user_models_dir() -> Path:
    """Modèles ajoutés par l'utilisateur (remplacement sans recompilation)."""
    return user_subdir("models")
