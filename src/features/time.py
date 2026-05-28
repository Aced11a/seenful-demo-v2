"""路径 B Time 维度 (ADR-0011): 自然日归属 + 时间链式切分 + 三路 grid.

参考:
  docs/17_path_b_time.md (完整算法规范)
  decisions/0011-time-natural-day-event-clustering.md
  config/path_b_time.yaml

输出: TimeFeature (含 band 终值 + 完整诊断字段)

⚠ 不是 DBSCAN: min_samples=1 时退化为 gap > eps 链式切分.
  跟 ADR-0010 location 真 DBSCAN 在输出范式 (band + rule_fired + shape) 同构,
  但底层算法不同源 — 见 Time_Aggregation_Spec.md v0.2 §2.2 命名澄清.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from src.contracts import BandLevel, L1Output, TimeFeature, TimeShape
from src.policy.config_loader import load_config


# ─── 自然日归属 (ADR-0011 §2.3) ──────────────────────────────


def _get_natural_date(ts: datetime, dawn_cutoff_hour: int) -> date:
    """0-6 点归"前一日 night", 其他归本日.

    例: 2026-05-15 03:00 → 2026-05-14 (前一日)
        2026-05-15 06:00 → 2026-05-15 (本日)
        2026-05-15 14:00 → 2026-05-15
    """
    if 0 <= ts.hour < dawn_cutoff_hour:
        return (ts - timedelta(days=1)).date()
    return ts.date()


# ─── 时间链式切分 (ADR-0011 §2.4, 非 DBSCAN) ─────────────────


def _chain_split(
    timestamps_sorted: list[datetime],
    eps_minutes: float,
    delta_minutes: float,
) -> tuple[list[list[datetime]], int]:
    """gap > eps → 切; gap ≤ eps → 连. 同时计 near_eps_boundary 次数.

    输入: 同一自然日内的 timestamp, 已排序.
    输出: (clusters, near_eps_count)
      clusters: list of cluster (each cluster is list of datetime)
      near_eps_count: 切分时 gap 落 [eps - δ, eps + δ] 的次数

    ⚠ min_samples 固定 1, 单点也成 cluster.
    """
    if not timestamps_sorted:
        return [], 0
    clusters: list[list[datetime]] = [[timestamps_sorted[0]]]
    near_count = 0
    for i in range(1, len(timestamps_sorted)):
        prev = timestamps_sorted[i - 1]
        curr = timestamps_sorted[i]
        gap_min = (curr - prev).total_seconds() / 60.0
        if abs(gap_min - eps_minutes) <= delta_minutes:
            near_count += 1
        if gap_min > eps_minutes:
            clusters.append([curr])
        else:
            clusters[-1].append(curr)
    return clusters, near_count


# ─── 每日 events 聚合 ────────────────────────────────────────


def _group_by_natural_day(
    timestamps_sorted: list[datetime],
    dawn_cutoff_hour: int,
) -> dict[date, list[datetime]]:
    """按自然日归属聚合 timestamps (输入已排序)."""
    by_day: dict[date, list[datetime]] = {}
    for ts in timestamps_sorted:
        d = _get_natural_date(ts, dawn_cutoff_hour)
        by_day.setdefault(d, []).append(ts)
    return by_day


# ─── 跨夜判定 (ADR-0011 §2.5 T2.1) ───────────────────────────


def _has_overnight_chain(
    day1_clusters: list[list[datetime]],
    day2_clusters: list[list[datetime]],
    max_gap_hours: float,
) -> bool:
    """day1 末事件结束 → day2 首事件开始 gap < max_gap_hours."""
    if not day1_clusters or not day2_clusters:
        return False
    day1_last = day1_clusters[-1][-1]
    day2_first = day2_clusters[0][0]
    gap_h = (day2_first - day1_last).total_seconds() / 3600.0
    return gap_h < max_gap_hours


# ─── T1 单日网格 (8 行, ADR-0011 §2.4) ───────────────────────


def _step_t1_grid(
    events_today: int,
    max_inter_cluster_gap_h: float | None,
    day_span_h: float,
    cfg: dict,
) -> tuple[BandLevel, TimeShape, str]:
    """单日 (K_days=1) 8 行 grid, 按行顺序匹配."""
    t1 = cfg["t1_grid"]
    single_max_h = float(t1["single_event_dense_max_h"])
    adj_gap_max_h = float(t1["adjacent_gap_max_h"])
    ec_max_span_h = float(t1["extended_chain_max_span_h"])
    ec_events_max = int(t1["extended_chain_events_max"])
    dense_events_min = int(t1["dense_chain_events_min"])

    # T1.1 / T1.2: single event
    if events_today == 1:
        if day_span_h <= single_max_h:
            return "strong", TimeShape.SINGLE_EVENT_DENSE, "T1.1"
        return "strong", TimeShape.SINGLE_EVENT_EXTENDED, "T1.2"

    # T1.3 / T1.4: 2 events
    if events_today == 2:
        gap_h = max_inter_cluster_gap_h if max_inter_cluster_gap_h is not None else 0.0
        if gap_h < adj_gap_max_h:
            return "strong", TimeShape.ADJACENT_EVENTS, "T1.3"
        return "medium", TimeShape.DISTANT_EVENTS, "T1.4"

    # events_today ≥ 3
    gap_h = max_inter_cluster_gap_h if max_inter_cluster_gap_h is not None else 0.0
    all_gaps_under_4h = gap_h < adj_gap_max_h
    span_under_12h = day_span_h <= ec_max_span_h

    # T1.7: 任一 gap ≥ 4h
    if not all_gaps_under_4h:
        return "weak", TimeShape.MULTI_EVENTS_BREAK, "T1.7"
    # T1.8: 跨度 > 12h
    if not span_under_12h:
        return "weak", TimeShape.OVERSTRETCHED_CHAIN, "T1.8"
    # T1.5: events ∈ [3, 5]
    if events_today <= ec_events_max:
        return "strong", TimeShape.EXTENDED_CHAIN, "T1.5"
    # T1.6: events ≥ 6
    if events_today >= dense_events_min:
        return "medium", TimeShape.DENSE_CHAIN, "T1.6"
    # 兜底 (events_today = 4 或 5 已被 T1.5 接, 不应到此)
    return "weak", TimeShape.MULTI_EVENTS_BREAK, "T1.7"


# ─── T2 跨双日网格 (4 行) ────────────────────────────────────


def _step_t2_grid(
    events_per_day_list: list[int],
    has_overnight: bool,
    total_span_h: float,
    cfg: dict,
) -> tuple[BandLevel, TimeShape, str]:
    """跨双日 (K_days=2) 4 行 grid."""
    t2 = cfg["t2_grid"]
    each_max = int(t2["each_day_events_max"])
    span_max_h = float(t2["total_span_max_h"])

    each_day_within = all(e <= each_max for e in events_per_day_list)

    # T2.1: 跨夜 + 各日 events ≤ 2
    if has_overnight and each_day_within:
        return "strong", TimeShape.OVERNIGHT, "T2.1"
    # T2.2: 无跨夜 + 各日 events ≤ 2 + 总跨 < 30h
    if not has_overnight and each_day_within and total_span_h < span_max_h:
        return "medium", TimeShape.WEEKEND_TRIP, "T2.2"
    # T2.3 / T2.4: 其他都 weak
    return "weak", TimeShape.SPARSE_TWO_DAYS, "T2.3" if not each_day_within else "T2.4"


# ─── T3 长跨网格 (4 行, cap medium) ──────────────────────────


def _step_t3_grid(
    k_days: int,
    has_empty: bool,
    cfg: dict,
) -> tuple[BandLevel, TimeShape, str]:
    """长跨 (K_days ≥ 3) 4 行 grid."""
    t3 = cfg["t3_grid"]
    short_max = int(t3["short_trip_max_days"])
    long_max = int(t3["long_trip_max_days"])

    if k_days <= short_max:
        if not has_empty:
            return "medium", TimeShape.SHORT_TRIP, "T3.1"
        return "weak", TimeShape.SPARSE_SHORT_TRIP, "T3.2"
    if k_days <= long_max:
        return "weak", TimeShape.LONG_TRIP, "T3.3"
    return "none", TimeShape.SCATTERED_LONG, "T3.4"


# ─── 派生 score (展示用, 真值表不读) ─────────────────────────


def _band_to_score(band: BandLevel) -> float:
    """band 终值 → 展示 score (与 ADR-0010 location 一致)."""
    return {"strong": 0.9, "medium": 0.7, "weak": 0.4, "none": 0.1}[band]


# ─── 高层入口 ────────────────────────────────────────────────


def build_time_feature(photos: list[L1Output]) -> TimeFeature:
    """从 photos 构造 TimeFeature (ADR-0011 直出 band).

    流水线 (docs/17 §2.1):
      Phase 1: 自然日归属
      Phase 2: K_days 分流 → T1/T2/T3 grid
      Phase 3: 边界保护带计数 → +near_eps_boundary
      Phase 4: fallback → confidence + 可能 +k_days_uncertain
    """
    cfg = load_config("path_b_time.yaml")["path_b_time"]

    chain_cfg = cfg["chain_segmentation"]
    eps_min = float(chain_cfg["eps_minutes"])
    near_cfg = cfg["near_eps_band"]
    delta_min = float(near_cfg["delta_minutes"])
    nat_cfg = cfg["natural_day"]
    dawn_h = int(nat_cfg["dawn_cutoff_hour"])
    over_cfg = cfg["overnight"]
    overnight_max_h = float(over_cfg["max_gap_hours"])
    fb_cfg = cfg["fallback"]
    full_fb_conf = float(fb_cfg["full_fallback_confidence"])
    partial_penalty = float(fb_cfg["partial_confidence_penalty"])

    # 收集 timestamps (None 排除)
    times: list[datetime] = sorted(p.captured_at for p in photos if p.captured_at is not None)

    # ─── Phase 4 fallback 统计 (band 不动, 但 confidence + 可能加 rule 后缀) ───
    fallback_count = sum(1 for p in photos if p.captured_at_source == "upload_time_fallback")
    total = max(1, len(photos))
    fallback_ratio = fallback_count / total
    if fallback_ratio == 1.0:
        confidence = full_fb_conf
        fallback_suffix = "+k_days_uncertain"
    elif fallback_ratio > 0:
        confidence = max(0.0, 1.0 - fallback_ratio * partial_penalty)
        fallback_suffix = ""
    else:
        confidence = 1.0
        fallback_suffix = ""

    # ─── K_days = 0: 无 timestamp ───────────────────────────
    if not times:
        return TimeFeature(
            band="none",
            rule_fired="T0" + fallback_suffix,
            score=_band_to_score("none"),
            unique_days_count=0,
            span_days=0,
            has_empty_days=False,
            events_per_day={},
            max_events_in_any_day=0,
            total_span_hours=0.0,
            max_inter_cluster_gap_h=None,
            max_intra_cluster_span_h=None,
            has_overnight_chain=False,
            has_dawn_photos=False,
            near_eps_boundary_count=0,
            fallback_count=fallback_count,
            fallback_ratio=fallback_ratio,
            confidence=confidence,
            shape=TimeShape.NO_TIMESTAMP,
        )

    # ─── Phase 1: 自然日归属 + 分组 ─────────────────────────
    by_day = _group_by_natural_day(times, dawn_h)
    sorted_days = sorted(by_day.keys())
    k_days = len(sorted_days)
    span_days = (sorted_days[-1] - sorted_days[0]).days + 1
    has_empty = span_days > k_days
    has_dawn = any(0 <= ts.hour < dawn_h for ts in times)
    total_span_h = (times[-1] - times[0]).total_seconds() / 3600.0

    # 每日链式切分
    per_day_clusters: dict[date, list[list[datetime]]] = {}
    total_near_count = 0
    for d in sorted_days:
        day_ts = by_day[d]
        clusters, near_count = _chain_split(day_ts, eps_min, delta_min)
        per_day_clusters[d] = clusters
        total_near_count += near_count

    events_per_day_map = {d.isoformat(): len(per_day_clusters[d]) for d in sorted_days}
    max_events = max(events_per_day_map.values()) if events_per_day_map else 0

    # 单日几何 (仅 K_days=1 计)
    max_inter_gap_h: float | None = None
    max_intra_span_h: float | None = None
    day_span_h = 0.0
    if k_days == 1:
        only_day = sorted_days[0]
        clusters = per_day_clusters[only_day]
        # day_span: 该日最早 ~ 最晚跨度 (h)
        day_ts = by_day[only_day]
        day_span_h = (day_ts[-1] - day_ts[0]).total_seconds() / 3600.0
        # max_inter_cluster_gap_h: cluster 与 cluster 之间最大 gap
        if len(clusters) >= 2:
            inter_gaps: list[float] = []
            for i in range(len(clusters) - 1):
                end = clusters[i][-1]
                start = clusters[i + 1][0]
                inter_gaps.append((start - end).total_seconds() / 3600.0)
            max_inter_gap_h = max(inter_gaps)
        else:
            max_inter_gap_h = 0.0
        # max_intra_cluster_span_h: cluster 内最大 span
        intra_spans = [
            (c[-1] - c[0]).total_seconds() / 3600.0
            for c in clusters
            if len(c) >= 2
        ]
        max_intra_span_h = max(intra_spans) if intra_spans else 0.0

    # 跨双日 overnight chain (仅 K_days=2 算)
    has_overnight = False
    if k_days == 2:
        d1, d2 = sorted_days
        has_overnight = _has_overnight_chain(
            per_day_clusters[d1], per_day_clusters[d2], overnight_max_h
        )

    # ─── Phase 2: K_days 分流 ────────────────────────────────
    if k_days == 1:
        band, shape, rule = _step_t1_grid(
            max_events, max_inter_gap_h, day_span_h, cfg
        )
    elif k_days == 2:
        events_list = [len(per_day_clusters[d]) for d in sorted_days]
        band, shape, rule = _step_t2_grid(
            events_list, has_overnight, total_span_h, cfg
        )
    else:
        band, shape, rule = _step_t3_grid(k_days, has_empty, cfg)

    # ─── Phase 3: 边界保护带落痕 ─────────────────────────────
    rule_fired = rule
    if total_near_count > 0:
        rule_fired += "+near_eps_boundary"
    rule_fired += fallback_suffix

    return TimeFeature(
        band=band,
        rule_fired=rule_fired,
        score=_band_to_score(band),
        unique_days_count=k_days,
        span_days=span_days,
        has_empty_days=has_empty,
        events_per_day=events_per_day_map,
        max_events_in_any_day=max_events,
        total_span_hours=total_span_h,
        max_inter_cluster_gap_h=max_inter_gap_h,
        max_intra_cluster_span_h=max_intra_span_h,
        has_overnight_chain=has_overnight,
        has_dawn_photos=has_dawn,
        near_eps_boundary_count=total_near_count,
        fallback_count=fallback_count,
        fallback_ratio=fallback_ratio,
        confidence=confidence,
        shape=shape,
    )
