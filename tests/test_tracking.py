from face_analyse.engine.tracking import FaceTracker, iou
from face_analyse.engine.types import Candidate, IdentityDecision, MatchStatus

from .conftest import make_face


def decision(name: str | None, sim: float = 0.8):
    if name is None:
        return IdentityDecision(MatchStatus.UNKNOWN, 0.5, [Candidate(9, "X", 0.2)])
    return IdentityDecision(MatchStatus.MATCH, 0.5, [Candidate(1, name, sim)])


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 5, 5)) == 0.0
    assert 0 < iou((0, 0, 10, 10), (5, 5, 10, 10)) < 1


def test_track_identity_persists_while_moving():
    t = FaceTracker()
    first = t.update([make_face(100, 100)])
    tid = first[0].track_id
    for dx in range(5, 40, 5):
        tracks = t.update([make_face(100 + dx, 100)])
        assert len(tracks) == 1 and tracks[0].track_id == tid


def test_new_face_gets_new_track_and_lost_tracks_expire():
    t = FaceTracker(max_missed=2)
    t.update([make_face(0, 0)])
    tracks = t.update([make_face(0, 0), make_face(400, 0)])
    assert len({tr.track_id for tr in tracks}) == 2
    for _ in range(4):
        t.update([])
    assert t.tracks == []


def test_vote_requires_majority():
    t = FaceTracker()
    tr = t.update([make_face()])[0]
    assert tr.label == "ANALYSE…"
    tr.add_decision(decision("Alice"))
    tr.add_decision(decision("Alice"))
    assert tr.label == "Alice" and tr.is_known
    for _ in range(4):
        tr.add_decision(decision(None))
    assert tr.label == "UNKNOWN"


def test_single_lucky_match_does_not_name_someone():
    t = FaceTracker()
    tr = t.update([make_face()])[0]
    tr.add_decision(decision(None))
    tr.add_decision(decision("Alice"))
    tr.add_decision(decision(None))
    assert tr.label == "UNKNOWN"
