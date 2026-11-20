"""Prétraitements image : chargement robuste (chemins Unicode Windows),
redimensionnement et correction de luminosité adaptative."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from face_analyse.core.errors import ImageError

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
MAX_PIXELS = 50_000_000


def load_image(path: str | Path) -> np.ndarray:
    """Charge une image en BGR.

    ``cv2.imread`` échoue sur les chemins non-ASCII sous Windows ; on lit
    donc les octets puis ``cv2.imdecode``.
    """
    p = Path(path)
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImageError(f"Format non pris en charge : {p.suffix or 'sans extension'}")
    try:
        data = np.fromfile(str(p), dtype=np.uint8)
    except OSError as exc:
        raise ImageError(f"Lecture impossible : {p.name}") from exc
    return decode_image(data.tobytes(), name=p.name)


def decode_image(data: bytes, name: str = "image") -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise ImageError(f"Image illisible : {name}")
    if img.shape[0] * img.shape[1] > MAX_PIXELS:
        raise ImageError("Image trop grande (> 50 mégapixels)")
    return img


def encode_jpeg(image_bgr: np.ndarray, quality: int = 92) -> bytes:
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ImageError("Encodage JPEG impossible")
    return buf.tobytes()


def resize_max_side(image: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    """Réduit l'image si nécessaire ; retourne (image, facteur appliqué)."""
    h, w = image.shape[:2]
    scale = min(1.0, max_side / float(max(h, w)))
    if scale >= 1.0:
        return image, 1.0
    resized = cv2.resize(image, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA)
    return resized, scale


def mean_luminance(image_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    return float(gray.mean())


def enhance_low_light(image_bgr: np.ndarray, target: float = 110.0) -> np.ndarray:
    """Correction gamma + CLAHE pour les images sombres ou surexposées.

    N'agit que si la luminance moyenne s'écarte nettement de la normale,
    pour ne pas dégrader les images correctement exposées.
    """
    lum = mean_luminance(image_bgr)
    if 70.0 <= lum <= 190.0:
        return image_bgr
    lum = min(max(lum, 1.0), 254.0)
    gamma = np.log(target / 255.0) / np.log(lum / 255.0)
    gamma = float(np.clip(gamma, 0.3, 3.0))
    lut = np.clip(((np.arange(256) / 255.0) ** gamma) * 255.0, 0, 255).astype(np.uint8)
    out = cv2.LUT(image_bgr, lut)
    lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    l_chan = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l_chan)
    return cv2.cvtColor(cv2.merge((l_chan, a_chan, b_chan)), cv2.COLOR_LAB2BGR)
