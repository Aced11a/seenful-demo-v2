"""Event 三级分层聚合 + 匹配单测 (ADR-0009).

覆盖:
  · aggregate_event (空 / 单一 / 强主导 / 混合 / 完全分散)
  · spec §六 Case 1-5 验证
  · match_event 各档 (strong/medium/weak/none + unknown / empty)
  · build_event_aggregation 高层入口

参考: docs/15_event_aggregation.md, decisions/0009-event-aggregation.md.
"""
from __future__ import annotations

from src.contracts import EventAggregation, L1Output
from src.contracts.l1_output import ImageFacts, SemanticFacts
from src.mini_album.event_aggregation import (
    aggregate_event,
    build_event_aggregation,
    match_event,
)

CFG = {
    "primary_threshold": 0.6,
    "secondary_threshold": 0.2,
    "tertiary_min_count": 1,
}


def _mk_photo(pid: str, hint: str) -> L1Output:
    return L1Output(
        photo_id=pid,
        user_id="user_demo",
        individual_title="t",
        individual_understanding="x" * 70,
        image_facts=ImageFacts(),
        semantic_facts=SemanticFacts(event_hint=hint),  # type: ignore[arg-type]
    )


def _mk_photos(hints: list[str]) -> list[L1Output]:
    return [_mk_photo(f"p{i}", h) for i, h in enumerate(hints)]


# ═════════════════════════════════════════════════════════════════
# aggregate_event 边界
# ═════════════════════════════════════════════════════════════════

class TestAggregateEdgeCases:
    def test_empty_members(self):
        agg = aggregate_event([], CFG)
        assert agg.primary is None
        assert agg.secondary == []
        assert agg.tertiary == []
        assert agg.distribution == {}
        assert agg.total_events == 0

    def test_all_unknown(self):
        agg = aggregate_event(_mk_photos(["unknown"] * 5), CFG)
        assert agg.primary is None
        assert agg.total_events == 0

    def test_single_photo_becomes_primary(self):
        # 单张 work → 100% ≥ 60% → primary
        agg = aggregate_event(_mk_photos(["work"]), CFG)
        assert agg.primary == "work"
        assert agg.secondary == []
        assert agg.tertiary == []
        assert agg.total_events == 1


# ═════════════════════════════════════════════════════════════════
# spec §六 Case 1-5
# ═════════════════════════════════════════════════════════════════

class TestSpecCases:
    def test_case1_strong_primary(self):
        # outing×6 + meal×1 + unknown×1
        hints = ["outing"] * 6 + ["meal"] + ["unknown"]
        agg = aggregate_event(_mk_photos(hints), CFG)
        assert agg.primary == "outing"
        assert agg.secondary == []
        assert agg.tertiary == ["meal"]
        assert agg.total_events == 7

        # 匹配
        assert match_event("outing", agg).band == "strong"
        assert match_event("meal", agg).band == "weak"
        assert match_event("celebration", agg).band == "none"

    def test_case2_mixed_no_primary(self):
        # outing×4 + meal×3 (4/7 = 57% < 60%)
        hints = ["outing"] * 4 + ["meal"] * 3
        agg = aggregate_event(_mk_photos(hints), CFG)
        assert agg.primary is None
        assert set(agg.secondary) == {"outing", "meal"}
        assert agg.tertiary == []

        # 匹配
        assert match_event("outing", agg).band == "medium"
        assert match_event("meal", agg).band == "medium"
        assert match_event("study", agg).band == "none"

    def test_case2b_clear_primary(self):
        # outing×6 + meal×3 (67% ≥ 60%)
        hints = ["outing"] * 6 + ["meal"] * 3
        agg = aggregate_event(_mk_photos(hints), CFG)
        assert agg.primary == "outing"
        assert agg.secondary == ["meal"]
        assert agg.tertiary == []

        # 匹配
        assert match_event("outing", agg).band == "strong"
        assert match_event("meal", agg).band == "medium"
        assert match_event("study", agg).band == "none"

    def test_case3_completely_scattered(self):
        # 4 个 event 各 2 张 (25% 各, 都 ≥ 20% 但都 < 60%)
        hints = (
            ["outing"] * 2 + ["meal"] * 2
            + ["gathering"] * 2 + ["celebration"] * 2
        )
        agg = aggregate_event(_mk_photos(hints), CFG)
        assert agg.primary is None
        assert set(agg.secondary) == {"outing", "meal", "gathering", "celebration"}
        assert agg.tertiary == []

        # 匹配
        assert match_event("outing", agg).band == "medium"
        assert match_event("work", agg).band == "none"

    def test_case4_all_unknown_aggregation(self):
        agg = aggregate_event(_mk_photos(["unknown"] * 5), CFG)
        # 任何 event → none
        assert match_event("outing", agg).band == "none"
        assert match_event("outing", agg).reason == "empty_aggregation"
        assert match_event("unknown", agg).band == "none"

    def test_case5_single_dominant_sparse(self):
        # work×8 + meal×1 (89% work)
        hints = ["work"] * 8 + ["meal"]
        agg = aggregate_event(_mk_photos(hints), CFG)
        assert agg.primary == "work"
        assert agg.secondary == []
        assert agg.tertiary == ["meal"]

        # 匹配
        assert match_event("work", agg).band == "strong"
        assert match_event("meal", agg).band == "weak"


