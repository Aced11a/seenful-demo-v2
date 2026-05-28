"""ADR-0017: cascade_backfill_single + rank_and_pick_top_n 单测.

参考: docs/23_pipeline_cascade_backfill.md
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.candidate_builder.backfill_scan import (
    cap_sediment_pool,
    rank_and_pick_top_n,
)
from src.contracts import L1Output
from src.contracts.l1_output import ImageFacts, SafetyFlags, SemanticFacts
from src.policy.cascade_backfill import cascade_backfill_single


NOW = datetime(2026, 5, 10, tzinfo=timezone.utc)


def mk(
    pid: str,
    captured: datetime,
    gps: tuple[float, float] | None = (30.28, 120.16),
    theme: list[str] | None = None,
    event: str = "outing",
    sensitive: str = "none",
) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=captured,
        theme_tags=theme if theme is not None else ["sunset"],
        image_facts=ImageFacts(exif_location=gps) if gps else ImageFacts(),
        safety_flags=SafetyFlags(sensitive_level=sensitive),  # type: ignore[arg-type]
        semantic_facts=SemanticFacts(event_hint=event),  # type: ignore[arg-type]
    )


# ═════════════════════════════════════════════════════════════════
# rank_and_pick_top_n
# ═════════════════════════════════════════════════════════════════

class TestRankAndPickTopN:
    """ADR-0017 维度强度总分排序 + top N 选择."""

    def setup_method(self):
        # 默认权重 (跟 config 一致)
        self.weights = {"gps": 1.0, "theme": 1.0, "event": 0.5}

    def test_all_three_dims_hit_max_score(self):
        """gps + theme + event 全过 = 2.5 分 (最高)."""
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["sunset", "city"], event="outing")
        cand = mk("c1", NOW - timedelta(days=1),
                  gps=(30.281, 120.161), theme=["sunset", "city"], event="outing")
        selected, ranking = rank_and_pick_top_n(new, [cand], n=4, weights=self.weights)
        assert len(selected) == 1
        assert ranking[0].score == 2.5
        assert ranking[0].selected is True

    def test_gps_only_score_1(self):
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["sunset"], event="outing")
        cand = mk("c1", NOW - timedelta(days=1),
                  gps=(30.281, 120.161), theme=["meal"], event="study")
        # 跨过 GPS 阈值, theme/event 都不过
        _, ranking = rank_and_pick_top_n(new, [cand], n=4, weights=self.weights)
        # 注意: jaccard({sunset},{meal}) = 0 < 0.5, fail
        assert ranking[0].gps_within_1km is True
        assert ranking[0].theme_jaccard_above_0_5 is False
        assert ranking[0].event_match is False
        assert ranking[0].score == 1.0

    def test_event_only_score_0_5(self):
        """event 单独命中 = 0.5 分 (最低非零, ADR-0017 核心降权)."""
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["sunset"], event="outing")
        cand = mk("c1", NOW - timedelta(days=1),
                  gps=(30.32, 120.20), theme=["meal"], event="outing")   # GPS 远 + theme 不重 + event 同
        _, ranking = rank_and_pick_top_n(new, [cand], n=4, weights=self.weights)
        assert ranking[0].event_match is True
        assert ranking[0].score == 0.5

    def test_event_downweight_vs_gps(self):
        """核心场景: 5 候选 4 张 event 一致 + 1 张 GPS 命中, top 1 = GPS.

        没降权 (event=1) 时, 4 张 event 一致都比 GPS=1 高, GPS 候选被排到第 5.
        降权 (event=0.5) 后, GPS 候选 score=1 > 任一 event-only score=0.5, GPS 排第 1.
        """
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["alpha"], event="outing")
        # 4 张 event 一致但 GPS 远 + theme 不重
        events = [
            mk(f"e{i}", NOW - timedelta(days=i),
               gps=(30.32 + i*0.01, 120.20), theme=["beta"], event="outing")
            for i in range(1, 5)
        ]
        # 1 张 GPS 命中但 theme/event 都不对
        gps_only = mk("g1", NOW - timedelta(days=10),
                      gps=(30.281, 120.161), theme=["gamma"], event="meal")
        selected, ranking = rank_and_pick_top_n(
            new, events + [gps_only], n=4, weights=self.weights,
        )
        # top 1 应该是 GPS 那张
        top_1_id = selected[0].photo_id
        assert top_1_id == "g1", f"event 降权失败, top 1 = {top_1_id} 不是 g1"
        # ranking 中 g1 的 score=1.0
        g1_entry = next(r for r in ranking if r.photo_id == "g1")
        assert g1_entry.score == 1.0
        assert g1_entry.selected is True

    def test_tie_break_by_captured_at(self):
        """同分时, captured_at 倒序 (最近优先)."""
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["sunset"], event="outing")
        # 两张都 event-only 命中 = 0.5 分
        older = mk("older", NOW - timedelta(days=20),
                   gps=(30.32, 120.20), theme=["x"], event="outing")
        newer = mk("newer", NOW - timedelta(days=2),
                   gps=(30.32, 120.20), theme=["x"], event="outing")
        selected, _ = rank_and_pick_top_n(new, [older, newer], n=1, weights=self.weights)
        assert selected[0].photo_id == "newer"

    def test_top_n_capped_at_4(self):
        """召回上限 4 张 (PRD §3.10.5)."""
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["sunset"], event="outing")
        # 6 张都 GPS 命中 = 1.0 分
        cands = [
            mk(f"c{i}", NOW - timedelta(days=i),
               gps=(30.281 + i*0.0001, 120.161), theme=["x"], event="meal")
            for i in range(6)
        ]
        selected, ranking = rank_and_pick_top_n(new, cands, n=4, weights=self.weights)
        assert len(selected) == 4
        # 6 个都进 ranking, 但只 4 个 selected
        selected_count = sum(1 for r in ranking if r.selected)
        assert selected_count == 4

    def test_empty_candidates_returns_empty(self):
        new = mk("new", NOW)
        selected, ranking = rank_and_pick_top_n(new, [], n=4, weights=self.weights)
        assert selected == []
        assert ranking == []


# ═════════════════════════════════════════════════════════════════
# cap_sediment_pool
# ═════════════════════════════════════════════════════════════════

class TestCapSedimentPool:
    """ADR-0017 沉淀池上限."""

    def test_cap_returns_most_recent_n(self):
        pool = [
            mk(f"p{i}", NOW - timedelta(days=i*2))
            for i in range(10)
        ]
        capped = cap_sediment_pool(pool, max_size=3)
        assert len(capped) == 3
        # 最新的 3 张 (days=0, 2, 4)
        ids = [p.photo_id for p in capped]
        assert ids == ["p0", "p1", "p2"]

    def test_cap_under_limit_returns_all(self):
        pool = [mk("p1", NOW), mk("p2", NOW - timedelta(days=1))]
        capped = cap_sediment_pool(pool, max_size=50)
        assert len(capped) == 2


# ═════════════════════════════════════════════════════════════════
# cascade_backfill_single
# ═════════════════════════════════════════════════════════════════

class TestCascadeBackfillSingle:
    """ADR-0017 cascade 单次端到端 (粗筛 → 排序 → caps)."""

    def test_empty_pool_returns_insufficient(self):
        new = mk("new", NOW)
        log = cascade_backfill_single(new, [])
        assert log.final_decision.decision_tier == "insufficient_candidates"
        assert log.coarse_filter_candidates == []
        assert log.priority_ranking == []

    def test_only_1_candidate_after_filter_insufficient_via_caps(self):
        """候选只 1 张 → CAP-03 (min_recalled_photos=2) 不过."""
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["sunset"], event="outing")
        # 1 张 GPS 命中
        pool = [mk("p1", NOW - timedelta(days=5),
                   gps=(30.281, 120.161), theme=["x"], event="meal")]
        log = cascade_backfill_single(new, pool)
        # 召回 1 张, < 2, CAP-03 不过 → no_backfill 或 insufficient
        assert log.final_decision.decision_tier in (
            "no_backfill", "insufficient_candidates",
        )

    def test_priority_ranking_populated(self):
        """priority_ranking 字段被填充 (ADR-0017 落痕)."""
        new = mk("new", NOW, gps=(30.28, 120.16), theme=["sunset"], event="outing")
        pool = [
            mk("p1", NOW - timedelta(days=5),
               gps=(30.281, 120.161), theme=["sunset"], event="outing"),
            mk("p2", NOW - timedelta(days=10),
               gps=(30.282, 120.162), theme=["sunset"], event="outing"),
        ]
        log = cascade_backfill_single(new, pool)
        assert len(log.priority_ranking) == 2
        # 两张都进 top 4 (因为 max_recall=4)
        assert all(r.selected for r in log.priority_ranking)
