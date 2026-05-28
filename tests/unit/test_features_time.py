"""路径 B time 维度单测 (ADR-0011).

覆盖:
  - 自然日归属 (0-6 归前日)
  - 时间链式切分 (gap > eps 切, ≤ eps 连)
  - T1.1~T1.8 单日 grid 8 行
  - T2.1~T2.4 跨双日 grid 4 行
  - T3.1~T3.4 长跨 grid 4 行
  - 跨夜判定 (12h 阈值)
  - 边界保护带 (eps ± 20min → +near_eps_boundary 落痕)
  - fallback (confidence + +k_days_uncertain)

参考: docs/17_path_b_time.md, decisions/0011-time-natural-day-event-clustering.md
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.contracts import L1Output, TimeShape
from src.features.time import (
    _chain_split,
    _get_natural_date,
    _has_overnight_chain,
    build_time_feature,
)


def make_photo(pid: str, t: datetime | None, source: str = "exif") -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=t,
        captured_at_source=source,  # type: ignore[arg-type]
    )


# ─── 工具函数测试 ────────────────────────────────────────────


class TestNaturalDateAttribution:
    """0-6 归前日 (ADR-0011 §2.3)."""

    def test_dawn_3am_goes_to_previous_day(self):
        ts = datetime(2026, 5, 15, 3, 0)
        assert _get_natural_date(ts, 6) == datetime(2026, 5, 14).date()

    def test_midnight_goes_to_previous_day(self):
        ts = datetime(2026, 5, 15, 0, 0)
        assert _get_natural_date(ts, 6) == datetime(2026, 5, 14).date()

    def test_5_59_am_still_previous_day(self):
        ts = datetime(2026, 5, 15, 5, 59)
        assert _get_natural_date(ts, 6) == datetime(2026, 5, 14).date()

    def test_6_00_am_is_current_day(self):
        ts = datetime(2026, 5, 15, 6, 0)
        assert _get_natural_date(ts, 6) == datetime(2026, 5, 15).date()

    def test_afternoon_is_current_day(self):
        ts = datetime(2026, 5, 15, 14, 0)
        assert _get_natural_date(ts, 6) == datetime(2026, 5, 15).date()


class TestChainSplit:
    """gap > eps 切, ≤ eps 连 (ADR-0011 §2.4)."""

    def test_empty(self):
        clusters, near = _chain_split([], 120, 20)
        assert clusters == [] and near == 0

    def test_single_point(self):
        ts = [datetime(2026, 5, 1, 12, 0)]
        clusters, near = _chain_split(ts, 120, 20)
        assert len(clusters) == 1 and len(clusters[0]) == 1
        assert near == 0

    def test_all_within_eps(self):
        ts = [
            datetime(2026, 5, 1, 12, 0),
            datetime(2026, 5, 1, 12, 30),
            datetime(2026, 5, 1, 13, 0),
        ]
        clusters, near = _chain_split(ts, 120, 20)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_gap_above_eps_splits(self):
        ts = [
            datetime(2026, 5, 1, 9, 0),
            datetime(2026, 5, 1, 13, 0),  # gap = 240 min > 120 切
        ]
        clusters, near = _chain_split(ts, 120, 20)
        assert len(clusters) == 2

    def test_near_eps_boundary_counted(self):
        # gap = 130min ∈ [100, 140] → near +1
        ts = [
            datetime(2026, 5, 1, 12, 0),
            datetime(2026, 5, 1, 14, 10),
        ]
        _, near = _chain_split(ts, 120, 20)
        assert near == 1

    def test_far_from_eps_not_counted(self):
        # gap = 150min > 140, 不算边界
        ts = [
            datetime(2026, 5, 1, 12, 0),
            datetime(2026, 5, 1, 14, 30),
        ]
        _, near = _chain_split(ts, 120, 20)
        assert near == 0


class TestOvernightChain:
    """跨夜 12h 阈值 (ADR-0011 §2.5 T2.1)."""

    def test_overnight_within_12h(self):
        day1 = [[datetime(2026, 5, 1, 21, 0)]]
        day2 = [[datetime(2026, 5, 2, 8, 0)]]
        assert _has_overnight_chain(day1, day2, 12) is True

    def test_gap_exactly_13h_not_overnight(self):
        day1 = [[datetime(2026, 5, 1, 19, 0)]]
        day2 = [[datetime(2026, 5, 2, 8, 0)]]
        assert _has_overnight_chain(day1, day2, 12) is False

    def test_empty_returns_false(self):
        assert _has_overnight_chain([], [], 12) is False


# ─── T1 单日 grid (8 行) ─────────────────────────────────────


class TestT1Grid:
    def test_t1_1_lunch_burst_strong(self):
        """T1.1: events=1, day_span ≤ 2h → strong."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 12, 0)),
            make_photo("p2", datetime(2026, 5, 1, 12, 5)),
            make_photo("p3", datetime(2026, 5, 1, 12, 30)),
        ]
        tf = build_time_feature(ps)
        assert tf.band == "strong"
        assert tf.shape == TimeShape.SINGLE_EVENT_DENSE
        assert tf.rule_fired.startswith("T1.1")
        assert tf.max_events_in_any_day == 1

    def test_t1_2_single_extended_strong(self):
        """T1.2: events=1, day_span > 2h → strong."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 9, 0)),
            make_photo("p2", datetime(2026, 5, 1, 10, 30)),
            make_photo("p3", datetime(2026, 5, 1, 11, 30)),  # 90min gap, 同 cluster
        ]
        tf = build_time_feature(ps)
        assert tf.band == "strong"
        assert tf.shape == TimeShape.SINGLE_EVENT_EXTENDED
        assert tf.rule_fired.startswith("T1.2")

    def test_t1_3_adjacent_events_strong(self):
        """T1.3: events=2, gap < 4h → strong."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 12, 30)),
            make_photo("p2", datetime(2026, 5, 1, 15, 30)),  # gap=180 切
        ]
        tf = build_time_feature(ps)
        assert tf.band == "strong"
        assert tf.shape == TimeShape.ADJACENT_EVENTS
        assert tf.rule_fired.startswith("T1.3")
        assert tf.max_events_in_any_day == 2

    def test_t1_4_distant_events_medium(self):
        """T1.4: events=2, gap ≥ 4h → medium."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 9, 0)),
            make_photo("p2", datetime(2026, 5, 1, 15, 0)),  # gap=6h
        ]
        tf = build_time_feature(ps)
        assert tf.band == "medium"
        assert tf.shape == TimeShape.DISTANT_EVENTS
        assert tf.rule_fired.startswith("T1.4")

    def test_t1_5_extended_chain_strong_westlake(self):
        """T1.5 v0.2: events∈[3,5], gaps<4h, span≤12h → strong.

        西湖一日游 5 张 — events=3 (cluster: [9] / [11:30,13,15] / [17:30]).
        """
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 9, 0)),
            make_photo("p2", datetime(2026, 5, 1, 11, 30)),
            make_photo("p3", datetime(2026, 5, 1, 13, 0)),
            make_photo("p4", datetime(2026, 5, 1, 15, 0)),
            make_photo("p5", datetime(2026, 5, 1, 17, 30)),
        ]
        tf = build_time_feature(ps)
        assert tf.band == "strong"
        assert tf.shape == TimeShape.EXTENDED_CHAIN
        assert tf.rule_fired.startswith("T1.5")
        assert tf.max_events_in_any_day == 3

    def test_t1_6_dense_chain_medium(self):
        """T1.6: events ≥ 6, gaps<4h, span≤12h → medium.

        构造 6 个 cluster, 相邻 gap=130min (>120 切, 落边界保护带),
        span = 5 × 130min = 650min ≈ 10h50m ≤ 12h, gaps < 4h.
        """
        from datetime import timedelta
        start = datetime(2026, 5, 1, 9, 0)
        ps = [
            make_photo(f"p{i}", start + timedelta(minutes=130 * i))
            for i in range(6)
        ]
        tf = build_time_feature(ps)
        assert tf.max_events_in_any_day == 6
        assert tf.band == "medium"
        assert tf.shape == TimeShape.DENSE_CHAIN
        assert tf.rule_fired.startswith("T1.6")
        # 130min ∈ [100, 140] 边界保护带, 全部 5 个 gap 都落带 → 落痕
        assert tf.near_eps_boundary_count == 5
        assert "+near_eps_boundary" in tf.rule_fired

    def test_t1_7_three_meals_weak(self):
        """T1.7: events≥3, 任一 gap ≥ 4h → weak (早午晚)."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 9, 0)),
            make_photo("p2", datetime(2026, 5, 1, 13, 0)),
            make_photo("p3", datetime(2026, 5, 1, 19, 0)),
        ]
        tf = build_time_feature(ps)
        assert tf.band == "weak"
        assert tf.shape == TimeShape.MULTI_EVENTS_BREAK
        assert tf.rule_fired.startswith("T1.7")

    def test_t1_8_overstretched_weak(self):
        """T1.8: events≥3, gaps<4h, span > 12h → weak.

        构造: 3 个 cluster, 每相邻 gap=3h, 第一个 9:00, 最后 21:00, span=12h (临界).
        放宽到 22:00 让 span=13 > 12.
        """
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 9, 0)),
            make_photo("p2", datetime(2026, 5, 1, 12, 30)),  # gap 3.5h
            make_photo("p3", datetime(2026, 5, 1, 16, 0)),   # gap 3.5h
            make_photo("p4", datetime(2026, 5, 1, 22, 30)),  # gap 6.5h ≥ 4h, 命中 T1.7 instead
        ]
        # 上面 p4 gap=6.5h 会先命中 T1.7. 改造: 全部相邻 gap < 4h 但 span > 12h
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 9, 0)),
            make_photo("p2", datetime(2026, 5, 1, 12, 30)),
            make_photo("p3", datetime(2026, 5, 1, 16, 0)),
            make_photo("p4", datetime(2026, 5, 1, 19, 30)),
            make_photo("p5", datetime(2026, 5, 1, 22, 30)),
        ]
        tf = build_time_feature(ps)
        # span = 13.5h > 12h; 所有 gap=3.5h or 3h < 4h
        assert tf.band == "weak"
        assert tf.shape == TimeShape.OVERSTRETCHED_CHAIN
        assert tf.rule_fired.startswith("T1.8")


