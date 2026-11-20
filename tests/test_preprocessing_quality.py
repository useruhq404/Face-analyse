import cv2
import numpy as np
import pytest

from face_analyse.core.errors import ImageError
from face_analyse.engine.preprocessing import enhance_low_light, load_image, mean_luminance, resize_max_side
from face_analyse.engine.quality import assess, estimate_yaw_ratio

from .conftest import make_face


def test_load_image_unicode_path(tmp_path):
    img = np.full((40, 60, 3), 128, np.uint8)
    path = tmp_path / "dossier é à ü" / "photo_été.jpg"
    path.parent.mkdir()
    ok, buf = cv2.imencode(".jpg", img)
    buf.tofile(str(path))
    loaded = load_image(path)
    assert loaded.shape == (40, 60, 3)


def test_load_image_rejects_bad_files(tmp_path):
    bad = tmp_path / "x.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(ImageError):
        load_image(bad)
    with pytest.raises(ImageError):
        load_image(tmp_path / "x.gif")
    with pytest.raises(ImageError):
        load_image(tmp_path / "missing.png")


def test_enhance_low_light_only_when_needed():
    dark = np.full((50, 50, 3), 25, np.uint8)
    normal = np.full((50, 50, 3), 120, np.uint8)
    assert mean_luminance(enhance_low_light(dark)) > 60
    assert np.array_equal(enhance_low_light(normal), normal)


def test_resize_max_side():
    img = np.zeros((1000, 2000, 3), np.uint8)
    out, scale = resize_max_side(img, 500)
    assert out.shape[:2] == (250, 500) and scale == pytest.approx(0.25)
    same, s2 = resize_max_side(img, 4000)
    assert same is img and s2 == 1.0


def test_yaw_ratio_frontal_vs_profile():
    frontal = make_face()
    assert estimate_yaw_ratio(frontal.landmarks) < 0.05
    lm = frontal.landmarks.copy()
    lm[2, 0] = lm[1, 0] - 2  # nez presque aligné sur un œil : profil
    assert estimate_yaw_ratio(lm) > 0.8


def test_quality_warnings():
    small = make_face(w=30, h=36, score=0.7)
    q = assess(small, np.full((112, 112, 3), 20, np.uint8))
    joined = " ".join(q.warnings)
    assert "petite taille" in joined and "sous-exposé" in joined and "floue" in joined
    assert 0.0 <= q.score <= 1.0
