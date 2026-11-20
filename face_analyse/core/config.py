"""Paramètres persistants (JSON dans le dossier utilisateur).

Les valeurs par défaut du seuil proviennent du benchmark LFW
(voir ``docs/BENCHMARK.md``) et peuvent être modifiées dans SETTINGS.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from face_analyse.core.paths import user_data_dir

log = logging.getLogger(__name__)


@dataclass
class EngineSettings:
    detector: str = "yunet"
    embedder: str = "sface"
    detection_score: float = 0.80
    # Seuil de similarité cosinus. En-dessous : UNKNOWN.
    # Valeur calibrée sur LFW (cf. docs/BENCHMARK.md) — à ajuster selon
    # le taux de faux positifs acceptable.
    match_threshold: float = 0.50
    # Écart minimal entre la 1re et la 2e identité pour ne pas signaler
    # d'ambiguïté.
    ambiguity_margin: float = 0.05
    min_face_size: int = 40
    enhance_lighting: bool = True
    top_k: int = 5


@dataclass
class CameraSettings:
    device_index: int = 0
    mirror: bool = True
    recognition_interval: int = 5  # reconnaissance toutes les N images
    camera_consent_given: bool = False


@dataclass
class OsintSettings:
    timeout_s: float = 10.0
    enabled_sources: list[str] = field(default_factory=list)  # vide = toutes
    username_check: bool = True
    ai_model: str = "claude-opus-5-5"


@dataclass
class Settings:
    engine: EngineSettings = field(default_factory=EngineSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
    osint: OsintSettings = field(default_factory=OsintSettings)

    # ------------------------------------------------------------------
    @staticmethod
    def path() -> Path:
        return user_data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        p = cls.path()
        s = cls()
        if not p.exists():
            return s
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Paramètres illisibles (%s), valeurs par défaut utilisées", exc)
            return s
        for section_name in ("engine", "camera", "osint"):
            section = getattr(s, section_name)
            known = {f.name for f in fields(section)}
            for key, value in (raw.get(section_name) or {}).items():
                if key in known:
                    setattr(section, key, value)
        return s

    def save(self) -> None:
        p = self.path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
