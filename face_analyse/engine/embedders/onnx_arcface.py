"""Embedder générique pour tout modèle ONNX de type ArcFace (entrée 112×112).

Permet de brancher un autre modèle (ArcFace R100, AdaFace, MagFace…)
en déposant simplement le fichier ``.onnx`` dans le dossier
``models`` de l'utilisateur et en le sélectionnant dans SETTINGS —
sans recompiler l'application.

Vérifiez la licence du modèle choisi : beaucoup de poids publics sont
réservés à un usage non commercial.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from face_analyse.core.errors import ModelError
from face_analyse.engine.alignment import align_5pts
from face_analyse.engine.interfaces import FaceEmbedder
from face_analyse.engine.types import DetectedFace


class OnnxArcFaceEmbedder(FaceEmbedder):
    default_threshold = 0.30

    def __init__(self, model_path: Path, input_size: int = 112, mean: float = 127.5, std: float = 127.5, rgb: bool = True):
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - dépend de l'installation
            raise ModelError("onnxruntime n'est pas installé") from exc
        path = Path(model_path)
        if not path.is_file():
            raise ModelError(f"Modèle ONNX introuvable : {path}")
        try:
            self._sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        except Exception as exc:  # noqa: BLE001 - onnxruntime lève des types variés
            raise ModelError(f"Modèle ONNX invalide : {path.name}") from exc
        inp = self._sess.get_inputs()[0]
        self._input_name = inp.name
        self._nchw = len(inp.shape) == 4 and inp.shape[1] == 3
        self.input_size = input_size
        self.mean, self.std, self.rgb = mean, std, rgb
        out_shape = self._sess.get_outputs()[0].shape
        self.dim = int(out_shape[-1]) if isinstance(out_shape[-1], int) else 0
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        self.model_id = f"onnx-{path.stem}-{digest}"

    def align(self, image_bgr: np.ndarray, face: DetectedFace) -> np.ndarray:
        return align_5pts(image_bgr, face.landmarks, self.input_size)

    def embed_aligned(self, aligned_bgr: np.ndarray) -> np.ndarray:
        img = aligned_bgr[:, :, ::-1] if self.rgb else aligned_bgr
        x = (img.astype(np.float32) - self.mean) / self.std
        x = x.transpose(2, 0, 1)[None] if self._nchw else x[None]
        return self._sess.run(None, {self._input_name: np.ascontiguousarray(x)})[0].reshape(-1)
