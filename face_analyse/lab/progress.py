"""Persistance locale de la progression du module CYBER LAB (fichier JSON)."""

from __future__ import annotations

import json
from pathlib import Path

from face_analyse.core.paths import user_data_dir


def _path() -> Path:
    return user_data_dir() / "lab_progress.json"


def load_done() -> set[str]:
    """Identifiants des étapes cochées (ensemble vide si rien / illisible)."""
    try:
        data = json.loads(_path().read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    if isinstance(data, list):
        return {str(x) for x in data}
    return set()


def save_done(done: set[str]) -> None:
    """Écrit la progression de façon atomique (ignore les erreurs disque)."""
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(done), ensure_ascii=False), "utf-8")
        tmp.replace(p)
    except OSError:
        pass
