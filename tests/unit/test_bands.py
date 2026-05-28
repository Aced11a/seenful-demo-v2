"""维度分档 + 高频地点降一档 单测."""
from __future__ import annotations

from src.contracts import FeaturePackage
from src.policy.bands import compute_bands


def make_fp(**kwargs) -> FeaturePackage:
    defaults = dict(
        location_score=0.0, time_score=0.0, theme_score=0.0,
        event_score=0.0, people_score=0.0, anchor_score=0.0,
        emotional_score=0.0, photo_count=3,
    )
    defaults.update(kwargs)
    return FeaturePackage(**defaults)


class TestBands:
    def test_all_strong(self):
        b = compute_bands(make_fp(
            location_score=0.9, time_score=0.9, theme_score=0.8,
            event_score=0.8, people_score=0.65, anchor_score=0.75,
            emotional_score=0.8,
        ))
        assert b.location == "strong"
        assert b.time == "strong"
        assert b.theme == "strong"
        assert b.event == "strong"
        # people 上限 0.65 < strong (0.70) → 应该 medium
        assert b.people == "medium"
        assert b.anchor == "strong"
        assert b.emotional == "strong"

    def test_all_none(self):
        b = compute_bands(make_fp())
        assert b.location == "none"
        assert b.theme == "none"
        assert b.event == "none"
        assert b.people == "none"

    def test_high_frequency_downgrades_location_one_step(self):
        # location=0.9 应 strong, 高频地点 → medium
        b = compute_bands(make_fp(
            location_score=0.9, is_high_frequency_place=True,
        ))
        assert b.location == "medium"

    def test_high_frequency_strong_to_medium_only_for_location(self):
        # 其他维度不应被高频降档
        b = compute_bands(make_fp(
            location_score=0.9, theme_score=0.9, is_high_frequency_place=True,
        ))
        assert b.location == "medium"
        assert b.theme == "strong"

    def test_high_frequency_medium_to_weak(self):
        b = compute_bands(make_fp(
            location_score=0.70, is_high_frequency_place=True,
        ))
        # 0.70 应 medium (>=0.65) → 降为 weak
        assert b.location == "weak"

    def test_high_frequency_weak_to_none(self):
        b = compute_bands(make_fp(
            location_score=0.45, is_high_frequency_place=True,
        ))
        # 0.45 应 weak (>=0.40) → 降为 none
        assert b.location == "none"
