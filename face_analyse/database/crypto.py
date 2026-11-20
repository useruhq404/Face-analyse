"""Chiffrement des données biométriques au repos.

* Photos, embeddings et secrets (clé API) sont chiffrés avec Fernet
  (AES-128-CBC + HMAC-SHA256).
* La clé Fernet est stockée dans le dossier utilisateur ; sous Windows elle
  est en plus protégée par **DPAPI** (liée au compte Windows) : copier le
  fichier sur une autre machine ne permet pas de la relire.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from face_analyse.core.errors import DatabaseError
from face_analyse.core.paths import user_data_dir

log = logging.getLogger(__name__)

_DPAPI_MAGIC = b"DPAPI1:"


# ------------------------------------------------------------------ DPAPI
if sys.platform.startswith("win"):  # pragma: no cover - testé sous Windows uniquement
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _to_blob(data: bytes) -> _Blob:
        buf = ctypes.create_string_buffer(data, len(data))
        return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _from_blob(blob: _Blob) -> bytes:
        out = ctypes.string_at(blob.pbData, blob.cbData)
        ctypes.windll.kernel32.LocalFree(blob.pbData)
        return out

    def dpapi_protect(data: bytes) -> bytes:
        out = _Blob()
        if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(_to_blob(data)), "FaceAnalyse", None, None, None, 0, ctypes.byref(out)):
            raise OSError("CryptProtectData a échoué")
        return _from_blob(out)

    def dpapi_unprotect(data: bytes) -> bytes:
        out = _Blob()
        if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(_to_blob(data)), None, None, None, None, 0, ctypes.byref(out)):
            raise OSError("CryptUnprotectData a échoué")
        return _from_blob(out)

    DPAPI_AVAILABLE = True
else:
    DPAPI_AVAILABLE = False

    def dpapi_protect(data: bytes) -> bytes:
        raise OSError("DPAPI indisponible hors Windows")

    def dpapi_unprotect(data: bytes) -> bytes:
        raise OSError("DPAPI indisponible hors Windows")


# ------------------------------------------------------------------ clé
def key_path() -> Path:
    return user_data_dir() / "vault.key"


def load_or_create_key(path: Path | None = None) -> bytes:
    path = path or key_path()
    if path.exists():
        raw = path.read_bytes()
        if raw.startswith(_DPAPI_MAGIC):
            try:
                return dpapi_unprotect(raw[len(_DPAPI_MAGIC):])
            except OSError as exc:
                raise DatabaseError("Clé de chiffrement illisible (compte Windows différent ?)") from exc
        return raw.strip()
    key = Fernet.generate_key()
    payload = key
    if DPAPI_AVAILABLE:
        try:
            payload = _DPAPI_MAGIC + dpapi_protect(key)
        except OSError:  # pragma: no cover
            log.warning("DPAPI indisponible, clé stockée sans protection système")
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(payload)
    try:
        os.chmod(tmp, 0o600)
    except OSError:  # pragma: no cover - Windows ignore chmod
        pass
    tmp.replace(path)
    log.info("Nouvelle clé de chiffrement créée")
    return key


class Vault:
    def __init__(self, key: bytes | None = None):
        self._fernet = Fernet(key or load_or_create_key())

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        try:
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise DatabaseError("Donnée chiffrée invalide ou clé incorrecte") from exc
