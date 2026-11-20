import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client de test avec une base neuve et un compte admin connu."""
    monkeypatch.setenv("FA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FA_DB_URL", f"sqlite:///{(tmp_path / 'srv.db').as_posix()}")
    monkeypatch.setenv("FA_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("FA_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("FA_ADMIN_PASSWORD", "owner-password-123")
    monkeypatch.setenv("FA_ONLINE_WINDOW_S", "90")

    import faceanalyse_server.config as config
    import faceanalyse_server.db as db

    config._settings = None
    db._engine = None
    db._Session = None

    from fastapi.testclient import TestClient

    from faceanalyse_server.app import app

    with TestClient(app) as c:
        yield c


def register(client, pseudo="alice", email="alice@example.com", password="password123", consent=True):
    return client.post("/auth/register", json={
        "pseudo": pseudo, "email": email, "password": password, "consent": consent,
        "device": {"hostname": "pc-alice", "os_name": "Windows 11", "machine_id": "m-123", "app_version": "1.0.0"},
    })


def login(client, identifier="owner@example.com", password="owner-password-123"):
    return client.post("/auth/login", json={"identifier": identifier, "password": password,
                                            "device": {"hostname": "h", "os_name": "o", "machine_id": "m"}})
