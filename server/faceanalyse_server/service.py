"""Logique métier réutilisable (indépendante de FastAPI, donc testable)."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from faceanalyse_server import geo
from faceanalyse_server.config import Settings
from faceanalyse_server.models import AuthSession, Event, User, utcnow
from faceanalyse_server.oauth import OAuthProfile
from faceanalyse_server.schemas import DeviceInfo
from faceanalyse_server.security import hash_password, new_session_token, token_hash


def bootstrap_admin(db: Session, settings: Settings) -> None:
    """Crée ou promeut le compte propriétaire au démarrage."""
    if not settings.admin_email:
        return
    email = settings.admin_email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        user = User(pseudo=settings.admin_pseudo, email=email, provider="local",
                    role="admin", status="active", consent_at=utcnow())
        if settings.admin_password:
            user.password_hash = hash_password(settings.admin_password)
        db.add(user)
    else:
        user.role = "admin"
        user.status = "active"
        if settings.admin_password:
            user.password_hash = hash_password(settings.admin_password)
    db.commit()


def create_session(db: Session, settings: Settings, user: User, ip: str, device: DeviceInfo,
                   user_agent: str = "") -> tuple[AuthSession, str]:
    token = new_session_token()
    sess = AuthSession(
        user_id=user.id, token_hash=token_hash(token), ip=ip,
        user_agent=(device.user_agent or user_agent)[:255],
        hostname=device.hostname[:120], os_name=device.os_name[:80],
        machine_id=device.machine_id[:80], app_version=device.app_version[:40],
        geo=geo.lookup(ip),
    )
    user.last_login_at = utcnow()
    db.add(sess)
    db.commit()
    return sess, token


def log_event(db: Session, user_id: int, kind: str, *, module: str = "", action: str = "",
              detail: dict | None = None, ip: str = "", session_id: int | None = None) -> None:
    db.add(Event(user_id=user_id, session_id=session_id, kind=kind, module=module[:40],
                 action=action[:80], detail=detail or {}, ip=ip))
    db.commit()


def _as_utc(dt):
    """SQLite renvoie des datetimes naïfs : on les suppose en UTC."""
    from datetime import timezone

    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def session_online(sess: AuthSession, settings: Settings) -> bool:
    if sess.revoked:
        return False
    age = (utcnow() - _as_utc(sess.last_seen)).total_seconds()
    return age <= settings.online_window_s


def oauth_upsert(db: Session, profile: OAuthProfile) -> User:
    user = db.scalar(select(User).where(User.provider == profile.provider,
                                        User.provider_id == profile.provider_id))
    if user is None and profile.email:
        user = db.scalar(select(User).where(func.lower(User.email) == profile.email.lower()))
    if user is None:
        user = User(pseudo=profile.pseudo[:60], email=profile.email, provider=profile.provider,
                    provider_id=profile.provider_id, role="user", status="active", consent_at=utcnow())
        db.add(user)
    else:
        user.provider, user.provider_id = profile.provider, profile.provider_id
        if profile.email and not user.email:
            user.email = profile.email
        if user.consent_at is None:
            user.consent_at = utcnow()
    db.commit()
    return user


def purge_expired(db: Session, settings: Settings) -> None:
    cutoff = utcnow() - timedelta(days=settings.session_ttl_days)
    for sess in db.scalars(select(AuthSession).where(AuthSession.revoked.is_(False))):
        if _as_utc(sess.last_seen) < cutoff:
            sess.revoked = True
    db.commit()


def new_link_code() -> str:
    return secrets.token_urlsafe(18)
