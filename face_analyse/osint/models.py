"""Structures de données OSINT."""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


def normalize_text(value: str) -> str:
    """Minuscule, sans accents, espaces normalisés."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().replace("-", " ").split())


def canonical_url(url: str) -> str:
    """Forme canonique pour la détection des doublons."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, parts.query, ""))


@dataclass(frozen=True)
class OsintQuery:
    first_name: str
    last_name: str
    city: str = ""
    extra_keywords: str = ""
    usernames: tuple[str, ...] = ()

    @property
    def full_name(self) -> str:
        return f"{self.first_name.strip()} {self.last_name.strip()}".strip()

    def validate(self) -> None:
        from face_analyse.core.errors import OsintError

        if len(self.last_name.strip()) < 2 or len(self.first_name.strip()) < 1:
            raise OsintError("Prénom et nom sont obligatoires (nom : 2 caractères minimum).")


@dataclass
class OsintResult:
    source: str  # ex. "Wikipedia (fr)"
    category: str  # Encyclopédie, Entreprises, Recherche, Code, Pseudonyme…
    title: str
    url: str
    snippet: str = ""
    relevance: float = 0.0  # correspondance du NOM (0-1), pas de l'identité
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    extra: dict[str, str] = field(default_factory=dict)
    duplicates: list[str] = field(default_factory=list)  # autres sources ayant la même URL

    @property
    def key(self) -> str:
        return canonical_url(self.url)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceStatus:
    source: str
    ok: bool
    count: int
    elapsed_ms: float
    error: str = ""


@dataclass
class SearchLink:
    platform: str
    category: str
    url: str
    note: str = ""


@dataclass
class OsintReport:
    query: OsintQuery
    started_at: str
    finished_at: str
    results: list[OsintResult]
    statuses: list[SourceStatus]
    links: list[SearchLink]
    duplicates_removed: int = 0
    ai_summary: str = ""
