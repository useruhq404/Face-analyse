import json

import numpy as np
import pytest

from face_analyse.core.config import Settings
from face_analyse.engine.benchmark import best_threshold, eer, parse_lfw_pairs, rates_at, roc_auc, threshold_at_fmr


def test_metrics_on_separable_scores():
    s = np.array([0.9, 0.8, 0.7, 0.2, 0.1, 0.0])
    lab = np.array([True, True, True, False, False, False])
    assert roc_auc(s, lab) == pytest.approx(1.0)
    t, acc = best_threshold(s, lab)
    assert acc == 1.0 and 0.2 < t <= 0.7
    assert rates_at(s, lab, 0.5) == (0.0, 0.0)
    e, _ = eer(s, lab)
    assert e == pytest.approx(0.0)


def test_metrics_on_random_scores():
    rng = np.random.default_rng(0)
    s = rng.random(4000)
    lab = rng.random(4000) > 0.5
    assert roc_auc(s, lab) == pytest.approx(0.5, abs=0.05)
    t = threshold_at_fmr(s, lab, 0.01)
    assert rates_at(s, lab, t)[0] <= 0.011


def test_parse_lfw_pairs(tmp_path):
    txt = "1\t2\nA\t1\t2\nB\t1\t3\nA\t1\tB\t2\nC\t2\tD\t1\n"
    (tmp_path / "pairs.txt").write_text(txt)
    pairs = parse_lfw_pairs(tmp_path / "pairs.txt", tmp_path)
    assert [p.same for p in pairs] == [True, True, False, False]
    assert pairs[0].a.name == "A_0001.jpg" and pairs[2].b.name == "B_0002.jpg"


def test_server_url_resolution(monkeypatch):
    s = Settings()
    assert s.server_url() == ""  # autonome par défaut
    s.auth.server_url = "https://panel.example/"
    assert s.server_url() == "https://panel.example"  # barre finale retirée
    monkeypatch.setenv("FACE_ANALYSE_SERVER", "https://env.example")
    assert s.server_url() == "https://env.example"  # l'env a priorité


def test_auth_settings_persisted():
    s = Settings.load()
    s.auth.server_url = "https://panel.example"
    s.auth.remember = False
    s.save()
    s2 = Settings.load()
    assert s2.auth.server_url == "https://panel.example" and s2.auth.remember is False


def test_settings_roundtrip_and_robustness():
    s = Settings.load()
    assert s.engine.match_threshold == 0.50
    s.engine.match_threshold = 0.55
    s.camera.mirror = False
    s.save()
    s2 = Settings.load()
    assert s2.engine.match_threshold == 0.55 and s2.camera.mirror is False
    raw = json.loads(Settings.path().read_text(encoding="utf-8"))
    raw["engine"]["unknown_key"] = 1
    Settings.path().write_text(json.dumps(raw), encoding="utf-8")
    assert Settings.load().engine.match_threshold == 0.55
    Settings.path().write_text("{corrupt", encoding="utf-8")
    assert Settings.load().engine.match_threshold == 0.50
