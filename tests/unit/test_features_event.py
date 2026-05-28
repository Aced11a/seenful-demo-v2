"""路径 B event 维度单测 (ADR-0012).

覆盖:
  - E.1 strong (event=1.0 + activity ≥ 2/3 双重门槛)
  - E.2 medium (event=1.0 + activity < 2/3)
  - E.3~E.5 medium/weak (event 0.4-1.0)
  - E.6 weak (event 散)
  - E.7/E.8 activity 兜底 (N_valid ≤ 1)
  - Spec §五 14 个 Case

参考: docs/18_path_b_event.md, decisions/0012-path-b-event-aggregation.md
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.contracts import EventShape, L1Output
from src.contracts.l1_output import SemanticFacts
from src.features.event import (
    _compute_activity_distribution,
    build_event_feature,
)


def make_photo(pid: str, event_hint: str = "unknown", activity: str = "unknown") -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 1, 14, 0),
        semantic_facts=SemanticFacts(event_hint=event_hint, activity=activity),
    )


# ─── 工具函数 ────────────────────────────────────────────────


class TestActivityDistribution:
    def test_all_unknown_returns_none(self):
        ps = [make_photo("p1", activity="unknown"), make_photo("p2", activity="unknown")]
        primary, count, share = _compute_activity_distribution(ps)
        assert primary is None
        assert count == 0
        assert share == 0.0

    def test_all_walk_share_1(self):
        ps = [make_photo(f"p{i}", activity="walk") for i in range(5)]
        primary, count, share = _compute_activity_distribution(ps)
        assert primary == "walk"
        assert count == 5
        assert share == 1.0

    def test_majority_walk_share_4_5(self):
        ps = [
            make_photo("p1", activity="walk"),
            make_photo("p2", activity="walk"),
            make_photo("p3", activity="walk"),
            make_photo("p4", activity="walk"),
            make_photo("p5", activity="meal"),
        ]
        primary, count, share = _compute_activity_distribution(ps)
        assert primary == "walk"
        assert share == pytest.approx(0.8)

    def test_unknown_excluded_from_count(self):
        ps = [
            make_photo("p1", activity="walk"),
            make_photo("p2", activity="walk"),
            make_photo("p3", activity="unknown"),
            make_photo("p4", activity="unknown"),
            make_photo("p5", activity="unknown"),
        ]
        primary, count, share = _compute_activity_distribution(ps)
        assert primary == "walk"
        assert count == 2
        assert share == pytest.approx(0.4)  # 2/5, 基于 N


# ─── Spec §五 14 个 Case ─────────────────────────────────────


class TestCase1UnanimousEventActivity:
    """Case 1: [meal × 5] + [activity=meal × 5] → E.1 strong."""
    def test(self):
        ps = [make_photo(f"p{i}", event_hint="meal", activity="meal") for i in range(5)]
        ef = build_event_feature(ps)
        assert ef.band == "strong"
        assert ef.shape == EventShape.UNANIMOUS_EVENT_ACTIVITY
        assert ef.rule_fired == "E.1"
        assert ef.used_activity_gate is True
        assert ef.used_activity_fallback is False
        assert ef.event_primary_share == 1.0
        assert ef.activity_primary_share == 1.0


class TestCase2DominantMedium:
    """Case 2: [meal × 4, gathering × 1] → E.3 medium (老 spec strong)."""
    def test(self):
        ps = [make_photo(f"p{i}", event_hint="meal") for i in range(4)] + [
            make_photo("p5", event_hint="gathering")
        ]
        ef = build_event_feature(ps)
        assert ef.band == "medium"
        assert ef.shape == EventShape.DOMINANT_EVENT
        assert ef.rule_fired == "E.3"
        assert ef.event_primary_share == pytest.approx(0.8)


class TestCase3MixedMedium:
    """Case 3: [meal × 3, gathering × 2] → E.4 medium."""
    def test(self):
        ps = [make_photo(f"p{i}", event_hint="meal") for i in range(3)] + [
            make_photo(f"p{i}", event_hint="gathering") for i in range(3, 5)
        ]
        ef = build_event_feature(ps)
        assert ef.band == "medium"
        assert ef.shape == EventShape.MIXED_EVENT
        assert ef.rule_fired == "E.4"
        assert ef.event_primary_share == pytest.approx(0.6)


class TestCase4WithUnknown:
    """Case 4: [meal × 2, gathering × 1, unknown × 2] → E.5 weak."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="meal"),
            make_photo("p2", event_hint="meal"),
            make_photo("p3", event_hint="gathering"),
            make_photo("p4", event_hint="unknown"),
            make_photo("p5", event_hint="unknown"),
        ]
        ef = build_event_feature(ps)
        # primary=meal (2/3 ≥ 0.6 of N_valid), share=2/5=0.4 → E.5 weak
        assert ef.band == "weak"
        assert ef.shape == EventShape.SCATTERED_EVENT
        assert ef.rule_fired == "E.5"
        assert ef.event_primary_share == pytest.approx(0.4)


