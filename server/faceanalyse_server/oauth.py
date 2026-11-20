"""Flux OAuth2 Discord et Google (facultatifs).

Chaque fournisseur renvoie un ``OAuthProfile`` normalisé. Les identifiants
d'application (client id/secret) sont fournis par variables d'environnement ;
sans eux, le fournisseur est désactivé et son bouton masqué.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from faceanalyse_server.config import Settings


@dataclass
class OAuthProfile:
    provider: str
    provider_id: str
    pseudo: str
    email: str | None
    avatar_url: str | None


class OAuthError(Exception):
    pass


def _redirect_uri(settings: Settings, provider: str) -> str:
    return f"{settings.public_url}/auth/{provider}/callback"


# ----------------------------------------------------------------- Discord
def discord_authorize_url(settings: Settings, state: str) -> str:
    from urllib.parse import urlencode

    q = urlencode({
        "response_type": "code",
        "client_id": settings.discord_client_id,
        "scope": "identify email",
        "redirect_uri": _redirect_uri(settings, "discord"),
        "state": state,
        "prompt": "consent",
    })
    return f"https://discord.com/oauth2/authorize?{q}"


def discord_exchange(settings: Settings, code: str) -> OAuthProfile:
    with httpx.Client(timeout=10) as client:
        tok = client.post("https://discord.com/api/oauth2/token", data={
            "client_id": settings.discord_client_id,
            "client_secret": settings.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(settings, "discord"),
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if tok.status_code != 200:
            raise OAuthError("Échange du code Discord refusé.")
        access = tok.json().get("access_token")
        me = client.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {access}"})
        if me.status_code != 200:
            raise OAuthError("Profil Discord inaccessible.")
    u = me.json()
    avatar = None
    if u.get("avatar"):
        avatar = f"https://cdn.discordapp.com/avatars/{u['id']}/{u['avatar']}.png?size=256"
    return OAuthProfile("discord", str(u["id"]), u.get("global_name") or u.get("username") or "discord",
                        u.get("email"), avatar)


# ----------------------------------------------------------------- Google
def google_authorize_url(settings: Settings, state: str) -> str:
    from urllib.parse import urlencode

    q = urlencode({
        "response_type": "code",
        "client_id": settings.google_client_id,
        "scope": "openid email profile",
        "redirect_uri": _redirect_uri(settings, "google"),
        "state": state,
        "access_type": "online",
        "prompt": "consent",
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{q}"


def google_exchange(settings: Settings, code: str) -> OAuthProfile:
    with httpx.Client(timeout=10) as client:
        tok = client.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(settings, "google"),
        })
        if tok.status_code != 200:
            raise OAuthError("Échange du code Google refusé.")
        access = tok.json().get("access_token")
        me = client.get("https://openidconnect.googleapis.com/v1/userinfo",
                        headers={"Authorization": f"Bearer {access}"})
        if me.status_code != 200:
            raise OAuthError("Profil Google inaccessible.")
    u = me.json()
    return OAuthProfile("google", str(u["sub"]), u.get("name") or u.get("email", "google").split("@")[0],
                        u.get("email"), u.get("picture"))


def exchange(settings: Settings, provider: str, code: str) -> OAuthProfile:
    if provider == "discord":
        return discord_exchange(settings, code)
    if provider == "google":
        return google_exchange(settings, code)
    raise OAuthError(f"Fournisseur inconnu : {provider}")


def authorize_url(settings: Settings, provider: str, state: str) -> str:
    if provider == "discord":
        return discord_authorize_url(settings, state)
    if provider == "google":
        return google_authorize_url(settings, state)
    raise OAuthError(f"Fournisseur inconnu : {provider}")
