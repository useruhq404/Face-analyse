"""Analyse des métadonnées d'image (EXIF / GPS) — hors ligne, local.

Lit les informations déjà présentes dans un fichier image que l'utilisateur
possède ou est autorisé à analyser : coordonnées GPS, date de prise de vue,
appareil (marque/modèle/logiciel). Aucune donnée n'est envoyée ; aucun scraping.

Prudence : un même modèle d'appareil ne prouve pas que deux photos viennent du
même téléphone ou de la même personne. Les coordonnées EXIF peuvent être
absentes, approximatives ou falsifiées. À présenter comme un INDICE, pas une preuve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS


@dataclass
class GeoPoint:
    lat: float
    lon: float

    @property
    def map_url(self) -> str:
        return f"https://www.openstreetmap.org/?mlat={self.lat:.6f}&mlon={self.lon:.6f}#map=15/{self.lat:.5f}/{self.lon:.5f}"


@dataclass
class ImageMeta:
    path: str
    width: int = 0
    height: int = 0
    gps: Optional[GeoPoint] = None
    datetime_original: str = ""
    camera_make: str = ""
    camera_model: str = ""
    software: str = ""
    other: dict[str, str] = field(default_factory=dict)
    error: str = ""

    @property
    def device_fingerprint(self) -> str:
        """Signature d'appareil (marque-modèle-logiciel) pour corréler des photos."""
        parts = [self.camera_make, self.camera_model, self.software]
        return " · ".join(p for p in parts if p) or "inconnu"

    @property
    def has_exif(self) -> bool:
        return bool(self.datetime_original or self.camera_make or self.camera_model or self.gps or self.other)


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        try:  # IFDRational / (num, den)
            return value[0] / value[1]
        except Exception:  # noqa: BLE001
            return None


def dms_to_decimal(dms, ref: str) -> Optional[float]:
    """Convertit (degrés, minutes, secondes) + référence (N/S/E/W) en décimal."""
    try:
        d, m, s = (_to_float(x) or 0.0 for x in dms)
    except (TypeError, ValueError):
        return None
    dec = d + m / 60.0 + s / 3600.0
    if str(ref).upper() in ("S", "W"):
        dec = -dec
    return round(dec, 6)


def _extract_gps(gps_ifd: dict) -> Optional[GeoPoint]:
    data = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
    lat, lat_ref = data.get("GPSLatitude"), data.get("GPSLatitudeRef")
    lon, lon_ref = data.get("GPSLongitude"), data.get("GPSLongitudeRef")
    if not (lat and lon and lat_ref and lon_ref):
        return None
    la = dms_to_decimal(lat, lat_ref)
    lo = dms_to_decimal(lon, lon_ref)
    if la is None or lo is None:
        return None
    return GeoPoint(la, lo)


#: tags EXIF retenus (hors GPS) → libellé
_KEEP = {"DateTimeOriginal": "date_prise", "Make": "make", "Model": "model",
         "Software": "software", "LensModel": "objectif", "Orientation": "orientation"}


def analyze_image(path: str) -> ImageMeta:
    """Analyse une image locale et renvoie ses métadonnées EXIF/GPS."""
    meta = ImageMeta(path=path)
    try:
        with Image.open(path) as img:
            meta.width, meta.height = img.size
            exif = img.getexif()
            if not exif:
                return meta
            values: dict[str, object] = {}
            for tag_id, value in exif.items():
                name = TAGS.get(tag_id, str(tag_id))
                values[name] = value
            meta.datetime_original = str(values.get("DateTimeOriginal") or values.get("DateTime") or "").strip()
            meta.camera_make = str(values.get("Make") or "").strip().strip("\x00")
            meta.camera_model = str(values.get("Model") or "").strip().strip("\x00")
            meta.software = str(values.get("Software") or "").strip()
            for name, label in _KEEP.items():
                if name in values and label not in ("make", "model", "software", "date_prise"):
                    meta.other[label] = str(values[name])
            try:
                gps_ifd = exif.get_ifd(0x8825)  # GPSInfo
                if gps_ifd:
                    meta.gps = _extract_gps(gps_ifd)
            except Exception:  # noqa: BLE001
                pass
    except FileNotFoundError:
        meta.error = "fichier introuvable"
    except Exception as exc:  # noqa: BLE001
        meta.error = f"{type(exc).__name__}: {exc}"
    return meta


def correlate_devices(paths: list[str]) -> dict[str, list[ImageMeta]]:
    """Regroupe des images par signature d'appareil (même marque/modèle/logiciel).

    Utile pour repérer que plusieurs photos viennent probablement du même appareil
    — un INDICE de corrélation, jamais une preuve d'identité.
    """
    groups: dict[str, list[ImageMeta]] = {}
    for p in paths:
        meta = analyze_image(p)
        groups.setdefault(meta.device_fingerprint, []).append(meta)
    return groups
