"""Tests du moteur réel (modèles ONNX). Les tests sur visages réels utilisent
LFW si ``FACE_ANALYSE_LFW`` est défini, sinon ils sont ignorés."""

import numpy as np
import pytest

from face_analyse.core.config import EngineSettings
from face_analyse.core.errors import ModelError, NoFaceError
from face_analyse.engine import registry
from face_analyse.engine.matcher import GalleryEntry
from face_analyse.engine.pipeline import FaceEngine
from face_analyse.engine.preprocessing import load_image
from face_analyse.engine.types import MatchStatus


@pytest.fixture(scope="module")
def engine():
    return FaceEngine.from_settings(EngineSettings())


def test_models_present_and_integrity_verified():
    for spec in (registry.DETECTORS["yunet"], registry.EMBEDDERS["sface"]):
        path = registry.locate(spec, verify=True)
        assert registry.sha256_file(path) == spec.sha256


def test_corrupted_model_is_detected(tmp_path, monkeypatch):
    bad = tmp_path / "models"
    bad.mkdir()
    spec = registry.EMBEDDERS["sface"]
    (bad / spec.filename).write_bytes(b"corrupted")
    monkeypatch.setattr(registry, "models_dir", lambda: bad)
    with pytest.raises(ModelError):
        registry.locate(spec)


def test_unknown_model_keys():
    with pytest.raises(ModelError):
        registry.create_detector("nope")
    with pytest.raises(ModelError):
        registry.create_embedder("nope")


def test_no_face_in_blank_image(engine):
    assert engine.detect(np.zeros((480, 640, 3), np.uint8)) == []
    assert engine.analyze(np.full((300, 300, 3), 200, np.uint8)) == []
    with pytest.raises(NoFaceError):
        engine.embed_single(np.zeros((200, 200, 3), np.uint8))


def test_embedding_shape_and_norm(engine, lfw_root):
    img = load_image(lfw_root / "Tony_Blair" / "Tony_Blair_0001.jpg")
    a, n = engine.embed_single(img)
    assert n >= 1 and a.embedding.vector.shape == (128,)
    assert abs(np.linalg.norm(a.embedding.vector) - 1) < 1e-5


def test_same_person_more_similar_than_different(engine, lfw_root):
    def emb(name, i):
        return engine.embed_single(load_image(lfw_root / name / f"{name}_{i:04d}.jpg"))[0].embedding.vector

    same = float(emb("Tony_Blair", 1) @ emb("Tony_Blair", 2))
    diff = float(emb("Tony_Blair", 1) @ emb("George_W_Bush", 1))
    assert same > 0.5 > diff


def test_absent_person_is_unknown(engine, lfw_root):
    entries = []
    for pid, name in enumerate(["Tony_Blair", "George_W_Bush", "Colin_Powell"]):
        for i in (1, 2, 3):
            a, _ = engine.embed_single(load_image(lfw_root / name / f"{name}_{i:04d}.jpg"))
            entries.append(GalleryEntry(pid * 10 + i, pid, name, a.embedding.vector, a.embedding.model_id))
    engine.matcher.load(entries, engine.embedder.model_id)
    known = engine.analyze(load_image(lfw_root / "Tony_Blair" / "Tony_Blair_0010.jpg"))
    assert known[0].decision.status == MatchStatus.MATCH and known[0].decision.identity.display_name == "Tony_Blair"
    absent = engine.analyze(load_image(lfw_root / "Jennifer_Aniston" / "Jennifer_Aniston_0001.jpg"))
    assert absent[0].decision.status == MatchStatus.UNKNOWN and absent[0].decision.identity is None


def test_multiple_faces_detected(engine, lfw_root):
    imgs = [load_image(lfw_root / n / f"{n}_0001.jpg") for n in ("Tony_Blair", "George_W_Bush", "Colin_Powell")]
    assert len(engine.detect(np.hstack(imgs))) == 3
