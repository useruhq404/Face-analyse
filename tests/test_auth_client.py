"""Tests du client d'authentification (sans réseau : session requests simulée)."""

from __future__ import annotations

import json

import pytest
import requests

from face_analyse.auth import device
from face_analyse.auth.client import AuthClient
from face_analyse.core.errors import AuthError, ServerUnavailableError


class FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.headers = {}

    def request(self, method, url, **kw):
        return self.handler(method, url, kw)


def make_client(handler) -> AuthClient:
    c = AuthClient("http://srv.test")
    c._s = FakeSession(handler)
    return c


def test_device_info_fields():
    d = device.collect()
    assert set(d) >= {"hostname", "os_name", "machine_id", "app_version", "user_agent"}
    assert len(d["machine_id"]) >= 8
    assert device.machine_id() == device.machine_id()  # stable


def test_login_adopts_token_and_account():
    def handler(method, url, kw):
        assert url.endswith("/auth/login") and kw["json"]["identifier"] == "alice"
        return FakeResp(200, {"token": "tok-123",
                              "user": {"id": 1, "pseudo": "alice", "email": None, "provider": "local",
                                       "role": "user", "status": "active", "has_avatar": False}})
    c = make_client(handler)
    acc = c.login("alice", "pw")
    assert acc.pseudo == "alice" and c.token == "tok-123"
    assert c._headers()["Authorization"] == "Bearer tok-123"


def test_login_error_maps_detail():
    c = make_client(lambda m, u, kw: FakeResp(401, {"detail": "Identifiants incorrects."}))
    with pytest.raises(AuthError, match="incorrects"):
        c.login("x", "y")


def test_server_unavailable_wrapped():
    def handler(method, url, kw):
        raise requests.ConnectionError("boom")
    c = make_client(handler)
    assert c.ping() is False
    with pytest.raises(ServerUnavailableError):
        c.config()


def test_resume_invalid_token_returns_none():
    c = make_client(lambda m, u, kw: FakeResp(401, {"detail": "Session invalide."}))
    assert c.resume("stale") is None and c.token is None


def test_log_event_never_raises():
    c = make_client(lambda m, u, kw: (_ for _ in ()).throw(requests.ConnectionError()))
    c.token = "t"
    c.log_event("osint", "search", {"q": "x"})  # ne doit pas lever


def test_oauth_poll_waits_then_succeeds():
    calls = {"n": 0}

    def handler(method, url, kw):
        calls["n"] += 1
        if calls["n"] < 2:
            return FakeResp(202)
        return FakeResp(200, {"token": "t", "user": {"id": 5, "pseudo": "disco", "email": None,
                              "provider": "discord", "role": "user", "status": "active", "has_avatar": False}})
    c = make_client(handler)
    acc = c.oauth_poll("link", interval=0.01, timeout=5)
    assert acc.pseudo == "disco" and calls["n"] == 2