# ─── T2 跨双日 grid (4 行) ───────────────────────────────────


class TestT2Grid:
    def test_t2_1_overnight_strong(self):
        """T2.1: 跨夜 + 各日 events ≤ 2 → strong."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 19, 0)),
            make_photo("p2", datetime(2026, 5, 1, 21, 0)),  # day1 single cluster (gap 2h)
            make_photo("p3", datetime(2026, 5, 2, 8, 0)),   # day2 single cluster
        ]
        tf = build_time_feature(ps)
        assert tf.band == "strong"
        assert tf.shape == TimeShape.OVERNIGHT
        assert tf.rule_fired.startswith("T2.1")
        assert tf.has_overnight_chain is True

    def test_t2_2_weekend_trip_medium(self):
        """T2.2: 无跨夜 + 各日 events ≤ 2 + 总跨 < 30h → medium."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 10, 0)),
            make_photo("p2", datetime(2026, 5, 2, 15, 0)),  # gap 29h
        ]
        tf = build_time_feature(ps)
        assert tf.band == "medium"
        assert tf.shape == TimeShape.WEEKEND_TRIP
        assert tf.rule_fired.startswith("T2.2")
        assert tf.has_overnight_chain is False

    def test_t2_3_sparse_two_days_weak(self):
        """T2.3: 某日 events ≥ 3 → weak."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 9, 0)),
            make_photo("p2", datetime(2026, 5, 1, 13, 0)),  # day1 events=2 (gap=240 切)
            make_photo("p3", datetime(2026, 5, 1, 19, 0)),  # day1 events=3
            make_photo("p4", datetime(2026, 5, 2, 10, 0)),  # day2 events=1
        ]
        tf = build_time_feature(ps)
        assert tf.band == "weak"
        assert tf.shape == TimeShape.SPARSE_TWO_DAYS


# ─── T3 长跨 grid (4 行) ─────────────────────────────────────


class TestT3Grid:
    def test_t3_1_short_trip_medium(self):
        """T3.1: K_days∈[3,7], 无空日 → medium."""
        ps = [
            make_photo(f"p{i}", datetime(2026, 5, i, 12, 0))
            for i in range(1, 6)  # 5 天连续
        ]
        tf = build_time_feature(ps)
        assert tf.band == "medium"
        assert tf.shape == TimeShape.SHORT_TRIP
        assert tf.rule_fired.startswith("T3.1")
        assert tf.unique_days_count == 5

    def test_t3_2_sparse_short_trip_weak(self):
        """T3.2: K_days∈[3,7], 中间有空日 → weak."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 12, 0)),
            make_photo("p2", datetime(2026, 5, 2, 12, 0)),
            # 5/3 空
            make_photo("p3", datetime(2026, 5, 4, 12, 0)),
        ]
        tf = build_time_feature(ps)
        assert tf.band == "weak"
        assert tf.shape == TimeShape.SPARSE_SHORT_TRIP
        assert tf.has_empty_days is True

    def test_t3_3_long_trip_weak(self):
        """T3.3: K_days∈[8,14] → weak."""
        ps = [
            make_photo(f"p{i}", datetime(2026, 5, i, 12, 0))
            for i in range(1, 11)  # 10 天
        ]
        tf = build_time_feature(ps)
        assert tf.band == "weak"
        assert tf.shape == TimeShape.LONG_TRIP

    def test_t3_4_scattered_long_none(self):
        """T3.4: K_days > 14 → none."""
        ps = [
            make_photo(f"p{i}", datetime(2026, 5, i, 12, 0))
            for i in range(1, 21)  # 20 天
        ]
        tf = build_time_feature(ps)
        assert tf.band == "none"
        assert tf.shape == TimeShape.SCATTERED_LONG


