"""Client HTTP vers le serveur de comptes FACE ANALYSE."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

from face_analyse.auth import device
from face_analyse.core.errors import AuthError, ServerUnavailableError

log = logging.getLogger(__name__)


@dataclass
class Account:
    id: int
    pseudo: str
    email: str | None
    provider: str
    role: str
    status: str
    has_avatar: bool

    @classmethod
    def from_dict(cls, d: dict) -> "Account":
        return cls(d["id"], d["pseudo"], d.get("email"), d.get("provider", "local"),
                   d.get("role", "user"), d.get("status", "active"), d.get("has_avatar", False))


@dataclass
class ServerConfig:
    discord_enabled: bool = False
    google_enabled: bool = False
    open_registration: bool = True
    consent_notice: str = ""
    data_collected: list = None  # type: ignore


class AuthClient:
    """Enveloppe requests. Le jeton est conservé par l'appelant (chiffré)."""

    def __init__(self, base_url: str, timeout: float = 12.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self.account: Account | None = None
        self._s = requests.Session()
        self._s.headers["User-Agent"] = device.collect()["user_agent"]

    # ------------------------------------------------------------ bas niveau
    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _request(self, method: str, path: str, **kw) -> requests.Response:
        try:
            r = self._s.request(method, self._url(path), timeout=self.timeout,
                                 headers={**self._headers(), **kw.pop("headers", {})}, **kw)
        except requests.RequestException as exc:
            raise ServerUnavailableError(f"Serveur injoignable : {self.base_url}") from exc
        return r

    @staticmethod
    def _detail(r: requests.Response) -> str:
        try:
            return r.json().get("detail", r.text[:200])
        except ValueError:
            return r.text[:200] or f"HTTP {r.status_code}"

    # ------------------------------------------------------------ public
    def ping(self) -> bool:
        try:
            return self._request("GET", "/health").status_code == 200
        except ServerUnavailableError:
            return False

    def config(self) -> ServerConfig:
        r = self._request("GET", "/auth/config")
        if r.status_code != 200:
            raise ServerUnavailableError()
        d = r.json()
        return ServerConfig(d["discord_enabled"], d["google_enabled"], d["open_registration"],
                            d["consent_notice"], d.get("data_collected", []))

    def _adopt(self, r: requests.Response) -> Account:
        if r.status_code != 200:
            raise AuthError(self._detail(r))
        data = r.json()
        self.token = data["token"]
        self.account = Account.from_dict(data["user"])
        return self.account

    def register(self, pseudo: str, email: str | None, password: str, consent: bool) -> Account:
        return self._adopt(self._request("POST", "/auth/register", json={
            "pseudo": pseudo, "email": email or None, "password": password,
            "consent": consent, "device": device.collect()}))

    def login(self, identifier: str, password: str) -> Account:
        return self._adopt(self._request("POST", "/auth/login", json={
            "identifier": identifier, "password": password, "device": device.collect()}))

    def resume(self, token: str) -> Account | None:
        """Reprend une session existante à partir d'un jeton stocké."""
        self.token = token
        r = self._request("GET", "/auth/me")
        if r.status_code == 200:
            self.account = Account.from_dict(r.json())
            return self.account
        self.token = None
        return None

    # ----- OAuth (navigateur + attente)
    def oauth_start(self, provider: str) -> tuple[str, str]:
        r = self._request("POST", "/auth/oauth/start", json={"provider": provider})
        if r.status_code != 200:
            raise AuthError(self._detail(r))
        d = r.json()
        return d["url"], d["link_code"]

    def oauth_poll(self, link_code: str, interval: float = 2.0, timeout: float = 180.0) -> Account:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = self._request("POST", "/auth/oauth/claim",
                              json={"link_code": link_code, "device": device.collect()})
            if r.status_code == 202:
                time.sleep(interval)
                continue
            return self._adopt(r)
        raise AuthError("Délai de connexion dépassé.")

    # ----- session active
    def heartbeat(self) -> dict:
        r = self._request("POST", "/auth/heartbeat")
        if r.status_code != 200:
            raise AuthError(self._detail(r))
        return r.json()

    def log_event(self, module: str, action: str, detail: dict | None = None, kind: str = "action") -> None:
        if not self.token:
            return
        try:
            self._request("POST", "/events", json={"kind": kind, "module": module,
                                                   "action": action, "detail": detail or {}})
        except AuthError:
            pass  # la journalisation ne doit jamais bloquer l'app

    def set_avatar(self, data: bytes, content_type: str = "image/png") -> None:
        r = self._request("POST", "/me/avatar", files={"file": ("avatar", data, content_type)})
        if r.status_code != 200:
            raise AuthError(self._detail(r))

    def logout(self) -> None:
        if self.token:
            try:
                self._request("POST", "/auth/logout")
            except AuthError:
                pass
        self.token, self.account = None, None
