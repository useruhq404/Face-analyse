"""API FastAPI : authentification, télémétrie de sécurité, panel d'administration."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from faceanalyse_server import __version__, content, oauth, service
from faceanalyse_server.config import Settings, get_settings
from faceanalyse_server.db import init_engine, new_session
from faceanalyse_server.models import AuthSession, Event, OAuthPending, User, utcnow
from faceanalyse_server.schemas import ClaimIn, EventIn, LoginIn, RegisterIn, TokenOut, UserOut
from faceanalyse_server.security import client_ip, token_hash, verify_password

WEB = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    init_engine()
    db = new_session()
    try:
        service.bootstrap_admin(db, settings)
        service.purge_expired(db, settings)
    finally:
        db.close()
    yield


app = FastAPI(title="FACE ANALYSE Server", version=__version__, lifespan=lifespan)


def db_dep():
    db = new_session()
    try:
        yield db
    finally:
        db.close()


def _state_serializer(settings: Settings) -> URLSafeSerializer:
    return URLSafeSerializer(settings.secret_key, salt="oauth-state")


# ------------------------------------------------------------ dépendances auth
def current(request: Request, db: Session = Depends(db_dep)) -> tuple[User, AuthSession]:
    settings = get_settings()
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Jeton manquant.")
    sess = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(auth[7:])))
    if sess is None or sess.revoked:
        raise HTTPException(401, "Session invalide ou révoquée.")
    user = db.get(User, sess.user_id)
    if user is None or user.status == "banned":
        raise HTTPException(403, "Compte suspendu.")
    sess.last_seen = utcnow()
    sess.ip = client_ip(request, settings.trust_proxy)
    db.commit()
    request.state.db = db
    return user, sess


def admin_only(pair: tuple[User, AuthSession] = Depends(current)) -> tuple[User, AuthSession]:
    if pair[0].role != "admin":
        raise HTTPException(403, "Réservé à l'administrateur.")
    return pair


# ------------------------------------------------------------ public
@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/auth/config")
def auth_config():
    s = get_settings()
    return {"discord_enabled": s.discord_enabled, "google_enabled": s.google_enabled,
            "open_registration": s.open_registration, "consent_notice": content.CONSENT_NOTICE,
            "data_collected": content.DATA_COLLECTED}


@app.post("/auth/register", response_model=TokenOut)
def register(body: RegisterIn, request: Request, db: Session = Depends(db_dep)):
    s = get_settings()
    if not s.open_registration:
        raise HTTPException(403, "Les inscriptions sont fermées. Contactez l'administrateur.")
    if not body.consent:
        raise HTTPException(400, "Le consentement est requis pour créer un compte.")
    email = body.email.lower() if body.email else None
    if email and db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Un compte existe déjà avec cet e-mail.")
    from faceanalyse_server.security import hash_password

    user = User(pseudo=body.pseudo.strip(), email=email, password_hash=hash_password(body.password),
                provider="local", role="user", status="active", consent_at=utcnow())
    db.add(user)
    db.commit()
    ip = client_ip(request, s.trust_proxy)
    sess, token = service.create_session(db, s, user, ip, body.device, request.headers.get("user-agent", ""))
    service.log_event(db, user.id, "login", module="auth", action="register", ip=ip, session_id=sess.id)
    return TokenOut(token=token, user=UserOut.of(user))


@app.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(db_dep)):
    s = get_settings()
    ident = body.identifier.strip()
    user = db.scalar(select(User).where((func.lower(User.email) == ident.lower()) | (User.pseudo == ident)))
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Identifiants incorrects.")
    if user.status == "banned":
        service.log_event(db, user.id, "security", module="auth", action="login_banned",
                          ip=client_ip(request, s.trust_proxy))
        raise HTTPException(403, "Compte suspendu.")
    ip = client_ip(request, s.trust_proxy)
    sess, token = service.create_session(db, s, user, ip, body.device, request.headers.get("user-agent", ""))
    service.log_event(db, user.id, "login", module="auth", action="login", ip=ip, session_id=sess.id)
    return TokenOut(token=token, user=UserOut.of(user))


@app.post("/auth/logout")
def logout(pair: tuple[User, AuthSession] = Depends(current), db: Session = Depends(db_dep)):
    user, sess = pair
    live = db.get(AuthSession, sess.id)
    if live:
        live.revoked = True
        db.commit()
    service.log_event(db, user.id, "logout", module="auth", action="logout", ip=sess.ip, session_id=sess.id)
    return {"status": "ok"}


@app.get("/auth/me", response_model=UserOut)
def me(pair: tuple[User, AuthSession] = Depends(current)):
    return UserOut.of(pair[0])


@app.post("/auth/heartbeat")
def heartbeat(pair: tuple[User, AuthSession] = Depends(current)):
    # Le simple fait d'arriver ici a mis à jour last_seen (dépendance current).
    return {"status": "ok", "user_status": pair[0].status, "role": pair[0].role}


@app.post("/events")
def post_event(body: EventIn, pair: tuple[User, AuthSession] = Depends(current), db: Session = Depends(db_dep)):
    user, sess = pair
    kind = body.kind if body.kind in ("action", "heartbeat") else "action"
    service.log_event(db, user.id, kind, module=body.module, action=body.action,
                      detail=body.detail or {}, ip=sess.ip, session_id=sess.id)
    return {"status": "ok"}


@app.post("/me/avatar")
async def set_avatar(file: UploadFile = File(...), pair: tuple[User, AuthSession] = Depends(current),
                     db: Session = Depends(db_dep)):
    s = get_settings()
    data = await file.read(s.max_avatar_bytes + 1)
    if len(data) > s.max_avatar_bytes:
        raise HTTPException(413, "Image trop volumineuse (max 2 Mo).")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "Fichier image attendu.")
    user = db.get(User, pair[0].id)
    user.avatar, user.avatar_type = data, file.content_type
    db.commit()
    return {"status": "ok"}


@app.get("/users/{user_id}/avatar")
def get_avatar(user_id: int, db: Session = Depends(db_dep)):
    user = db.get(User, user_id)
    if user is None or not user.avatar:
        raise HTTPException(404, "Pas d'avatar.")
    return Response(content=user.avatar, media_type=user.avatar_type or "image/png")


# ------------------------------------------------------------ OAuth (navigateur + client)
@app.post("/auth/oauth/start")
def oauth_start(payload: dict, db: Session = Depends(db_dep)):
    s = get_settings()
    provider = payload.get("provider", "")
    if provider == "discord" and not s.discord_enabled:
        raise HTTPException(400, "Discord non configuré sur ce serveur.")
    if provider == "google" and not s.google_enabled:
        raise HTTPException(400, "Google non configuré sur ce serveur.")
    if provider not in ("discord", "google"):
        raise HTTPException(400, "Fournisseur inconnu.")
    link = service.new_link_code()
    db.add(OAuthPending(link_code=link, provider=provider))
    db.commit()
    return {"link_code": link, "url": f"{s.public_url}/auth/{provider}/login?link={link}"}


@app.get("/auth/{provider}/login")
def oauth_login(provider: str, link: str, db: Session = Depends(db_dep)):
    s = get_settings()
    if db.get(OAuthPending, link) is None:
        raise HTTPException(400, "Lien expiré.")
    state = _state_serializer(s).dumps({"provider": provider, "link": link})
    return RedirectResponse(oauth.authorize_url(s, provider, state))


@app.get("/auth/{provider}/callback", response_class=HTMLResponse)
def oauth_callback(provider: str, request: Request, code: str = "", state: str = "",
                   db: Session = Depends(db_dep)):
    s = get_settings()
    try:
        data = _state_serializer(s).loads(state)
    except BadSignature:
        raise HTTPException(400, "État OAuth invalide.")
    pending = db.get(OAuthPending, data.get("link", ""))
    if pending is None:
        raise HTTPException(400, "Autorisation introuvable.")
    try:
        profile = oauth.exchange(s, data["provider"], code)
        user = service.oauth_upsert(db, profile)
        if user.status == "banned":
            raise oauth.OAuthError("Compte suspendu.")
        pending.user_id = user.id
        db.commit()
        return _oauth_done_page(True, "Connexion réussie. Vous pouvez revenir à l'application.")
    except oauth.OAuthError as exc:
        pending.error = str(exc)[:255]
        db.commit()
        return _oauth_done_page(False, str(exc))


@app.post("/auth/oauth/claim")
def oauth_claim(body: ClaimIn, request: Request, db: Session = Depends(db_dep)):
    s = get_settings()
    pending = db.get(OAuthPending, body.link_code)
    if pending is None:
        raise HTTPException(404, "Lien inconnu.")
    if pending.error:
        err = pending.error
        db.delete(pending)
        db.commit()
        raise HTTPException(400, err)
    if pending.user_id is None:
        return Response(status_code=202)  # toujours en attente
    user = db.get(User, pending.user_id)
    ip = client_ip(request, s.trust_proxy)
    sess, token = service.create_session(db, s, user, ip, body.device, request.headers.get("user-agent", ""))
    service.log_event(db, user.id, "login", module="auth", action=f"login_{user.provider}", ip=ip, session_id=sess.id)
    db.delete(pending)
    db.commit()
    return TokenOut(token=token, user=UserOut.of(user)).model_dump()


def _oauth_done_page(ok: bool, message: str) -> HTMLResponse:
    color = "#d9ffe6" if ok else "#ff9a9a"
    return HTMLResponse(
        f"""<!doctype html><html lang=fr><head><meta charset=utf-8><title>FACE ANALYSE</title>
        <style>body{{background:#050505;color:#eee;font-family:system-ui;display:flex;height:100vh;margin:0;
        align-items:center;justify-content:center;text-align:center}}
        .c{{color:{color};letter-spacing:3px;font-weight:200;font-size:20px}}</style></head>
        <body><div><div class=c>{message}</div><p style="color:#777">Vous pouvez fermer cet onglet.</p></div></body></html>"""
    )


# ------------------------------------------------------------ Admin
@app.get("/", response_class=HTMLResponse)
def landing():
    s = get_settings()
    return HTMLResponse(
        f"""<!doctype html><html lang=fr><head><meta charset=utf-8><title>FACE ANALYSE Server</title>
        <style>body{{background:#050505;color:#eee;font-family:system-ui;max-width:640px;margin:60px auto;padding:0 20px}}
        a{{color:#fff}} code{{color:#9fd}}</style></head><body>
        <h1 style="font-weight:200;letter-spacing:4px">FACE ANALYSE · SERVER</h1>
        <p style="color:#888">Serveur de comptes, de sessions et de journalisation.</p>
        <p>Panneau d'administration : <a href="/admin">/admin</a></p>
        <p style="color:#666">Discord : {"activé" if s.discord_enabled else "non configuré"} ·
        Google : {"activé" if s.google_enabled else "non configuré"} ·
        Inscriptions : {"ouvertes" if s.open_registration else "fermées"}</p>
        </body></html>"""
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return HTMLResponse((WEB / "admin.html").read_text(encoding="utf-8"))


def _user_row(db: Session, s: Settings, u: User) -> dict:
    sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == u.id)).all()
    online = sum(1 for x in sessions if service.session_online(x, s))
    return {"id": u.id, "pseudo": u.pseudo, "email": u.email, "provider": u.provider, "role": u.role,
            "status": u.status, "has_avatar": u.avatar is not None,
            "created_at": u.created_at.isoformat(), "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "sessions": len(sessions), "online": online}


@app.get("/admin/api/overview")
def admin_overview(pair=Depends(admin_only), db: Session = Depends(db_dep)):
    s = get_settings()
    users = db.scalars(select(User)).all()
    sessions = db.scalars(select(AuthSession).where(AuthSession.revoked.is_(False))).all()
    online = sum(1 for x in sessions if service.session_online(x, s))
    return {"users": len(users), "banned": sum(1 for u in users if u.status == "banned"),
            "sessions_active": len(sessions), "online": online,
            "events": db.scalar(select(func.count(Event.id)))}


@app.get("/admin/api/users")
def admin_users(pair=Depends(admin_only), db: Session = Depends(db_dep), q: str = ""):
    s = get_settings()
    stmt = select(User).order_by(desc(User.last_login_at.is_(None)), desc(User.last_login_at))
    if q:
        stmt = stmt.where(User.pseudo.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    return [_user_row(db, s, u) for u in db.scalars(stmt)]


@app.get("/admin/api/users/{user_id}")
def admin_user_detail(user_id: int, pair=Depends(admin_only), db: Session = Depends(db_dep)):
    s = get_settings()
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Inconnu.")
    sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)
                          .order_by(desc(AuthSession.last_seen))).all()
    events = db.scalars(select(Event).where(Event.user_id == user_id).order_by(desc(Event.ts)).limit(100)).all()
    return {
        "user": _user_row(db, s, u),
        "sessions": [{
            "id": x.id, "ip": x.ip, "hostname": x.hostname, "os_name": x.os_name,
            "machine_id": x.machine_id, "app_version": x.app_version, "user_agent": x.user_agent,
            "geo": x.geo, "created_at": x.created_at.isoformat(), "last_seen": x.last_seen.isoformat(),
            "online": service.session_online(x, s), "revoked": x.revoked,
        } for x in sessions],
        "events": [{"ts": e.ts.isoformat(), "kind": e.kind, "module": e.module, "action": e.action,
                    "detail": e.detail, "ip": e.ip} for e in events],
    }


@app.get("/admin/api/sessions")
def admin_sessions(pair=Depends(admin_only), db: Session = Depends(db_dep), online: int = 0):
    s = get_settings()
    rows = db.scalars(select(AuthSession).where(AuthSession.revoked.is_(False))
                      .order_by(desc(AuthSession.last_seen))).all()
    out = []
    for x in rows:
        is_online = service.session_online(x, s)
        if online and not is_online:
            continue
        u = db.get(User, x.user_id)
        out.append({"id": x.id, "user_id": x.user_id, "pseudo": u.pseudo if u else "?", "ip": x.ip,
                    "hostname": x.hostname, "os_name": x.os_name, "machine_id": x.machine_id,
                    "app_version": x.app_version, "geo": x.geo, "last_seen": x.last_seen.isoformat(),
                    "online": is_online})
    return out


@app.get("/admin/api/events")
def admin_events(pair=Depends(admin_only), db: Session = Depends(db_dep), limit: int = 200,
                 user_id: int = 0, kind: str = ""):
    stmt = select(Event).order_by(desc(Event.ts)).limit(min(limit, 1000))
    if user_id:
        stmt = stmt.where(Event.user_id == user_id)
    if kind:
        stmt = stmt.where(Event.kind == kind)
    out = []
    for e in db.scalars(stmt):
        u = db.get(User, e.user_id)
        out.append({"ts": e.ts.isoformat(), "user_id": e.user_id, "pseudo": u.pseudo if u else "?",
                    "kind": e.kind, "module": e.module, "action": e.action, "detail": e.detail, "ip": e.ip})
    return out


@app.post("/admin/api/users/{user_id}/ban")
def admin_ban(user_id: int, payload: dict, pair=Depends(admin_only), db: Session = Depends(db_dep)):
    admin_user = pair[0]
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Inconnu.")
    if u.role == "admin" and u.id != admin_user.id:
        raise HTTPException(403, "Impossible de suspendre un autre administrateur.")
    u.status = "banned" if payload.get("banned") else "active"
    if u.status == "banned":
        for sx in db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)):
            sx.revoked = True
    db.commit()
    service.log_event(db, admin_user.id, "admin", module="admin",
                      action=("ban" if u.status == "banned" else "unban"), detail={"target": user_id})
    return {"status": u.status}


@app.post("/admin/api/users/{user_id}/role")
def admin_role(user_id: int, payload: dict, pair=Depends(admin_only), db: Session = Depends(db_dep)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Inconnu.")
    role = payload.get("role")
    if role not in ("user", "admin"):
        raise HTTPException(400, "Rôle invalide.")
    u.role = role
    db.commit()
    service.log_event(db, pair[0].id, "admin", module="admin", action="set_role",
                      detail={"target": user_id, "role": role})
    return {"role": role}


@app.post("/admin/api/sessions/{session_id}/revoke")
def admin_revoke(session_id: int, pair=Depends(admin_only), db: Session = Depends(db_dep)):
    sx = db.get(AuthSession, session_id)
    if sx is None:
        raise HTTPException(404, "Inconnue.")
    sx.revoked = True
    db.commit()
    service.log_event(db, pair[0].id, "admin", module="admin", action="revoke_session",
                      detail={"session": session_id, "target_user": sx.user_id})
    return {"status": "revoked"}


@app.delete("/admin/api/users/{user_id}")
def admin_delete(user_id: int, pair=Depends(admin_only), db: Session = Depends(db_dep)):
    if user_id == pair[0].id:
        raise HTTPException(400, "Vous ne pouvez pas supprimer votre propre compte admin.")
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Inconnu.")
    db.delete(u)
    db.commit()
    service.log_event(db, pair[0].id, "admin", module="admin", action="delete_user", detail={"target": user_id})
    return {"status": "deleted"}
