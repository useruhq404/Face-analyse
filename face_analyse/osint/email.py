"""OSINT e-mail : vérifications à partir de sources PUBLIQUES et officielles.

* Validation du format.
* Profil public **Gravatar** (si la personne l'a volontairement publié) :
  pseudo, nom affiché et comptes sociaux qu'elle a elle-même liés.
* Analyse du domaine (fournisseur grand public vs domaine propre).
* Pistes de pseudonymes dérivées de la partie locale.
* Liens de recherche à ouvrir soi-même (moteurs, fuites via le site HIBP).

Aucun accès à un compte, aucune vérification de mot de passe, aucun envoi d'e-mail.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from face_analyse.core.errors import OsintError
from face_analyse.osint.http import PoliteSession

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "hotmail.fr", "live.com",
    "yahoo.com", "yahoo.fr", "icloud.com", "me.com", "proton.me", "protonmail.com",
    "orange.fr", "wanadoo.fr", "free.fr", "sfr.fr", "laposte.net", "gmx.com", "yandex.com",
}


@dataclass
class GravatarProfile:
    profile_url: str = ""
    username: str = ""
    display_name: str = ""
    location: str = ""
    accounts: list[tuple[str, str]] = field(default_factory=list)  # (plateforme, url)


@dataclass
class EmailInfo:
    email: str
    valid: bool
    local: str
    domain: str
    provider_type: str  # "grand public" | "domaine propre"
    gravatar_found: bool = False
    gravatar: GravatarProfile | None = None
    username_candidates: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)  # (libellé, url)
    sources: list[str] = field(default_factory=list)


def _candidates(local: str) -> list[str]:
    base = re.sub(r"[.+_-].*$", "", local)  # avant un séparateur / suffixe +tag
    out = []
    for c in (local, local.replace(".", ""), local.replace(".", "_"), base):
        c = c.strip()
        if c and c not in out and re.match(r"^[A-Za-z0-9._-]{2,40}$", c):
            out.append(c)
    return out


def _gravatar(http: PoliteSession, email: str) -> GravatarProfile | None:
    digest = hashlib.md5(email.strip().lower().encode()).hexdigest()
    try:
        r = http.get(f"https://en.gravatar.com/{digest}.json")
    except Exception:  # noqa: BLE001 - réseau : pas de profil, on continue
        return None
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
        return None
    try:
        entry = (r.json().get("entry") or [])[0]
    except (ValueError, IndexError, AttributeError):
        return None
    accounts = [(a.get("shortname") or a.get("domain", ""), a.get("url", ""))
                for a in entry.get("accounts", []) if a.get("url")]
    loc = entry.get("currentLocation", "")
    return GravatarProfile(
        profile_url=entry.get("profileUrl", ""),
        username=entry.get("preferredUsername", ""),
        display_name=entry.get("displayName", ""),
        location=loc,
        accounts=accounts,
    )


def _links(email: str) -> list[tuple[str, str]]:
    e = quote_plus(f'"{email}"')
    return [
        ("Google", f"https://www.google.com/search?q={e}"),
        ("Bing", f"https://www.bing.com/search?q={e}"),
        ("DuckDuckGo", f"https://duckduckgo.com/?q={e}"),
        ("Fuites de données (Have I Been Pwned)", f"https://haveibeenpwned.com/account/{quote_plus(email)}"),
        ("GitHub (commits)", f"https://github.com/search?q={quote_plus(email)}&type=commits"),
    ]


def investigate(email: str, http: PoliteSession | None = None) -> EmailInfo:
    email = email.strip()
    if not EMAIL_RE.match(email):
        raise OsintError("Adresse e-mail invalide.")
    http = http or PoliteSession()
    local, domain = email.rsplit("@", 1)
    domain = domain.lower()
    info = EmailInfo(
        email=email, valid=True, local=local, domain=domain,
        provider_type="grand public" if domain in FREE_PROVIDERS else "domaine propre",
        username_candidates=_candidates(local), links=_links(email),
    )
    profile = _gravatar(http, email)
    if profile is not None:
        info.gravatar_found = True
        info.gravatar = profile
        info.sources.append("Gravatar")
        if profile.username and profile.username not in info.username_candidates:
            info.username_candidates.insert(0, profile.username)
    return info
