import numpy as np
import pytest

from face_analyse.engine.matcher import GalleryEntry, IdentityMatcher, cosine_similarity
from face_analyse.engine.types import FaceEmbedding, MatchStatus

from .conftest import unit

M = "model-a"


def entry(ref, pid, name, vec, model=M):
    return GalleryEntry(ref, pid, name, unit(vec), model)


@pytest.fixture
def matcher():
    m = IdentityMatcher(threshold=0.5, ambiguity_margin=0.05)
    m.load([
        entry(1, 1, "Alice Martin", [1, 0, 0, 0]),
        entry(2, 1, "Alice Martin", [0.9, 0.1, 0, 0]),
        entry(3, 2, "Bob Durand", [0, 1, 0, 0]),
    ], M)
    return m


def q(vec, model=M):
    return FaceEmbedding(unit(vec), model)


def test_match_above_threshold(matcher):
    d = matcher.search(q([0.95, 0.05, 0, 0]))
    assert d.status == MatchStatus.MATCH
    assert d.identity.display_name == "Alice Martin"
    assert d.candidates[0].similarity > 0.9


def test_unknown_below_threshold_returns_no_identity(matcher):
    d = matcher.search(q([0, 0, 1, 0]))
    assert d.status == MatchStatus.UNKNOWN
    assert d.identity is None
    assert d.label == "UNKNOWN"
    # Les plus proches restent consultables mais aucun nom n'est retenu.
    assert all(c.similarity < 0.5 for c in d.candidates)


def test_never_invents_identity_with_empty_gallery():
    m = IdentityMatcher(0.3)
    m.load([], M)
    d = m.search(q([1, 0, 0, 0]))
    assert d.status == MatchStatus.UNKNOWN and d.identity is None and not d.candidates


def test_model_mismatch_is_refused(matcher):
    d = matcher.search(q([1, 0, 0, 0], model="other-model"))
    assert d.status == MatchStatus.UNKNOWN
    assert "différent" in d.note


def test_gallery_ignores_embeddings_from_other_models():
    m = IdentityMatcher(0.5)
    n = m.load([entry(1, 1, "A", [1, 0]), entry(2, 2, "B", [0, 1], model="other")], M)
    assert n == 1 and m.person_count == 1


def test_multiple_references_use_best(matcher):
    d = matcher.search(q([0.9, 0.1, 0, 0]))
    assert d.candidates[0].best_reference_id == 2
    assert len({c.person_id for c in d.candidates}) == len(d.candidates)  # une ligne par personne


def test_ambiguous_when_two_people_close():
    m = IdentityMatcher(0.5, ambiguity_margin=0.05)
    m.load([entry(1, 1, "A", [1, 0.02, 0]), entry(2, 2, "B", [1, -0.02, 0])], M)
    d = m.search(q([1, 0, 0]))
    assert d.status == MatchStatus.AMBIGUOUS
    assert d.label.startswith("? ")


def test_threshold_is_configurable(matcher):
    probe = q([0.6, 0.0, 0.8, 0])  # similarité ~0.6 avec Alice
    matcher.threshold = 0.5
    assert matcher.search(probe).status == MatchStatus.MATCH
    matcher.threshold = 0.7
    assert matcher.search(probe).status == MatchStatus.UNKNOWN


def test_cosine_similarity_refuses_mixed_models():
    with pytest.raises(ValueError):
        cosine_similarity(q([1, 0]), q([1, 0], model="x"))
    assert cosine_similarity(q([1, 0]), q([1, 0])) == pytest.approx(1.0)


def test_top_k_limits_candidates():
    m = IdentityMatcher(0.0)
    rng = np.random.default_rng(0)
    m.load([entry(i, i, f"P{i}", rng.normal(size=16)) for i in range(50)], M)
    assert len(m.search(q(rng.normal(size=16)), top_k=3).candidates) == 3
