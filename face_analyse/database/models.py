"""Schéma SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    photos: Mapped[list["ReferencePhoto"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class ReferencePhoto(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    image_enc: Mapped[bytes] = mapped_column(LargeBinary)  # JPEG chiffré
    thumb_enc: Mapped[bytes] = mapped_column(LargeBinary)  # visage recadré chiffré
    sha256: Mapped[str] = mapped_column(String(64))
    quality: Mapped[float] = mapped_column(Float, default=0.0)
    face_box: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    person: Mapped[Person] = relationship(back_populates="photos")
    embeddings: Mapped[list["EmbeddingRecord"]] = relationship(
        back_populates="photo", cascade="all, delete-orphan", passive_deletes=True
    )


class EmbeddingRecord(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str] = mapped_column(String(80), index=True)
    vector_enc: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    photo: Mapped[ReferencePhoto] = relationship(back_populates="embeddings")


class HistoryEntry(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    module: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    details_json: Mapped[str] = mapped_column(Text, default="{}")


class Secret(Base):
    __tablename__ = "secrets"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_enc: Mapped[bytes] = mapped_column(LargeBinary)
