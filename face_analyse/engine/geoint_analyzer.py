# face_analyse/engine/geoint_analyzer.py
from typing import Dict, List, Optional
from collections import defaultdict
from PIL import Image, ImageOps
from PIL.ExifTags import Base, GPS, IFD  # Pillow >= 9.4


class GeointAnalyzer:
    """
    Moteur d'analyse géospatiale.
    Pipeline: EXIF -> Device Fingerprinting -> Temporal Clues -> Visual Heuristics.
    """

    def analyze_image(self, image_path: str) -> Dict:
        """Analyse complète d'une image pour extraire les indices géospatiaux."""
        results = {
            "location": None,
            "exif_raw": {},
            "device_fingerprint": {"make": None, "model": None, "software": None},
            "temporal_clues": [],
            "visual_heuristics": [],
            "confidence_score": 0.0,
        }

        try:
            with Image.open(image_path) as img:
                exif = img.getexif()  # lire l'EXIF AVANT exif_transpose
                img = ImageOps.exif_transpose(img)
                img.load()

            if exif:
                exif_ifd = exif.get_ifd(IFD.Exif)
                gps_ifd = exif.get_ifd(IFD.GPSInfo)

                # 1. Extraction EXIF
                raw = {
                    "Make": exif.get(Base.Make),
                    "Model": exif.get(Base.Model),
                    "Software": exif.get(Base.Software),
                    "DateTime": exif.get(Base.DateTime),
                    "DateTimeOriginal": exif_ifd.get(Base.DateTimeOriginal),
                    "PixelXDimension": exif_ifd.get(Base.ExifImageWidth),
                    "PixelYDimension": exif_ifd.get(Base.ExifImageHeight),
                }
                results["exif_raw"] = {k: self._clean(v) for k, v in raw.items() if v is not None}

                # 2. Coordonnées GPS
                lat = self._dms_to_decimal(gps_ifd.get(GPS.GPSLatitude), gps_ifd.get(GPS.GPSLatitudeRef, "N"))
                lon = self._dms_to_decimal(gps_ifd.get(GPS.GPSLongitude), gps_ifd.get(GPS.GPSLongitudeRef, "E"))
                if lat is not None and lon is not None:
                    results["location"] = {"lat": lat, "lon": lon, "confidence": "HIGH"}
                    results["confidence_score"] += 0.6

                # 3. Fingerprint de l'appareil
                results["device_fingerprint"] = {
                    "make": results["exif_raw"].get("Make"),
                    "model": results["exif_raw"].get("Model"),
                    "software": results["exif_raw"].get("Software"),
                }

                # 4. Indices temporels
                date = results["exif_raw"].get("DateTimeOriginal") or results["exif_raw"].get("DateTime")
                if date:
                    results["temporal_clues"].append({
                        "type": "EXIF_DATE",
                        "value": date,
                        "description": "Date de prise de vue",
                    })
                    results["confidence_score"] += 0.2
            else:
                results["warning"] = "No EXIF data found"

            # 5. Analyse visuelle (même sans EXIF)
            results["visual_heuristics"] = self._visual_analysis(img)

        except Exception as e:
            results["error"] = f"{type(e).__name__}: {e}"

        return results

    @staticmethod
    def _clean(value):
        if isinstance(value, bytes):
            return value.decode(errors="ignore").strip("\x00 ")
        if isinstance(value, str):
            return value.strip("\x00 ")
        return value

    @staticmethod
    def _dms_to_decimal(dms, ref) -> Optional[float]:
        """Convertit DMS en décimal."""
        if not dms or len(dms) != 3:
            return None
        try:
            d, m, s = (float(x) for x in dms)
            decimal = d + m / 60.0 + s / 3600.0
            if isinstance(ref, bytes):
                ref = ref.decode(errors="ignore")
            if str(ref).upper().startswith(("S", "W")):
                decimal = -decimal
            return round(decimal, 6)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _visual_analysis(img: Image.Image) -> List[Dict]:
        """Heuristiques visuelles."""
        heuristics = []
        small = img.convert("RGB").resize((100, 100))
        colors = small.getcolors(100 * 100)
        if colors:
            dominant = max(colors, key=lambda c: c[0])[1]
            heuristics.append({
                "type": "DOMINANT_COLOR",
                "value": dominant,
                "description": "Couleur dominante (indicateur d'environnement)",
            })
        return heuristics

    def correlate_devices(self, images: List[str]) -> Dict[str, List[str]]:
        """Regroupe les images par empreinte d'appareil (make-model-software)."""
        groups = defaultdict(list)
        for path in images:
            fp = self.analyze_image(path)["device_fingerprint"]
            if not fp.get("make") and not fp.get("model"):
                groups["UNKNOWN"].append(path)
                continue
            key = "-".join(str(fp.get(k) or "?") for k in ("make", "model", "software"))
            groups[key].append(path)
        return dict(groups)
