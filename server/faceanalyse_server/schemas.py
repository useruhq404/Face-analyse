"""Schémas Pydantic (entrées/sorties de l'API)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DeviceInfo(BaseModel):
    hostname: str = ""
    os_name: str = ""
    machine_id: str = ""
    app_version: str = ""
    user_agent: str = ""


_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    pseudo: str = Field(min_length=2, max_length=60)
    email: str | None = None
    password: str = Field(min_length=8, max_length=200)
    consent: bool
    device: DeviceInfo = DeviceInfo()

    @field_validator("email")
    @classmethod
    def _check_email(cls, v):
        import re

        if v and not re.match(_EMAIL_RE, v):
            raise ValueError("Adresse e-mail invalide.")
        return v or None


class LoginIn(BaseModel):
    identifier: str  # e-mail ou pseudo
    password: str
    device: DeviceInfo = DeviceInfo()


class ClaimIn(BaseModel):
    link_code: str
    device: DeviceInfo = DeviceInfo()


class EventIn(BaseModel):
    kind: str = "action"
    module: str = ""
    action: str = ""
    detail: dict = {}


class UserOut(BaseModel):
    id: int
    pseudo: str
    email: str | None
    provider: str
    role: str
    status: str
    has_avatar: bool

    @classmethod
    def of(cls, u) -> "UserOut":
        return cls(id=u.id, pseudo=u.pseudo, email=u.email, provider=u.provider, role=u.role,
                   status=u.status, has_avatar=u.avatar is not None)


class TokenOut(BaseModel):
    token: str
    user: UserOut
