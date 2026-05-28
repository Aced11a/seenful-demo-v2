"""people_score 单测 (event 部分迁移至 test_features_event.py, ADR-0012)."""
from __future__ import annotations

from datetime import datetime

from src.contracts import L1Output
from src.contracts.l1_output import SemanticFacts
from src.features.people import compute_people_score


def make_photo(pid: str, **sf) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 1, 14, 0),
        semantic_facts=SemanticFacts(**sf),
    )


class TestPeopleScore:
    def test_all_none(self):
        ps = [
            make_photo("p1", people_presence="none"),
            make_photo("p2", people_presence="none"),
        ]
        assert compute_people_score(ps) == 0.0

    def test_consistent_close_face_count(self):
        ps = [
            make_photo("p1", people_presence="group", face_count=4),
            make_photo("p2", people_presence="group", face_count=5),
        ]
        score = compute_people_score(ps)
        assert score == 0.65  # P0 上限

    def test_consistent_far_face_count(self):
        ps = [
            make_photo("p1", people_presence="group", face_count=2),
            make_photo("p2", people_presence="group", face_count=10),
        ]
        assert compute_people_score(ps) == 0.45

    def test_inconsistent_presence(self):
        ps = [
            make_photo("p1", people_presence="single"),
            make_photo("p2", people_presence="group"),
        ]
        assert compute_people_score(ps) == 0.3

    def test_p0_cap_never_exceeds_065(self):
        ps = [
            make_photo("p1", people_presence="family_like", face_count=3),
            make_photo("p2", people_presence="family_like", face_count=3),
        ]
        assert compute_people_score(ps) <= 0.65
