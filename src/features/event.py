"""路径 B Event 维度 (ADR-0012): event primary_share + activity 二次门槛.

参考:
  docs/18_path_b_event.md (完整算法规范)
  decisions/0012-path-b-event-aggregation.md
  config/path_b_event.yaml

输出: EventFeature (含 band 终值 + 完整诊断字段)

⚠ A3 真值表让 event=强单独成集, 因此 strong 门槛必须严:
   E.1 唯一通道 = event_primary_share=1.0 AND activity_primary_share≥2/3
   见 Path_B_Event_Aggregation_Spec.md v0.2 §1.5.

⚠ 复用 ADR-0009 `aggregate_event(photos)` 算 distribution.
   path A 用同函数做匹配, path B 用同函数做内聚度判定.
"""
from __future__ import annotations

from collections import Counter

from src.contracts import BandLevel, EventFeature, EventShape, L1Output
from src.mini_album.event_aggregation import aggregate_event
from src.policy.config_loader import load_config


# ─── 派生 score (展示用, 真值表不读) ─────────────────────────


def _band_to_score(band: BandLevel) -> float:
    """band 终值 → 展示 score (与 ADR-0010 / ADR-0011 一致)."""
    return {"strong": 0.9, "medium": 0.7, "weak": 0.4, "none": 0.1}[band]


# ─── activity 分布计算 ───────────────────────────────────────


def _compute_activity_distribution(photos: list[L1Output]) -> tuple[str | None, int, float]:
    """计算 activity 多数派 (排除 unknown).

    返回 (activity_primary, activity_primary_count, activity_primary_share).
    activity_primary_share 基于 N (总数), 跟 event_primary_share 同分母.
    """
    n = len(photos)
    if n == 0:
        return None, 0, 0.0

    valid_activities = [
        p.semantic_facts.activity
        for p in photos
        if p.semantic_facts.activity != "unknown"
    ]
    if not valid_activities:
        return None, 0, 0.0

    counter: Counter[str] = Counter(valid_activities)
    activity_primary, activity_primary_count = counter.most_common(1)[0]
    activity_primary_share = activity_primary_count / n
    return activity_primary, activity_primary_count, activity_primary_share


# ─── 8 行 grid 判定 (E.1~E.8) ────────────────────────────────


def _step_grid(
    event_share: float,
    activity_share: float,
    n_valid: int,
    n: int,
    cfg: dict,
) -> tuple[BandLevel, EventShape, str, bool, bool]:
    """E.1~E.8 grid 判定.

    返回 (band, shape, rule_fired, used_activity_gate, used_activity_fallback).
    """
    bt = cfg["band_thresholds"]
    strong_share = float(bt["strong_share"])
    medium_dominant = float(bt["medium_dominant_share"])
    medium_mixed = float(bt["medium_mixed_share"])
    weak_scattered = float(bt["weak_scattered_share"])

    gate_min = float(cfg["activity_gate"]["min_consensus_ratio"])
    fb_cfg = cfg["activity_fallback"]
    fb_min = float(fb_cfg["min_consensus_ratio"])
    fb_max_valid = int(fb_cfg["max_valid_event_for_fallback"])
    fb_band: BandLevel = fb_cfg["fallback_band"]  # type: ignore[assignment]

    # E.1 / E.2: event 100% 一致 → 看 activity 二次门槛
    if event_share >= strong_share:  # event = 1.0
        if activity_share >= gate_min:
            return "strong", EventShape.UNANIMOUS_EVENT_ACTIVITY, "E.1", True, False
        return "medium", EventShape.UNANIMOUS_EVENT_MIXED_ACTIVITY, "E.2", True, False

    # E.3: 0.8 ≤ < 1.0 → medium dominant
    if event_share >= medium_dominant:
        return "medium", EventShape.DOMINANT_EVENT, "E.3", False, False

    # E.4: 0.6 ≤ < 0.8 → medium mixed
    if event_share >= medium_mixed:
        return "medium", EventShape.MIXED_EVENT, "E.4", False, False

    # E.5: 0.4 ≤ < 0.6 → weak scattered
    if event_share >= weak_scattered:
        return "weak", EventShape.SCATTERED_EVENT, "E.5", False, False

    # event_share < 0.4 时, 判 event 缺位还是事件散乱
    if n_valid <= fb_max_valid:
        # E.7 / E.8: event 缺位, 走 activity 兜底
        if activity_share >= fb_min:
            return fb_band, EventShape.ACTIVITY_FALLBACK, "E.7", False, True
        return "none", EventShape.NO_EVENT_SIGNAL, "E.8", False, True

    # E.6: event 散 + N_valid ≥ 2 → weak fragmented
    return "weak", EventShape.FRAGMENTED_EVENT, "E.6", False, False


# ─── 高层入口 ────────────────────────────────────────────────


def build_event_feature(photos: list[L1Output]) -> EventFeature:
    """从 photos 构造 EventFeature (ADR-0012 直出 band).

    流水线 (docs/18 §2.1):
      Phase 1: ADR-0009 aggregate_event(photos) 算 distribution
      Phase 2: event_primary_share = primary_count / N
      Phase 3: activity_primary_share = activity_counter / N (排除 unknown)
      Phase 4: 8 行 grid 判定 → band + shape + rule_fired

    边界:
      N < 2 → band="none" (path B 红线 §3 最低 ≥ 2 张)
    """
    cfg = load_config("path_b_event.yaml")["path_b_event"]
    n = len(photos)

    # 边界: N < 2 → none (红线 "2 张永远不成集")
    if n < 2:
        return EventFeature(
            band="none",
            rule_fired="E.8",
            score=_band_to_score("none"),
            total_photos=n,
            valid_event_count=0,
            unknown_share=0.0,
            primary_event=None,
            primary_count=0,
            event_primary_share=0.0,
            secondary_events=[],
            tertiary_events=[],
            distinct_events=0,
            activity_primary=None,
            activity_primary_count=0,
            activity_primary_share=0.0,
            used_activity_gate=False,
            used_activity_fallback=False,
            shape=EventShape.NO_EVENT_SIGNAL,
        )

    # Phase 1: 复用 ADR-0009 aggregate_event
    agg_cfg = load_config("event_aggregation.yaml")["event_aggregation"]
    agg = aggregate_event(photos, agg_cfg)

    n_valid = agg.total_events
    unknown_share = (n - n_valid) / n
    primary_count = agg.distribution.get(agg.primary, 0) if agg.primary else 0
    event_primary_share = primary_count / n

    # Phase 3: activity 分布
    activity_primary, activity_primary_count, activity_primary_share = (
        _compute_activity_distribution(photos)
    )

    # Phase 4: grid 判定
    band, shape, rule_fired, used_gate, used_fallback = _step_grid(
        event_share=event_primary_share,
        activity_share=activity_primary_share,
        n_valid=n_valid,
        n=n,
        cfg=cfg,
    )

    return EventFeature(
        band=band,
        rule_fired=rule_fired,
        score=_band_to_score(band),
        total_photos=n,
        valid_event_count=n_valid,
        unknown_share=unknown_share,
        primary_event=agg.primary,
        primary_count=primary_count,
        event_primary_share=event_primary_share,
        secondary_events=list(agg.secondary),
        tertiary_events=list(agg.tertiary),
        distinct_events=len(agg.distribution),
        activity_primary=activity_primary,
        activity_primary_count=activity_primary_count,
        activity_primary_share=activity_primary_share,
        used_activity_gate=used_gate,
        used_activity_fallback=used_fallback,
        shape=shape,
    )
