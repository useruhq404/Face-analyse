"""Configuration du serveur, par variables d'environnement (jamais de secret en dur)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # Clé de signature (cookies admin, états OAuth). Générée si absente (volatile).
    secret_key: str = field(default_factory=lambda: os.environ.get("FA_SECRET_KEY") or secrets.token_urlsafe(48))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("FA_DATA_DIR", "./fa_server_data")))
    db_url: str = ""
    public_url: str = os.environ.get("FA_PUBLIC_URL", "http://localhost:8000").rstrip("/")
    trust_proxy: bool = _bool("FA_TRUST_PROXY", False)

    # Compte propriétaire créé/promu au démarrage.
    admin_email: str = os.environ.get("FA_ADMIN_EMAIL", "")
    admin_password: str = os.environ.get("FA_ADMIN_PASSWORD", "")
    admin_pseudo: str = os.environ.get("FA_ADMIN_PSEUDO", "owner")

    # Inscriptions ouvertes ? Sinon, seul l'admin crée des comptes / codes d'invitation.
    open_registration: bool = _bool("FA_OPEN_REGISTRATION", True)

    # OAuth (facultatif). Sans identifiants, les boutons correspondants sont masqués.
    discord_client_id: str = os.environ.get("FA_DISCORD_CLIENT_ID", "")
    discord_client_secret: str = os.environ.get("FA_DISCORD_CLIENT_SECRET", "")
    google_client_id: str = os.environ.get("FA_GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.environ.get("FA_GOOGLE_CLIENT_SECRET", "")

    # Une session est « en ligne » si vue depuis moins de N secondes.
    online_window_s: int = int(os.environ.get("FA_ONLINE_WINDOW_S", "90"))
    session_ttl_days: int = int(os.environ.get("FA_SESSION_TTL_DAYS", "30"))
    max_avatar_bytes: int = 2_000_000

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_url:
            self.db_url = os.environ.get("FA_DB_URL", f"sqlite:///{(self.data_dir / 'server.db').as_posix()}")

    @property
    def discord_enabled(self) -> bool:
        return bool(self.discord_client_id and self.discord_client_secret)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