class TestCase5HalfAndHalf:
    """Case 5: [meal × 2, gathering × 2] → E.6 weak (primary=None)."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="meal"),
            make_photo("p2", event_hint="meal"),
            make_photo("p3", event_hint="gathering"),
            make_photo("p4", event_hint="gathering"),
        ]
        ef = build_event_feature(ps)
        assert ef.band == "weak"
        assert ef.shape == EventShape.FRAGMENTED_EVENT
        assert ef.rule_fired == "E.6"
        assert ef.primary_event is None  # 0.5 < 0.6 threshold


class TestCase6ThreeWayScattered:
    """Case 6: [meal, gathering, performance, outing] → E.6 weak."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="meal"),
            make_photo("p2", event_hint="gathering"),
            make_photo("p3", event_hint="performance"),
            make_photo("p4", event_hint="outing"),
        ]
        ef = build_event_feature(ps)
        assert ef.band == "weak"
        assert ef.shape == EventShape.FRAGMENTED_EVENT
        assert ef.rule_fired == "E.6"


class TestCase7ActivityFallbackWeak:
    """Case 7: [unknown × 5] + [activity=walk × 4, meal × 1] → E.7 weak."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="unknown", activity="walk"),
            make_photo("p2", event_hint="unknown", activity="walk"),
            make_photo("p3", event_hint="unknown", activity="walk"),
            make_photo("p4", event_hint="unknown", activity="walk"),
            make_photo("p5", event_hint="unknown", activity="meal"),
        ]
        ef = build_event_feature(ps)
        assert ef.band == "weak"
        assert ef.shape == EventShape.ACTIVITY_FALLBACK
        assert ef.rule_fired == "E.7"
        assert ef.used_activity_fallback is True
        assert ef.used_activity_gate is False
        assert ef.activity_primary_share == pytest.approx(0.8)


class TestCase8NoSignal:
    """Case 8: [unknown × 5] + activity 散 → E.8 none."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="unknown", activity="walk"),
            make_photo("p2", event_hint="unknown", activity="meal"),
            make_photo("p3", event_hint="unknown", activity="gathering"),
            make_photo("p4", event_hint="unknown", activity="sightseeing"),
            make_photo("p5", event_hint="unknown", activity="unknown"),
        ]
        ef = build_event_feature(ps)
        assert ef.band == "none"
        assert ef.shape == EventShape.NO_EVENT_SIGNAL
        assert ef.rule_fired == "E.8"


class TestCase9TwoPhotosSameEvent:
    """Case 9: 2 张 [meal] + [activity=meal] → E.1 strong."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="meal", activity="meal"),
            make_photo("p2", event_hint="meal", activity="meal"),
        ]
        ef = build_event_feature(ps)
        assert ef.band == "strong"
        assert ef.shape == EventShape.UNANIMOUS_EVENT_ACTIVITY


class TestCase10TwoPhotosBinaryChoice:
    """Case 10: 2 张 [meal, gathering] → E.6 weak (老 none, 新 weak)."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="meal"),
            make_photo("p2", event_hint="gathering"),
        ]
        ef = build_event_feature(ps)
        assert ef.band == "weak"
        assert ef.shape == EventShape.FRAGMENTED_EVENT
        assert ef.rule_fired == "E.6"


