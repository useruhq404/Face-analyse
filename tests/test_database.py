import sqlite3

import numpy as np
import pytest

from face_analyse.core.errors import ConsentError, DatabaseError, NoFaceError
from face_analyse.database.crypto import Vault, load_or_create_key
from face_analyse.database.repository import Repository


@pytest.fixture
def repo(tmp_path):
    r = Repository(tmp_path / "t.db")
    yield r
    r.close()


def img(value: int) -> np.ndarray:
    return np.full((120, 100, 3), value, np.uint8)


def test_vault_roundtrip_and_key_persistence(tmp_path):
    key_file = tmp_path / "k.key"
    k1 = load_or_create_key(key_file)
    k2 = load_or_create_key(key_file)
    assert k1 == k2
    v = Vault(k1)
    token = v.encrypt(b"secret")
    assert token != b"secret" and v.decrypt(token) == b"secret"
    with pytest.raises(DatabaseError):
        Vault(load_or_create_key(tmp_path / "other.key")).decrypt(token)


def test_consent_is_mandatory(repo):
    with pytest.raises(ConsentError):
        repo.add_person("Jean", "Dupont", consent=False)
    with pytest.raises(DatabaseError):
        repo.add_person("", "  ", consent=True)


def test_person_crud_and_search(repo):
    pid = repo.add_person("Jean", "Dupont", consent=True, notes="équipe A")
    repo.add_person("Marie", "Curie", consent=True)
    assert [p.display_name for p in repo.list_people("dup")] == ["Jean Dupont"]
    assert [p.display_name for p in repo.list_people("équipe")] == ["Jean Dupont"]
    repo.update_person(pid, "Jean", "Dupond", "")
    assert repo.get_person(pid).last_name == "Dupond"
    assert repo.get_person(pid).consent_at is not None


def test_multiple_photos_and_gallery(repo, fake_engine):
    pid = repo.add_person("Jean", "Dupont", consent=True)
    for v in (90, 120, 150):
        repo.add_photo(pid, img(v), fake_engine)
    gal = repo.gallery("fake-1")
    assert len(gal) == 3 and {g.person_id for g in gal} == {pid}
    assert all(abs(np.linalg.norm(g.vector) - 1) < 1e-5 for g in gal)
    assert repo.gallery("other-model") == []
    assert len(repo.list_photos(pid)) == 3
    assert repo.photo_image(repo.list_photos(pid)[0].id).shape[2] == 3


def test_photo_without_face_is_rejected(repo, fake_engine):
    pid = repo.add_person("A", "B", consent=True)
    with pytest.raises(NoFaceError):
        repo.add_photo(pid, img(0), fake_engine)
    assert repo.stats()["photos"] == 0


def test_biometrics_are_encrypted_at_rest(repo, fake_engine):
    pid = repo.add_person("Jean", "Dupont", consent=True)
    repo.add_photo(pid, img(100), fake_engine)
    con = sqlite3.connect(repo.db_path)
    blob, = con.execute("select image_enc from photos").fetchone()
    vec, = con.execute("select vector_enc from embeddings").fetchone()
    con.close()
    assert not bytes(blob).startswith(b"\xff\xd8")  # pas un JPEG en clair
    assert bytes(blob).startswith(b"gAAAA") and bytes(vec).startswith(b"gAAAA")  # jetons Fernet


def test_delete_person_removes_everything(repo, fake_engine):
    pid = repo.add_person("Zorglub", "Unique", consent=True)
    repo.add_photo(pid, img(100), fake_engine)
    repo.add_photo(pid, img(130), fake_engine)
    repo.delete_person(pid)
    assert repo.stats() == {"persons": 0, "photos": 0, "embeddings": 0}
    raw = repo.db_path.read_bytes()
    assert b"Zorglub" not in raw  # VACUUM + secure_delete : le nom ne subsiste pas dans le fichier


def test_reencode_for_new_model(repo, fake_engine):
    pid = repo.add_person("A", "B", consent=True)
    repo.add_photo(pid, img(100), fake_engine)
    from .conftest import FakeEngine

    new = FakeEngine(model_id="fake-2")
    assert repo.photos_missing_model("fake-2") == 1
    ok, fail = repo.reencode_all(new)
    assert (ok, fail) == (1, 0)
    assert repo.photos_missing_model("fake-2") == 0
    assert len(repo.gallery("fake-2")) == 1 and len(repo.gallery("fake-1")) == 1


def test_history_and_secrets(repo):
    repo.log_history("osint", "search", "Recherche X", {"n": 3})
    assert repo.history("osint")[0].summary == "Recherche X"
    repo.clear_history()
    assert repo.history() == []
    repo.set_secret("anthropic_api_key", "sk-test")
    assert repo.get_secret("anthropic_api_key") == "sk-test"
    con = sqlite3.connect(repo.db_path)
    raw, = con.execute("select value_enc from secrets").fetchone()
    con.close()
    assert b"sk-test" not in bytes(raw)
    repo.set_secret("anthropic_api_key", "")
    assert repo.get_secret("anthropic_api_key") == ""


def test_overview_aggregates(repo):
    for mod, act, summ in [("osint", "search", "r1"), ("osint", "report", "r2"),
                           ("analysis", "photo_analyzed", "a1"), ("tools", "ip_lookup", "t1")]:
        repo.log_history(mod, act, summ)
    assert repo.history_count() == 4
    usage = dict(repo.module_usage())
    assert usage["osint"] == 2 and usage["analysis"] == 1 and usage["tools"] == 1
    days = repo.activity_by_day(14)
    assert len(days) == 14
    assert sum(n for _, n in days) == 4  # tout est aujourd'hui
    assert days[-1][1] == 4  # dernière colonne = aujourd'hui


def test_wipe(repo, fake_engine):
    pid = repo.add_person("A", "B", consent=True)
    repo.add_photo(pid, img(100), fake_engine)
    repo.wipe_biometrics()
    assert repo.stats() == {"persons": 0, "photos": 0, "embeddings": 0}
