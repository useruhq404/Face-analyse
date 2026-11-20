"""Tests de l'API serveur (auth, télémétrie, admin) via TestClient."""

from __future__ import annotations

from faceanalyse_server.security import hash_password, verify_password

from .conftest import login, register


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------ sécurité de base
def test_password_hash_roundtrip():
    h = hash_password("secret-pw")
    assert h != "secret-pw" and verify_password("secret-pw", h)
    assert not verify_password("wrong", h)


def test_health_and_config(client):
    assert client.get("/health").json()["status"] == "ok"
    cfg = client.get("/auth/config").json()
    assert cfg["open_registration"] is True
    assert cfg["discord_enabled"] is False and cfg["google_enabled"] is False
    assert "IP" in cfg["consent_notice"] or "adresse IP" in cfg["consent_notice"]


# ------------------------------------------------------------ inscription / login
def test_register_requires_consent(client):
    r = register(client, consent=False)
    assert r.status_code == 400


def test_register_and_login_flow(client):
    r = register(client)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["pseudo"] == "alice" and data["user"]["role"] == "user"
    token = data["token"]
    assert client.get("/auth/me", headers=auth(token)).json()["pseudo"] == "alice"

    # Mauvais mot de passe refusé, bon mot de passe accepté.
    assert client.post("/auth/login", json={"identifier": "alice", "password": "nope",
                                            "device": {}}).status_code == 401
    assert client.post("/auth/login", json={"identifier": "alice@example.com", "password": "password123",
                                            "device": {}}).status_code == 200


def test_duplicate_email_rejected(client):
    register(client)
    assert register(client, pseudo="alice2").status_code == 409


def test_token_required_and_invalid_rejected(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth("garbage")).status_code == 401


# ------------------------------------------------------------ télémétrie
def test_heartbeat_and_events_logged(client):
    token = register(client).json()["token"]
    assert client.post("/auth/heartbeat", headers=auth(token)).json()["user_status"] == "active"
    r = client.post("/events", headers=auth(token),
                    json={"kind": "action", "module": "osint", "action": "search", "detail": {"q": "x"}})
    assert r.status_code == 200
    # L'admin voit l'événement.
    admin = login(client).json()["token"]
    events = client.get("/admin/api/events", headers=auth(admin)).json()
    actions = {(e["module"], e["action"]) for e in events}
    assert ("osint", "search") in actions and ("auth", "register") in actions


def test_session_records_ip_and_device(client):
    register(client)
    admin = login(client).json()["token"]
    users = client.get("/admin/api/users", headers=auth(admin)).json()
    alice = next(u for u in users if u["pseudo"] == "alice")
    detail = client.get(f"/admin/api/users/{alice['id']}", headers=auth(admin)).json()
    s = detail["sessions"][0]
    assert s["hostname"] == "pc-alice" and s["os_name"] == "Windows 11"
    assert s["machine_id"] == "m-123" and s["ip"]  # une IP est bien enregistrée


# ------------------------------------------------------------ admin
def test_admin_requires_admin_role(client):
    token = register(client).json()["token"]
    assert client.get("/admin/api/users", headers=auth(token)).status_code == 403
    admin = login(client).json()["token"]
    assert client.get("/admin/api/users", headers=auth(admin)).status_code == 200


def test_ban_blocks_user_and_revokes_sessions(client):
    token = register(client).json()["token"]
    admin = login(client).json()["token"]
    uid = client.get("/auth/me", headers=auth(token)).json()["id"]
    assert client.post(f"/admin/api/users/{uid}/ban", headers=auth(admin),
                       json={"banned": True}).json()["status"] == "banned"
    # Sa session est révoquée : il ne peut plus agir, ni se reconnecter.
    assert client.get("/auth/me", headers=auth(token)).status_code in (401, 403)
    assert client.post("/auth/login", json={"identifier": "alice", "password": "password123",
                                            "device": {}}).status_code == 403
    # Réactivation.
    client.post(f"/admin/api/users/{uid}/ban", headers=auth(admin), json={"banned": False})
    assert client.post("/auth/login", json={"identifier": "alice", "password": "password123",
                                            "device": {}}).status_code == 200


def test_admin_cannot_ban_other_admin(client):
    token = register(client).json()["token"]
    admin_token = login(client).json()["token"]
    uid = client.get("/auth/me", headers=auth(token)).json()["id"]
    client.post(f"/admin/api/users/{uid}/role", headers=auth(admin_token), json={"role": "admin"})
    # L'admin d'origine ne peut pas bannir ce nouvel admin.
    assert client.post(f"/admin/api/users/{uid}/ban", headers=auth(admin_token),
                       json={"banned": True}).status_code == 403


def test_revoke_single_session(client):
    token = register(client).json()["token"]
    admin = login(client).json()["token"]
    uid = client.get("/auth/me", headers=auth(token)).json()["id"]
    sid = client.get(f"/admin/api/users/{uid}", headers=auth(admin)).json()["sessions"][0]["id"]
    client.post(f"/admin/api/sessions/{sid}/revoke", headers=auth(admin))
    assert client.get("/auth/me", headers=auth(token)).status_code == 401


def test_rgpd_delete_user(client):
    token = register(client).json()["token"]
    admin = login(client).json()["token"]
    uid = client.get("/auth/me", headers=auth(token)).json()["id"]
    assert client.delete(f"/admin/api/users/{uid}", headers=auth(admin)).json()["status"] == "deleted"
    assert all(u["id"] != uid for u in client.get("/admin/api/users", headers=auth(admin)).json())


def test_overview_counts(client):
    register(client)
    admin = login(client).json()["token"]
    ov = client.get("/admin/api/overview", headers=auth(admin)).json()
    assert ov["users"] >= 2 and ov["online"] >= 1


def test_admin_page_and_landing_served(client):
    assert "PANNEAU ADMINISTRATEUR" in client.get("/admin").text
    assert "SERVER" in client.get("/").text


def test_avatar_upload_and_fetch(client):
    token = register(client).json()["token"]
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    r = client.post("/me/avatar", headers=auth(token), files={"file": ("a.png", png, "image/png")})
    assert r.status_code == 200
    uid = client.get("/auth/me", headers=auth(token)).json()["id"]
    got = client.get(f"/users/{uid}/avatar")
    assert got.status_code == 200 and got.content == png
