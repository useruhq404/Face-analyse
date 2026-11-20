"""Vérification de l'existence d'un pseudonyme sur des plateformes publiques.

Seules des vérifications fiables sont utilisées (API publiques ou code
HTTP 404 explicite). Le contenu des profils n'est PAS récupéré : on indique
seulement qu'un compte portant ce pseudo existe. Un même pseudo est très
souvent utilisé par des personnes différentes.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

from face_analyse.osint.http import PoliteSession
from face_analyse.osint.models import normalize_text

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{2,40}$")


class Presence(str, Enum):
    FOUND = "trouvé"
    ABSENT = "absent"
    UNKNOWN = "indéterminé"


@dataclass(frozen=True)
class Platform:
    name: str
    check_url: str  # URL interrogée ({u})
    profile_url: str  # URL affichée à l'utilisateur
    mode: str = "status"  # status | json_nonempty | text_absent
    absent_marker: str = ""


PLATFORMS: list[Platform] = [
    Platform("GitHub", "https://api.github.com/users/{u}", "https://github.com/{u}"),
    Platform("GitLab", "https://gitlab.com/api/v4/users?username={u}", "https://gitlab.com/{u}", "json_nonempty"),
    Platform("Codeberg", "https://codeberg.org/api/v1/users/{u}", "https://codeberg.org/{u}"),
    Platform("Reddit", "https://www.reddit.com/user/{u}/about.json", "https://www.reddit.com/user/{u}"),
    Platform("Hacker News", "https://hacker-news.firebaseio.com/v0/user/{u}.json", "https://news.ycombinator.com/user?id={u}", "json_nonempty"),
    Platform("Dev.to", "https://dev.to/api/users/by_username?url={u}", "https://dev.to/{u}"),
    Platform("Keybase", "https://keybase.io/_/api/1.0/user/lookup.json?usernames={u}", "https://keybase.io/{u}", "text_absent", '"them":[null]'),
    Platform("Mastodon (mastodon.social)", "https://mastodon.social/api/v1/accounts/lookup?acct={u}", "https://mastodon.social/@{u}"),
    Platform("Bluesky", "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={u}.bsky.social", "https://bsky.app/profile/{u}.bsky.social"),
    Platform("Chess.com", "https://api.chess.com/pub/player/{u}", "https://www.chess.com/member/{u}"),
    Platform("Lichess", "https://lichess.org/api/user/{u}", "https://lichess.org/@/{u}"),
    Platform("Docker Hub", "https://hub.docker.com/v2/users/{u}/", "https://hub.docker.com/u/{u}"),
    Platform("PyPI", "https://pypi.org/user/{u}/", "https://pypi.org/user/{u}/"),
    Platform("npm", "https://registry.npmjs.org/-/user/org.couchdb.user:{u}", "https://www.npmjs.com/~{u}"),
    Platform("SoundCloud", "https://soundcloud.com/{u}", "https://soundcloud.com/{u}"),
    Platform("Linktree", "https://linktr.ee/{u}", "https://linktr.ee/{u}"),
    Platform("Vimeo", "https://vimeo.com/{u}", "https://vimeo.com/{u}"),
    Platform("Steam", "https://steamcommunity.com/id/{u}", "https://steamcommunity.com/id/{u}", "text_absent",
             "The specified profile could not be found"),
    Platform("Telegram", "https://t.me/{u}", "https://t.me/{u}", "text_absent", 'tgme_page_title" ><span dir="auto"></span>'),
]


@dataclass(frozen=True)
class UsernameHit:
    username: str
    platform: str
    url: str
    presence: Presence
    detail: str = ""


@dataclass(frozen=True)
class ProfileSite:
    """Site dont l'URL de profil est prévisible à partir du pseudo.

    Ces plateformes bloquent la collecte automatisée (anti-robots) : on ne les
    interroge PAS. On construit seulement l'URL à OUVRIR dans le navigateur, avec
    son propre compte, dans le respect des règles du site.
    """
    name: str
    category: str
    url: str  # gabarit avec {u}
    note: str = ""


#: Grand répertoire « façon menu » — liens profil direct, à ouvrir soi-même.
#: Couvre les réseaux que l'anti-robots interdit d'interroger automatiquement.
DIRECT_PROFILE_SITES: list[ProfileSite] = [
    # Réseaux sociaux grand public
    ProfileSite("Instagram", "Réseaux sociaux", "https://www.instagram.com/{u}/"),
    ProfileSite("TikTok", "Réseaux sociaux", "https://www.tiktok.com/@{u}"),
    ProfileSite("Snapchat", "Réseaux sociaux", "https://www.snapchat.com/add/{u}"),
    ProfileSite("X / Twitter", "Réseaux sociaux", "https://x.com/{u}"),
    ProfileSite("Facebook", "Réseaux sociaux", "https://www.facebook.com/{u}"),
    ProfileSite("LinkedIn", "Réseaux sociaux", "https://www.linkedin.com/in/{u}", "connexion requise"),
    ProfileSite("Threads", "Réseaux sociaux", "https://www.threads.net/@{u}"),
    ProfileSite("Pinterest", "Réseaux sociaux", "https://www.pinterest.com/{u}/"),
    ProfileSite("Tumblr", "Réseaux sociaux", "https://{u}.tumblr.com"),
    ProfileSite("VK", "Réseaux sociaux", "https://vk.com/{u}"),
    ProfileSite("Discord", "Réseaux sociaux", 'https://www.google.com/search?q=%22{u}%22+discord',
                "Discord n'expose pas de profil public par pseudo → recherche web"),
    # Messageries / contact
    ProfileSite("Telegram", "Messageries", "https://t.me/{u}"),
    # Vidéo / streaming
    ProfileSite("YouTube", "Vidéo", "https://www.youtube.com/@{u}"),
    ProfileSite("Twitch", "Vidéo", "https://www.twitch.tv/{u}"),
    ProfileSite("Vimeo", "Vidéo", "https://vimeo.com/{u}"),
    ProfileSite("Dailymotion", "Vidéo", "https://www.dailymotion.com/{u}"),
    # Jeux vidéo
    ProfileSite("Steam", "Jeux vidéo", "https://steamcommunity.com/id/{u}"),
    ProfileSite("Roblox", "Jeux vidéo", "https://www.roblox.com/search/users?keyword={u}"),
    ProfileSite("Xbox Gamertag", "Jeux vidéo", "https://xboxgamertag.com/search/{u}"),
    ProfileSite("Epic / Fortnite (fortnitetracker)", "Jeux vidéo", "https://fortnitetracker.com/profile/all/{u}"),
    ProfileSite("Chess.com", "Jeux vidéo", "https://www.chess.com/member/{u}"),
    ProfileSite("Lichess", "Jeux vidéo", "https://lichess.org/@/{u}"),
    # Musique / audio
    ProfileSite("SoundCloud", "Musique", "https://soundcloud.com/{u}"),
    ProfileSite("Spotify", "Musique", "https://open.spotify.com/user/{u}"),
    ProfileSite("Bandcamp", "Musique", "https://{u}.bandcamp.com"),
    ProfileSite("Last.fm", "Musique", "https://www.last.fm/user/{u}"),
    # Photo / visuel
    ProfileSite("Flickr", "Photo", "https://www.flickr.com/people/{u}"),
    ProfileSite("500px", "Photo", "https://500px.com/p/{u}"),
    ProfileSite("DeviantArt", "Photo", "https://www.deviantart.com/{u}"),
    ProfileSite("Behance", "Photo", "https://www.behance.net/{u}"),
    # Écriture / blog
    ProfileSite("Medium", "Écriture", "https://medium.com/@{u}"),
    ProfileSite("Substack", "Écriture", "https://{u}.substack.com"),
    ProfileSite("Wattpad", "Écriture", "https://www.wattpad.com/user/{u}"),
    # Développement
    ProfileSite("GitHub", "Développement", "https://github.com/{u}"),
    ProfileSite("GitLab", "Développement", "https://gitlab.com/{u}"),
    ProfileSite("Replit", "Développement", "https://replit.com/@{u}"),
    ProfileSite("Stack Overflow (recherche)", "Développement",
                "https://stackoverflow.com/users?tab=Reputation&search={u}"),
    # Créateurs / liens
    ProfileSite("Patreon", "Créateurs", "https://www.patreon.com/{u}"),
    ProfileSite("Ko-fi", "Créateurs", "https://ko-fi.com/{u}"),
    ProfileSite("Linktree", "Créateurs", "https://linktr.ee/{u}"),
    ProfileSite("Buy Me a Coffee", "Créateurs", "https://www.buymeacoffee.com/{u}"),
    # Forums / communautés
    ProfileSite("Reddit", "Communautés", "https://www.reddit.com/user/{u}"),
    ProfileSite("Mastodon (recherche)", "Communautés", "https://mastodon.social/@{u}"),
    ProfileSite("Bluesky", "Communautés", "https://bsky.app/profile/{u}.bsky.social"),
    ProfileSite("Product Hunt", "Communautés", "https://www.producthunt.com/@{u}"),
]


def profile_links(username: str) -> list[tuple[str, str, str, str]]:
    """Liens profil direct (name, category, url, note) pour un pseudo.

    N'interroge aucun site : construit des URL à ouvrir soi-même. Le pseudo est
    déjà restreint à des caractères sûrs pour une URL (USERNAME_RE).
    """
    u = username.strip().lstrip("@")
    if not USERNAME_RE.match(u):
        return []
    return [(s.name, s.category, s.url.format(u=u), s.note) for s in DIRECT_PROFILE_SITES]


def candidate_usernames(first_name: str, last_name: str) -> list[str]:
    """Pseudonymes courants dérivés du nom (variantes classiques)."""
    f = normalize_text(first_name).replace(" ", "")
    l_ = normalize_text(last_name).replace(" ", "")
    if not f or not l_:
        return []
    raw = [f + l_, f"{f}.{l_}", f"{f}_{l_}", f"{f}-{l_}", f[0] + l_, l_ + f, f"{l_}.{f}", f + l_[0]]
    seen, out = set(), []
    for c in raw:
        if c not in seen and USERNAME_RE.match(c):
            seen.add(c)
            out.append(c)
    return out


def check_one(http: PoliteSession, platform: Platform, username: str) -> UsernameHit:
    url = platform.profile_url.format(u=username)
    try:
        r = http.get(platform.check_url.format(u=username), allow_redirects=True,
                     headers={"Accept": "application/json, text/html;q=0.9"})
    except Exception as exc:  # noqa: BLE001 - réseau : on reste « indéterminé »
        return UsernameHit(username, platform.name, url, Presence.UNKNOWN, type(exc).__name__)
    code = r.status_code
    if code in (404, 410):
        return UsernameHit(username, platform.name, url, Presence.ABSENT)
    if code == 400 and "bsky" in platform.check_url:
        return UsernameHit(username, platform.name, url, Presence.ABSENT)
    if code != 200:
        return UsernameHit(username, platform.name, url, Presence.UNKNOWN, f"HTTP {code}")
    if platform.mode == "json_nonempty":
        try:
            data = r.json()
        except ValueError:
            return UsernameHit(username, platform.name, url, Presence.UNKNOWN, "réponse invalide")
        return UsernameHit(username, platform.name, url, Presence.FOUND if data else Presence.ABSENT)
    if platform.mode == "text_absent":
        absent = platform.absent_marker in r.text.replace(" ", "") or platform.absent_marker in r.text
        return UsernameHit(username, platform.name, url, Presence.ABSENT if absent else Presence.FOUND)
    return UsernameHit(username, platform.name, url, Presence.FOUND)


def check_usernames(http: PoliteSession, usernames: list[str], platforms: list[Platform] | None = None,
                    workers: int = 8, progress=None) -> list[UsernameHit]:
    platforms = platforms or PLATFORMS
    valid = [u for u in usernames if USERNAME_RE.match(u)]
    jobs = [(p, u) for u in valid for p in platforms]
    hits: list[UsernameHit] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, hit in enumerate(pool.map(lambda j: check_one(http, *j), jobs)):
            hits.append(hit)
            if progress:
                progress(i + 1, len(jobs))
    return hits