class TestCase11UnanimousEventScatteredActivity:
    """Case 11 (v0.2 关键): event 一致 + activity 散 → E.2 medium."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="outing", activity="walk"),
            make_photo("p2", event_hint="outing", activity="walk"),
            make_photo("p3", event_hint="outing", activity="sightseeing"),
            make_photo("p4", event_hint="outing", activity="sightseeing"),
            make_photo("p5", event_hint="outing", activity="gathering"),
        ]
        ef = build_event_feature(ps)
        # event 1.0, activity max=walk 或 sightseeing 2/5=0.4 < 2/3 → E.2
        assert ef.band == "medium"
        assert ef.shape == EventShape.UNANIMOUS_EVENT_MIXED_ACTIVITY
        assert ef.rule_fired == "E.2"
        assert ef.used_activity_gate is True
        assert ef.event_primary_share == 1.0


class TestCase12SportsAcceptanceBoundary:
    """Case 12 (篮球/足球场景): [sports × 5] + [activity=gathering × 5] → E.1 strong (接受边界)."""
    def test(self):
        ps = [make_photo(f"p{i}", event_hint="sports", activity="gathering") for i in range(5)]
        ef = build_event_feature(ps)
        # sports 大类成集合理 (方案 a 接受), 子类区分由 theme 维度承担
        assert ef.band == "strong"
        assert ef.shape == EventShape.UNANIMOUS_EVENT_ACTIVITY


class TestCase13EventUnanimousActivityMajority:
    """Case 13: event 1.0 + activity 主导 (4/5=0.8 ≥ 2/3) → E.1 strong."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="outing", activity="walk"),
            make_photo("p2", event_hint="outing", activity="walk"),
            make_photo("p3", event_hint="outing", activity="walk"),
            make_photo("p4", event_hint="outing", activity="walk"),
            make_photo("p5", event_hint="outing", activity="sightseeing"),
        ]
        ef = build_event_feature(ps)
        assert ef.band == "strong"
        assert ef.shape == EventShape.UNANIMOUS_EVENT_ACTIVITY
        assert ef.activity_primary_share == pytest.approx(0.8)


class TestCase14EventUnanimousActivityWithUnknown:
    """Case 14: event 1.0 + activity 含 unknown (share=0.6 < 2/3) → E.2 medium."""
    def test(self):
        ps = [
            make_photo("p1", event_hint="meal", activity="meal"),
            make_photo("p2", event_hint="meal", activity="meal"),
            make_photo("p3", event_hint="meal", activity="meal"),
            make_photo("p4", event_hint="meal", activity="unknown"),
            make_photo("p5", event_hint="meal", activity="unknown"),
        ]
        ef = build_event_feature(ps)
        # activity_share = 3/5 = 0.6 < 2/3
        assert ef.band == "medium"
        assert ef.shape == EventShape.UNANIMOUS_EVENT_MIXED_ACTIVITY
        assert ef.rule_fired == "E.2"
        assert ef.activity_primary_share == pytest.approx(0.6)


# ─── 边界 case ───────────────────────────────────────────────


class TestBoundary:
    def test_empty_returns_none(self):
        ef = build_event_feature([])
        assert ef.band == "none"
        assert ef.shape == EventShape.NO_EVENT_SIGNAL

    def test_single_photo_returns_none(self):
        """N < 2 → none (path B 红线 §3 '2 张永远不成集')."""
        ps = [make_photo("p1", event_hint="meal", activity="meal")]
        ef = build_event_feature(ps)
        assert ef.band == "none"

    def test_strong_threshold_boundary_above(self):
        """activity_share = 5/7 ≈ 0.714 > 2/3 → strong."""
        ps = [
            make_photo(f"p{i}", event_hint="outing", activity="walk") for i in range(5)
        ] + [
            make_photo("p6", event_hint="outing", activity="sightseeing"),
            make_photo("p7", event_hint="outing", activity="gathering"),
        ]
        ef = build_event_feature(ps)
        # 5/7 ≈ 0.714 ≥ 0.667 → strong
        assert ef.band == "strong"

    def test_strong_threshold_boundary_below(self):
        """activity_share = 3/5 = 0.6 < 2/3 → medium."""
        ps = [
            make_photo(f"p{i}", event_hint="outing", activity="walk") for i in range(3)
        ] + [
            make_photo("p4", event_hint="outing", activity="sightseeing"),
            make_photo("p5", event_hint="outing", activity="gathering"),
        ]
        ef = build_event_feature(ps)
        # 3/5 = 0.6 < 0.667 → medium
        assert ef.band == "medium"


# ─── 老 API 兼容性测试 (compute_event_score 删除) ────────────


class TestOldAPIRemoved:
    """Ace 偏好 '老方案直接删, 不留 deprecated'. compute_event_score 应已删除."""
    def test_compute_event_score_removed(self):
        from src.features import event as event_module
        assert not hasattr(event_module, "compute_event_score")
