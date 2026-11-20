"""Informations d'appareil envoyées au serveur (transparent pour l'utilisateur).

Volontairement limité : nom de machine, système, un identifiant technique
stable (non réversible) et la version de l'app. Aucune donnée personnelle
au-delà de ce que l'utilisateur a accepté à la connexion.
"""

from __future__ import annotations

import hashlib
import platform
import socket
import uuid

from face_analyse import __version__


def machine_id() -> str:
    """Identifiant stable par machine (haché, non réversible)."""
    raw = f"{uuid.getnode()}|{platform.node()}|{platform.system()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def collect() -> dict:
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = platform.node() or "unknown"
    return {
        "hostname": hostname[:120],
        "os_name": f"{platform.system()} {platform.release()}".strip()[:80],
        "machine_id": machine_id(),
        "app_version": __version__,
        "user_agent": f"FaceAnalyse/{__version__} ({platform.system()})",
    }
