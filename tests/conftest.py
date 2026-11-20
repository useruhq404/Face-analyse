"""Fixtures partagées : dossier utilisateur isolé, faux moteur, images de test."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from face_analyse.core.errors import NoFaceError
from face_analyse.engine.types import DetectedFace, FaceAnalysis, FaceEmbedding, FaceQuality

LFW_ENV = "FACE_ANALYSE_LFW"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("FACE_ANALYSE_HOME", str(home))
    return home


def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def make_face(x=10.0, y=10.0, w=80.0, h=100.0, score=0.95) -> DetectedFace:
    lm = np.array([[x + 0.3 * w, y + 0.4 * h], [x + 0.7 * w, y + 0.4 * h], [x + 0.5 * w, y + 0.6 * h],
                   [x + 0.35 * w, y + 0.8 * h], [x + 0.65 * w, y + 0.8 * h]], np.float32)
    return DetectedFace(x, y, w, h, lm, score)


class FakeEngine:
    """Moteur déterministe : l'embedding est dérivé de la couleur moyenne de l'image.

    Permet de tester la base de données sans modèles ni vrais visages.
    """

    def __init__(self, dim: int = 8, model_id: str = "fake-1"):
        self.embedder = SimpleNamespace(model_id=model_id)
        self.dim = dim

    def embed_single(self, image):
        if image.mean() < 1.0:
            raise NoFaceError()
        rng = np.random.default_rng(int(image.mean() * 1000) % (2**32))
        vec = unit(rng.normal(size=self.dim))
        face = make_face()
        q = FaceQuality(80, 100, 120, 0.05, 0.95, 0.8, [])
        return FaceAnalysis(face, FaceEmbedding(vec, self.embedder.model_id), q), 1


@pytest.fixture
def fake_engine():
    return FakeEngine()


@pytest.fixture
def lfw_root() -> Path:
    root = os.environ.get(LFW_ENV)
    if not root:
        pytest.skip(f"jeu LFW non disponible (définir {LFW_ENV})")
    path = Path(root)
    images = path / "lfw_funneled" if (path / "lfw_funneled").is_dir() else path / "lfw"
    if not images.is_dir():
        pytest.skip("dossier LFW invalide")
    return images
