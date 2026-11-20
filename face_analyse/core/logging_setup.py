"""Journalisation technique : fichier tournant + console."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from face_analyse.core.paths import logs_dir

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(level)

    file_handler = RotatingFileHandler(
        logs_dir() / "face_analyse.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    _CONFIGURED = True