# ═════════════════════════════════════════════════════════════════
# match_event 各档 + 边界
# ═════════════════════════════════════════════════════════════════

class TestMatchEvent:
    def setup_method(self):
        # 通用 agg: primary=outing, secondary=[meal], tertiary=[celebration]
        self.agg = EventAggregation(
            primary="outing",
            secondary=["meal"],
            tertiary=["celebration"],
            distribution={"outing": 6, "meal": 3, "celebration": 1},
            total_events=10,
        )

    def test_strong_on_primary(self):
        r = match_event("outing", self.agg)
        assert r.band == "strong"
        assert r.matched_tier == "primary"
        assert r.reason == ""

    def test_medium_on_secondary(self):
        r = match_event("meal", self.agg)
        assert r.band == "medium"
        assert r.matched_tier == "secondary"

    def test_weak_on_tertiary(self):
        r = match_event("celebration", self.agg)
        assert r.band == "weak"
        assert r.matched_tier == "tertiary"

    def test_none_on_unrelated(self):
        r = match_event("sports", self.agg)
        assert r.band == "none"
        assert r.matched_tier == "none"
        assert r.reason == ""

    def test_unknown_event_none_with_reason(self):
        r = match_event("unknown", self.agg)
        assert r.band == "none"
        assert r.reason == "unknown_event"

    def test_empty_aggregation_none_with_reason(self):
        empty = EventAggregation(
            primary=None, secondary=[], tertiary=[], distribution={}, total_events=0,
        )
        r = match_event("outing", empty)
        assert r.band == "none"
        assert r.reason == "empty_aggregation"

    def test_diagnostics_complete(self):
        r = match_event("outing", self.agg)
        assert r.diagnostics["new_event"] == "outing"
        assert r.diagnostics["primary"] == "outing"
        assert r.diagnostics["secondary"] == ["meal"]
        assert r.diagnostics["tertiary"] == ["celebration"]


# ═════════════════════════════════════════════════════════════════
# build_event_aggregation 高层入口
# ═════════════════════════════════════════════════════════════════

class TestBuildEventAggregation:
    def test_build_from_photos(self):
        # outing×3 + meal×1: total=4, outing=75% (primary), meal=25% (≥20% → secondary)
        photos = _mk_photos(["outing"] * 3 + ["meal"])
        agg, at = build_event_aggregation(photos)
        assert agg.primary == "outing"
        assert agg.secondary == ["meal"]
        assert agg.tertiary == []
        assert at is not None

    def test_build_empty(self):
        agg, at = build_event_aggregation([])
        assert agg.total_events == 0
        assert at is not None


# ═════════════════════════════════════════════════════════════════
# 10 枚举 (ADR-0009) — 验证 contracts 接受新枚举
# ═════════════════════════════════════════════════════════════════

class TestNewEnums:
    def test_all_10_enums_accepted(self):
        # 10 枚举每个都能装进 fixture L1
        enums = [
            "meal", "outing", "gathering", "celebration",
            "performance", "sports", "work", "study",
            "daily_record", "unknown",
        ]
        for hint in enums:
            p = _mk_photo("p", hint)
            assert p.semantic_facts.event_hint == hint
