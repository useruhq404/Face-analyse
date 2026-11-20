"""Moteur SQLAlchemy et session de base."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from faceanalyse_server.config import get_settings
from faceanalyse_server.models import Base

_engine = None
_Session: sessionmaker | None = None


def init_engine():
    global _engine, _Session
    if _engine is not None:
        return
    url = get_settings().db_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, future=True, connect_args=connect_args)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _fk(dbapi_conn, _):  # pragma: no cover
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(_engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    if _Session is None:
        init_engine()
    assert _Session is not None
    with _Session() as session:
        yield session


def new_session() -> Session:
    if _Session is None:
        init_engine()
    assert _Session is not None
    return _Session()
