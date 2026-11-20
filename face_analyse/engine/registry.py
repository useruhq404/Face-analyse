"""Catalogue des modèles et vérification d'intégrité (SHA-256).

Pour ajouter un modèle : déclarer une ``ModelSpec`` et une fabrique.
Les modèles ONNX déposés dans le dossier utilisateur ``models/`` sont
automatiquement proposés comme embedders ``onnx:<nom_fichier>``.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from face_analyse.core.errors import ModelError
from face_analyse.core.paths import models_dir, user_models_dir
from face_analyse.engine.interfaces import FaceDetector, FaceEmbedder

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    filename: str
    sha256: str
    url: str
    license: str
    description: str


DETECTORS: dict[str, ModelSpec] = {
    "yunet": ModelSpec(
        key="yunet",
        filename="face_detection_yunet_2023mar.onnx",
        sha256="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        url="https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
        license="MIT",
        description="YuNet 2023 (OpenCV Zoo) — détecteur léger, 5 points de repère",
    ),
}

EMBEDDERS: dict[str, ModelSpec] = {
    "sface": ModelSpec(
        key="sface",
        filename="face_recognition_sface_2021dec.onnx",
        sha256="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        url="https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
        license="Apache-2.0",
        description="SFace 2021 (OpenCV Zoo) — embeddings 128-D",
    ),
}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def locate(spec: ModelSpec, verify: bool = True) -> Path:
    """Cherche le modèle (ressources embarquées puis dossier utilisateur)."""
    for folder in (models_dir(), user_models_dir()):
        candidate = folder / spec.filename
        if candidate.is_file():
            if verify and sha256_file(candidate) != spec.sha256:
                raise ModelError(f"Empreinte SHA-256 invalide pour {spec.filename} : fichier corrompu ou modifié")
            return candidate
    raise ModelError(
        f"Modèle manquant : {spec.filename}. Lancez « python scripts/download_models.py »."
    )


def custom_onnx_models() -> list[Path]:
    return sorted(user_models_dir().glob("*.onnx"))


def available_embedders() -> list[str]:
    return list(EMBEDDERS) + [f"onnx:{p.name}" for p in custom_onnx_models()]


def create_detector(key: str, **kwargs) -> FaceDetector:
    if key == "yunet":
        from face_analyse.engine.detectors.yunet import YuNetDetector

        return YuNetDetector(locate(DETECTORS["yunet"]), **kwargs)
    raise ModelError(f"Détecteur inconnu : {key}")


def create_embedder(key: str) -> FaceEmbedder:
    if key == "sface":
        from face_analyse.engine.embedders.sface import SFaceEmbedder

        return SFaceEmbedder(locate(EMBEDDERS["sface"]))
    if key.startswith("onnx:"):
        from face_analyse.engine.embedders.onnx_arcface import OnnxArcFaceEmbedder

        return OnnxArcFaceEmbedder(user_models_dir() / key.split(":", 1)[1])
    raise ModelError(f"Modèle d'embedding inconnu : {key}")