# ─── 自然日归属影响 K_days (Case 8) ──────────────────────────


class TestDawnAttribution:
    def test_3am_plus_9am_becomes_overnight_t21(self):
        """Case 8: [03:00, 09:00] 同一日历日 → 凌晨归前日 → K_days=2 → T2.1.

        03:00 归前一日 night, 09:00 归本日, gap=6h < 12h → overnight.
        """
        ps = [
            make_photo("p1", datetime(2026, 5, 15, 3, 0)),
            make_photo("p2", datetime(2026, 5, 15, 9, 0)),
        ]
        tf = build_time_feature(ps)
        assert tf.unique_days_count == 2
        assert tf.has_dawn_photos is True
        assert tf.band == "strong"
        assert tf.shape == TimeShape.OVERNIGHT


# ─── 边界保护带 ──────────────────────────────────────────────


class TestNearEpsBoundary:
    def test_gap_130min_falls_in_boundary(self):
        """gap=130min ∈ [100, 140] → +near_eps_boundary 落痕."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 12, 0)),
            make_photo("p2", datetime(2026, 5, 1, 14, 10)),  # gap=130min, 切 (> 120)
        ]
        tf = build_time_feature(ps)
        assert tf.near_eps_boundary_count == 1
        assert "+near_eps_boundary" in tf.rule_fired

    def test_gap_150min_not_in_boundary(self):
        """gap=150min > 140 → 不落痕."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 12, 0)),
            make_photo("p2", datetime(2026, 5, 1, 14, 30)),  # gap=150min
        ]
        tf = build_time_feature(ps)
        assert tf.near_eps_boundary_count == 0
        assert "+near_eps_boundary" not in tf.rule_fired


