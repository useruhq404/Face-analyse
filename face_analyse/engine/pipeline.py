"""Orchestrateur : détection -> embedding -> recherche d'identité.

Chaque étage reste remplaçable indépendamment ; ``FaceEngine`` ne fait que
les enchaîner et mesurer les temps d'exécution.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from face_analyse.core.config import EngineSettings
from face_analyse.core.errors import NoFaceError
from face_analyse.engine import quality as quality_mod
from face_analyse.engine.interfaces import FaceDetector, FaceEmbedder
from face_analyse.engine.matcher import IdentityMatcher, cosine_similarity
from face_analyse.engine.registry import create_detector, create_embedder
from face_analyse.engine.types import DetectedFace, FaceAnalysis, FaceEmbedding

log = logging.getLogger(__name__)


@dataclass
class Timings:
    detection_ms: float = 0.0
    embedding_ms: float = 0.0
    search_ms: float = 0.0
    extra: dict[str, float] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    similarity: float
    threshold: float
    above_threshold: bool
    face_a: FaceAnalysis
    face_b: FaceAnalysis

    @property
    def verdict(self) -> str:
        if self.above_threshold:
            return "Ressemblance au-dessus du seuil (même personne possible, non certaine)"
        return "Ressemblance insuffisante (personnes probablement différentes, non certain)"


class FaceEngine:
    def __init__(self, detector: FaceDetector, embedder: FaceEmbedder, matcher: IdentityMatcher, flip_tta: bool = True):
        self.detector = detector
        self.embedder = embedder
        self.matcher = matcher
        self.flip_tta = flip_tta
        self.last_timings = Timings()

    @classmethod
    def from_settings(cls, s: EngineSettings) -> "FaceEngine":
        detector = create_detector(
            s.detector,
            score_threshold=s.detection_score,
            min_face_size=max(10, s.min_face_size // 2),
            enhance_lighting=s.enhance_lighting,
        )
        embedder = create_embedder(s.embedder)
        matcher = IdentityMatcher(s.match_threshold, s.ambiguity_margin)
        log.info("Moteur chargé : détecteur=%s embedder=%s seuil=%.3f", detector.name, embedder.model_id, s.match_threshold)
        return cls(detector, embedder, matcher)

    # ------------------------------------------------------------------
    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        t0 = time.perf_counter()
        faces = self.detector.detect(image)
        self.last_timings.detection_ms = (time.perf_counter() - t0) * 1000
        return faces

    def describe(self, image: np.ndarray, face: DetectedFace) -> FaceAnalysis:
        t0 = time.perf_counter()
        aligned = self.embedder.align(image, face)
        q = quality_mod.assess(face, aligned)
        try:
            emb = self.embedder.embed(image, face, flip_tta=self.flip_tta)
        except ValueError as exc:
            log.warning("Embedding impossible : %s", exc)
            emb = None
        self.last_timings.embedding_ms += (time.perf_counter() - t0) * 1000
        return FaceAnalysis(face=face, embedding=emb, quality=q)

    def analyze(self, image: np.ndarray, identify: bool = True, top_k: int = 5) -> list[FaceAnalysis]:
        """Détecte TOUS les visages (connus ou non), puis cherche leur identité."""
        self.last_timings = Timings()
        faces = self.detect(image)
        results = [self.describe(image, f) for f in faces]
        if identify:
            t0 = time.perf_counter()
            for r in results:
                if r.embedding is not None:
                    r.decision = self.matcher.search(r.embedding, top_k=top_k)
            self.last_timings.search_ms = (time.perf_counter() - t0) * 1000
        return results

    def embed_single(self, image: np.ndarray) -> tuple[FaceAnalysis, int]:
        """Pour l'enrôlement : retourne le plus grand visage et le nombre détecté."""
        faces = self.detect(image)
        if not faces:
            raise NoFaceError()
        analysis = self.describe(image, faces[0])
        if analysis.embedding is None:
            raise NoFaceError("Visage détecté mais non exploitable (alignement impossible).")
        return analysis, len(faces)

    def compare(self, image_a: np.ndarray, image_b: np.ndarray) -> ComparisonResult:
        a, _ = self.embed_single(image_a)
        b, _ = self.embed_single(image_b)
        assert a.embedding is not None and b.embedding is not None
        sim = cosine_similarity(a.embedding, b.embedding)
        return ComparisonResult(sim, self.matcher.threshold, sim >= self.matcher.threshold, a, b)

    def embedding_for(self, image: np.ndarray, face: DetectedFace) -> FaceEmbedding:
        return self.embedder.embed(image, face, flip_tta=self.flip_tta)
