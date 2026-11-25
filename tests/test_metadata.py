"""Tests de l'analyse des métadonnées EXIF/GPS (sans dépendre d'une vraie photo géotaguée)."""

from __future__ import annotations

from PIL import Image

from face_analyse.osint import metadata as md


def test_dms_to_decimal_paris():
    # Paris ≈ 48°51'24"N, 2°21'07"E
    lat = md.dms_to_decimal((48, 51, 24), "N")
    lon = md.dms_to_decimal((2, 21, 7), "E")
    assert abs(lat - 48.8567) < 0.01 and abs(lon - 2.3519) < 0.01


def test_dms_south_west_negative():
    assert md.dms_to_decimal((33, 0, 0), "S") < 0
    assert md.dms_to_decimal((70, 0, 0), "W") < 0


def test_geopoint_map_url():
    p = md.GeoPoint(48.8567, 2.3519)
    assert "openstreetmap" in p.map_url and "48.8567" in p.map_url


def test_analyze_image_without_exif(tmp_path):
    f = tmp_path / "plain.png"
    Image.new("RGB", (20, 10), (120, 30, 30)).save(f)
    m = md.analyze_image(str(f))
    assert not m.error and m.width == 20 and m.height == 10
    assert m.gps is None and not m.has_exif and m.device_fingerprint == "inconnu"


def test_analyze_missing_file():
    m = md.analyze_image("/does/not/exist.jpg")
    assert m.error


def test_correlate_devices_groups(tmp_path):
    files = []
    for i in range(3):
        f = tmp_path / f"i{i}.png"
        Image.new("RGB", (8, 8), (i, i, i)).save(f)
        files.append(str(f))
    groups = md.correlate_devices(files)
    # aucune EXIF → tous regroupés sous « inconnu »
    assert groups and sum(len(v) for v in groups.values()) == 3
