"""路径 B anchor 维度单测 (ADR-0014 v0.3 双层判定).

覆盖跟 theme 对称, 主字段 meaning_anchors / 次字段 object_anchors.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.contracts import AnchorShape, L1Output
from src.contracts.l1_output import SemanticFacts
from src.features.anchor import build_anchor_feature


def make_photo(
    pid: str,
    meaning_anchors: list[str] | None = None,
    object_anchors: list[str] | None = None,
) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 1, 12, 0),
        meaning_anchors=meaning_anchors or [],
        semantic_facts=SemanticFacts(object_anchors=object_anchors or []),
    )


class TestAN1Strong:
    def test_all_same_meaning(self):
        ps = [
            make_photo(f"p{i}", meaning_anchors=["天光", "树影"])
            for i in range(5)
        ]
        af = build_anchor_feature(ps)
        assert af.band == "strong"
        assert af.rule_fired == "AN.1"
        assert af.shape == AnchorShape.FULL_COVERAGE_ANCHORED
        assert af.primary_coverage == 1.0
        assert af.secondary_coverage is None


class TestAN2SecondaryBoost:
    """AN.2 主字段 0.8 + 次字段 (object) 强 → 升 strong."""
    def test_object_anchors_save(self):
        ps = [
            make_photo("p1", meaning_anchors=["天光"], object_anchors=["湖"]),
            make_photo("p2", meaning_anchors=["天光"], object_anchors=["湖"]),
            make_photo("p3", meaning_anchors=["天光"], object_anchors=["湖"]),
            make_photo("p4", meaning_anchors=["天光"], object_anchors=["湖"]),
            make_photo("p5", meaning_anchors=["拥堵"], object_anchors=["湖"]),
        ]
        af = build_anchor_feature(ps)
        # primary_coverage = 4/5 = 0.8 → AN.2
        # secondary_coverage = 5/5 = 1.0 ≥ 2/3 → boost
        assert af.band == "strong"
        assert "AN.2" in af.rule_fired
        assert "+secondary_boost" in af.rule_fired
        assert af.secondary_action == "boost"


class TestAN2SecondaryDemote:
    """AN.2 主字段 0.8 + 次字段 (object) 散 → 降 weak."""
    def test_object_anchors_all_different(self):
        ps = [
            make_photo("p1", meaning_anchors=["天光"], object_anchors=["扶梯"]),
            make_photo("p2", meaning_anchors=["天光"], object_anchors=["树"]),
            make_photo("p3", meaning_anchors=["天光"], object_anchors=["桥"]),
            make_photo("p4", meaning_anchors=["天光"], object_anchors=["汽车"]),
            make_photo("p5", meaning_anchors=["拥堵"], object_anchors=["楼"]),
        ]
        af = build_anchor_feature(ps)
        # secondary 5 独立各 hit=1 < 2 → secondary_coverage=0 < 1/3 → demote
        assert af.band == "weak"
        assert "AN.2+secondary_demote" in af.rule_fired
        assert af.secondary_action == "demote"


class TestAN3MediumNoChange:
    def test_secondary_middle(self):
        ps = [
            make_photo("p1", meaning_anchors=["天光"], object_anchors=["湖面"]),
            make_photo("p2", meaning_anchors=["天光"], object_anchors=["湖面"]),
            make_photo("p3", meaning_anchors=["天光"], object_anchors=["湖面"]),
            make_photo("p4", meaning_anchors=["楼影"], object_anchors=["桥"]),
            make_photo("p5", meaning_anchors=["楼影"], object_anchors=["桥"]),
        ]
        af = build_anchor_feature(ps)
        # primary: 天光 hit_rate=0.6 ≥ 0.5 → theme cluster, coverage=0.6 → AN.3
        # secondary: 湖面 hit_rate=0.6, 桥=0.4. 仅湖面入主题簇.
        #   secondary_coverage = 3/5 = 0.6 ∈ [1/3, 2/3) → 不动
        assert af.band == "medium"
        assert af.rule_fired == "AN.3"
        assert af.secondary_action == "none"


class TestAN4Weak:
    def test_all_different_meaning(self):
        # ADR-0020 v0.7: a_N 在真 Qwen 中高度相似, 用真实多样化 anchor
        diverse = ["nostalgia", "freedom", "curiosity", "loneliness", "joy"]
        ps = [
            make_photo(f"p{i}", meaning_anchors=[diverse[i]])
            for i in range(5)
        ]
        af = build_anchor_feature(ps)
        assert af.band == "weak"
        assert af.rule_fired == "AN.4"


class TestAN5None:
    def test_empty(self):
        af = build_anchor_feature([])
        assert af.band == "none"
        assert af.rule_fired == "AN.5"

    def test_all_meaning_empty(self):
        ps = [make_photo(f"p{i}", meaning_anchors=[]) for i in range(5)]
        af = build_anchor_feature(ps)
        # N_valid = 0 → none (即使 object 有数据)
        assert af.band == "none"
