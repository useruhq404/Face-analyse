"""Accès aux données : personnes, photos de référence, embeddings, historique.

Toute la biométrie est chiffrée. La suppression d'une personne efface en
cascade ses photos et embeddings, puis ``VACUUM`` réécrit le fichier ; avec
``PRAGMA secure_delete=ON`` les pages libérées sont remises à zéro.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, event, func, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from face_analyse.core.errors import ConsentError, DatabaseError, NoFaceError
from face_analyse.core.paths import database_path
from face_analyse.database.crypto import Vault
from face_analyse.database.models import Base, EmbeddingRecord, HistoryEntry, Person, ReferencePhoto, Secret
from face_analyse.engine.matcher import GalleryEntry
from face_analyse.engine.pipeline import FaceEngine
from face_analyse.engine.preprocessing import decode_image, encode_jpeg, resize_max_side

log = logging.getLogger(__name__)

CONSENT_TEXT = (
    "La personne enregistrée a donné son consentement explicite et éclairé à l'enregistrement "
    "de ses photographies et de leurs empreintes faciales (données biométriques, art. 9 RGPD) "
    "dans cette base locale, aux seules fins de comparaison faciale. Elle peut demander à tout "
    "moment la suppression complète de ses données."
)
MAX_STORED_SIDE = 1600


@dataclass(frozen=True)
class PersonSummary:
    id: int
    first_name: str
    last_name: str
    notes: str
    photo_count: int
    consent_at: datetime
    created_at: datetime

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class PhotoSummary:
    id: int
    person_id: int
    quality: float
    created_at: datetime
    thumbnail_jpeg: bytes


class Repository:
    def __init__(self, db_path: Path | None = None, vault: Vault | None = None):
        self.db_path = Path(db_path or database_path())
        self.vault = vault or Vault()
        self._engine = create_engine(f"sqlite:///{self.db_path.as_posix()}", future=True)

        @event.listens_for(self._engine, "connect")
        def _pragmas(dbapi_conn, _):  # pragma: no cover - simple configuration
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA secure_delete=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        self._lock = threading.RLock()

    def session(self) -> Session:
        return self._session_factory()

    def close(self) -> None:
        self._engine.dispose()

    # ------------------------------------------------------------ personnes
    def add_person(self, first_name: str, last_name: str, consent: bool, notes: str = "") -> int:
        if not consent:
            raise ConsentError()
        first_name, last_name = first_name.strip(), last_name.strip()
        if not first_name and not last_name:
            raise DatabaseError("Le nom ou le prénom est obligatoire.")
        with self._lock, self.session() as s:
            p = Person(first_name=first_name, last_name=last_name, notes=notes.strip(),
                       consent_at=datetime.now(timezone.utc), consent_text=CONSENT_TEXT)
            s.add(p)
            s.commit()
            self.log_history("database", "person_added", f"Personne ajoutée : {p.display_name}", {"person_id": p.id})
            return p.id

    def update_person(self, person_id: int, first_name: str, last_name: str, notes: str) -> None:
        with self._lock, self.session() as s:
            p = s.get(Person, person_id)
            if p is None:
                raise DatabaseError("Personne introuvable.")
            p.first_name, p.last_name, p.notes = first_name.strip(), last_name.strip(), notes.strip()
            s.commit()
        self.log_history("database", "person_updated", f"Personne modifiée : {first_name} {last_name}", {"person_id": person_id})

    def delete_person(self, person_id: int) -> None:
        """Suppression complète : personne, photos, embeddings, traces dans
        l'historique (qui mentionne son nom), puis VACUUM."""
        with self._lock, self.session() as s:
            p = s.get(Person, person_id)
            if p is None:
                return
            name = p.display_name
            s.delete(p)
            # L'historique ne doit pas conserver le nom d'une personne supprimée.
            s.query(HistoryEntry).filter(or_(
                HistoryEntry.summary.contains(name),
                HistoryEntry.details_json.contains(name),
                HistoryEntry.details_json.contains(f'"person_id": {person_id},'),
                HistoryEntry.details_json.contains(f'"person_id": {person_id}}}'),
            )).delete(synchronize_session=False)
            s.commit()
        self.log_history("database", "person_deleted", "Suppression complète des données d'une personne",
                         {"deleted_person_ref": person_id})
        self._vacuum()

    def list_people(self, query: str = "") -> list[PersonSummary]:
        with self.session() as s:
            stmt = (
                select(Person, func.count(ReferencePhoto.id))
                .outerjoin(ReferencePhoto)
                .group_by(Person.id)
                .order_by(Person.last_name, Person.first_name)
            )
            q = query.strip()
            if q:
                like = f"%{q}%"
                stmt = stmt.where(or_(Person.first_name.ilike(like), Person.last_name.ilike(like), Person.notes.ilike(like)))
            return [
                PersonSummary(p.id, p.first_name, p.last_name, p.notes, int(n), p.consent_at, p.created_at)
                for p, n in s.execute(stmt).all()
            ]

    def get_person(self, person_id: int) -> PersonSummary | None:
        return next((p for p in self.list_people() if p.id == person_id), None)

    # ------------------------------------------------------------ photos
    def add_photo(self, person_id: int, image_bgr: np.ndarray, engine: FaceEngine) -> tuple[int, list[str]]:
        """Enrôle une photo : détection, embedding, stockage chiffré.

        Retourne (id photo, avertissements qualité).
        """
        analysis, n_faces = engine.embed_single(image_bgr)
        warnings = list(analysis.quality.warnings)
        if n_faces > 1:
            warnings.insert(0, f"{n_faces} visages détectés : le plus grand a été utilisé.")
        assert analysis.embedding is not None

        stored, _ = resize_max_side(image_bgr, MAX_STORED_SIDE)
        jpeg = encode_jpeg(stored)
        x, y, w, h = analysis.face.box
        pad = int(0.25 * max(w, h))
        H, W = image_bgr.shape[:2]
        crop = image_bgr[max(0, y - pad): min(H, y + h + pad), max(0, x - pad): min(W, x + w + pad)]
        thumb, _ = resize_max_side(crop, 160)

        with self._lock, self.session() as s:
            if s.get(Person, person_id) is None:
                raise DatabaseError("Personne introuvable.")
            photo = ReferencePhoto(
                person_id=person_id,
                image_enc=self.vault.encrypt(jpeg),
                thumb_enc=self.vault.encrypt(encode_jpeg(thumb, 88)),
                sha256=hashlib.sha256(jpeg).hexdigest(),
                quality=analysis.quality.score,
                face_box=json.dumps([x, y, w, h]),
            )
            photo.embeddings.append(EmbeddingRecord(
                model_id=analysis.embedding.model_id,
                vector_enc=self.vault.encrypt(analysis.embedding.vector.astype(np.float32).tobytes()),
            ))
            s.add(photo)
            s.commit()
            pid = photo.id
        self.log_history("database", "photo_added", "Photo de référence ajoutée", {"person_id": person_id, "photo_id": pid})
        return pid, warnings

    def delete_photo(self, photo_id: int) -> None:
        with self._lock, self.session() as s:
            ph = s.get(ReferencePhoto, photo_id)
            if ph is not None:
                s.delete(ph)
                s.commit()
        self._vacuum()

    def list_photos(self, person_id: int) -> list[PhotoSummary]:
        with self.session() as s:
            rows = s.scalars(select(ReferencePhoto).where(ReferencePhoto.person_id == person_id).order_by(ReferencePhoto.id)).all()
            return [PhotoSummary(r.id, r.person_id, r.quality, r.created_at, self.vault.decrypt(r.thumb_enc)) for r in rows]

    def photo_image(self, photo_id: int) -> np.ndarray:
        with self.session() as s:
            ph = s.get(ReferencePhoto, photo_id)
            if ph is None:
                raise DatabaseError("Photo introuvable.")
            return decode_image(self.vault.decrypt(ph.image_enc))

    # ------------------------------------------------------------ galerie
    def gallery(self, model_id: str) -> list[GalleryEntry]:
        with self.session() as s:
            rows = s.execute(
                select(EmbeddingRecord, ReferencePhoto.person_id, Person.first_name, Person.last_name)
                .join(ReferencePhoto, EmbeddingRecord.photo_id == ReferencePhoto.id)
                .join(Person, ReferencePhoto.person_id == Person.id)
                .where(EmbeddingRecord.model_id == model_id)
            ).all()
        out = []
        for rec, pid, fn, ln in rows:
            vec = np.frombuffer(self.vault.decrypt(rec.vector_enc), dtype=np.float32).copy()
            out.append(GalleryEntry(rec.photo_id, pid, f"{fn} {ln}".strip(), vec, rec.model_id))
        return out

    def photos_missing_model(self, model_id: str) -> int:
        with self.session() as s:
            have = select(EmbeddingRecord.photo_id).where(EmbeddingRecord.model_id == model_id)
            return int(s.scalar(select(func.count(ReferencePhoto.id)).where(ReferencePhoto.id.not_in(have))) or 0)

    def reencode_all(self, engine: FaceEngine, progress=None) -> tuple[int, int]:
        """Recalcule les embeddings avec le modèle courant (changement de modèle).

        Les photos chiffrées étant conservées, aucun ré-enrôlement manuel n'est
        nécessaire. Retourne (réussites, échecs).
        """
        model_id = engine.embedder.model_id
        with self.session() as s:
            have = select(EmbeddingRecord.photo_id).where(EmbeddingRecord.model_id == model_id)
            ids = list(s.scalars(select(ReferencePhoto.id).where(ReferencePhoto.id.not_in(have))))
        ok = fail = 0
        for i, pid in enumerate(ids):
            try:
                img = self.photo_image(pid)
                analysis, _ = engine.embed_single(img)
                assert analysis.embedding is not None
                with self._lock, self.session() as s:
                    s.add(EmbeddingRecord(photo_id=pid, model_id=model_id,
                                          vector_enc=self.vault.encrypt(analysis.embedding.vector.astype(np.float32).tobytes())))
                    s.commit()
                ok += 1
            except (NoFaceError, DatabaseError) as exc:
                log.warning("Ré-encodage photo %s impossible : %s", pid, exc)
                fail += 1
            if progress:
                progress(i + 1, len(ids))
        return ok, fail

    # ------------------------------------------------------------ historique
    def log_history(self, module: str, action: str, summary: str, details: dict | None = None) -> None:
        try:
            with self._lock, self.session() as s:
                s.add(HistoryEntry(module=module, action=action, summary=summary,
                                   details_json=json.dumps(details or {}, ensure_ascii=False, default=str)))
                s.commit()
        except Exception:  # noqa: BLE001 - l'historique ne doit jamais bloquer
            log.exception("Écriture de l'historique impossible")

    def history(self, module: str | None = None, limit: int = 500) -> list[HistoryEntry]:
        with self.session() as s:
            stmt = select(HistoryEntry).order_by(HistoryEntry.timestamp.desc()).limit(limit)
            if module:
                stmt = stmt.where(HistoryEntry.module == module)
            return list(s.scalars(stmt))

    def clear_history(self) -> None:
        with self._lock, self.session() as s:
            s.query(HistoryEntry).delete()
            s.commit()
        self._vacuum()

    # ------------------------------------------------------------ agrégats (OVERVIEW)
    def activity_by_day(self, days: int = 14) -> list[tuple[str, int]]:
        """Nombre d'actions par jour, sur les N derniers jours (jours sans activité inclus)."""
        from datetime import date, timedelta

        today = date.today()
        buckets = {(today - timedelta(days=i)).isoformat(): 0 for i in range(days)}
        with self.session() as s:
            rows = s.scalars(select(HistoryEntry.timestamp).order_by(HistoryEntry.timestamp.desc()).limit(5000)).all()
        for ts in rows:
            key = (ts.astimezone().date() if ts.tzinfo else ts.date()).isoformat()
            if key in buckets:
                buckets[key] += 1
        return [(k, buckets[k]) for k in sorted(buckets)]

    def module_usage(self) -> list[tuple[str, int]]:
        """Répartition des actions par module (toutes périodes)."""
        with self.session() as s:
            rows = s.execute(
                select(HistoryEntry.module, func.count(HistoryEntry.id))
                .group_by(HistoryEntry.module).order_by(func.count(HistoryEntry.id).desc())
            ).all()
        return [(m or "autre", int(n)) for m, n in rows]

    def history_count(self) -> int:
        with self.session() as s:
            return int(s.scalar(select(func.count(HistoryEntry.id))) or 0)

    # ------------------------------------------------------------ secrets
    def set_secret(self, name: str, value: str) -> None:
        with self._lock, self.session() as s:
            if value:
                s.merge(Secret(name=name, value_enc=self.vault.encrypt(value.encode())))
            else:
                obj = s.get(Secret, name)
                if obj:
                    s.delete(obj)
            s.commit()

    def get_secret(self, name: str) -> str:
        with self.session() as s:
            obj = s.get(Secret, name)
            return self.vault.decrypt(obj.value_enc).decode() if obj else ""

    # ------------------------------------------------------------ maintenance
    def stats(self) -> dict[str, int]:
        with self.session() as s:
            return {
                "persons": int(s.scalar(select(func.count(Person.id))) or 0),
                "photos": int(s.scalar(select(func.count(ReferencePhoto.id))) or 0),
                "embeddings": int(s.scalar(select(func.count(EmbeddingRecord.id))) or 0),
            }

    def wipe_biometrics(self) -> None:
        """Efface toutes les personnes, photos et embeddings."""
        with self._lock, self.session() as s:
            s.query(EmbeddingRecord).delete()
            s.query(ReferencePhoto).delete()
            s.query(Person).delete()
            s.commit()
        self._vacuum()
        self.log_history("database", "wipe", "Effacement complet de la base biométrique")

    def _vacuum(self) -> None:
        with self._lock, self._engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.exec_driver_sql("VACUUM")