# ─── Fallback ────────────────────────────────────────────────


class TestFallback:
    def test_full_fallback_confidence_05(self):
        """所有 fallback → confidence=0.5 + +k_days_uncertain."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 12, 0), "upload_time_fallback"),
            make_photo("p2", datetime(2026, 5, 1, 12, 30), "upload_time_fallback"),
        ]
        tf = build_time_feature(ps)
        assert tf.fallback_ratio == 1.0
        assert tf.confidence == 0.5
        assert "+k_days_uncertain" in tf.rule_fired
        # band 不动
        assert tf.band == "strong"

    def test_partial_fallback_confidence_decay(self):
        """50% fallback → confidence ≈ 0.85."""
        ps = [
            make_photo("p1", datetime(2026, 5, 1, 12, 0), "exif"),
            make_photo("p2", datetime(2026, 5, 1, 12, 30), "upload_time_fallback"),
        ]
        tf = build_time_feature(ps)
        assert tf.fallback_ratio == 0.5
        assert tf.confidence == pytest.approx(1.0 - 0.5 * 0.3)
        assert "+k_days_uncertain" not in tf.rule_fired

    def test_no_fallback_full_confidence(self):
        ps = [make_photo("p1", datetime(2026, 5, 1, 12, 0))]
        tf = build_time_feature(ps)
        assert tf.confidence == 1.0


# ─── 边界 case ───────────────────────────────────────────────


class TestBoundary:
    def test_empty_returns_none_band(self):
        tf = build_time_feature([])
        assert tf.band == "none"
        assert tf.rule_fired.startswith("T0")
        assert tf.unique_days_count == 0
        assert tf.shape == TimeShape.NO_TIMESTAMP

    def test_all_no_timestamp_returns_none(self):
        ps = [make_photo("p1", None), make_photo("p2", None)]
        tf = build_time_feature(ps)
        assert tf.band == "none"
        assert tf.shape == TimeShape.NO_TIMESTAMP

    def test_single_photo_strong(self):
        ps = [make_photo("p1", datetime(2026, 5, 1, 12, 0))]
        tf = build_time_feature(ps)
        assert tf.band == "strong"
        assert tf.unique_days_count == 1
        assert tf.max_events_in_any_day == 1
