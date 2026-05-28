"""Event 三级分层聚合 + 匹配 (路径 A event 维度) · 纯 Python 实现.

参考:
  docs/15_event_aggregation.md
  decisions/0009-event-aggregation.md
  archive/specs/Event_Field_And_Aggregation_Spec.md (原始 spec, 已归档)

提供:
  · aggregate_event           — 三级分层聚合 (spec §五 5.2)
  · match_event               — 1 张新照片 vs 老相册四档匹配 (spec §五 5.3)
  · build_event_aggregation   — 高层入口, 从 L1 photos 构造

依赖: 仅 stdlib (collections, datetime). 零外部依赖.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from src.contracts import (
    EventAggregation,
    EventMatchResult,
    L1Output,
)
from src.policy.config_loader import load_config


# ═════════════════════════════════════════════════════════════════
# 聚合 (spec §五 5.2)
# ═════════════════════════════════════════════════════════════════

def aggregate_event(
    members: list[L1Output],
    cfg: dict,
) -> EventAggregation:
    """对成员照片的 event_hint 做三级分层聚合.

    流程 (docs/15 §三 3.1):
      Step 1: 过滤 unknown → hints
      Step 2: Counter(hints) → distribution
      Step 3: 三级分层
        · primary = sorted_events[0] 占比 ≥ primary_threshold 吗? 该 event : None
        · 剩余 event 按占比/count 分配:
            - 占比 ≥ secondary_threshold → secondary
            - count ≥ tertiary_min_count → tertiary

    cfg 是 event_aggregation 段 dict (已下钻一层).
    """
    primary_threshold = float(cfg["primary_threshold"])
    secondary_threshold = float(cfg["secondary_threshold"])
    tertiary_min_count = int(cfg["tertiary_min_count"])

    # Step 1: 过滤 unknown
    hints = [
        p.semantic_facts.event_hint
        for p in members
        if p.semantic_facts.event_hint != "unknown"
    ]

    if not hints:
        return EventAggregation(
            primary=None,
            secondary=[],
            tertiary=[],
            distribution={},
            total_events=0,
        )

    # Step 2: Counter
    counter: Counter[str] = Counter(hints)
    total = len(hints)
    sorted_events = counter.most_common()

    # Step 3: 三级分层
    primary: str | None = None
    secondary: list[str] = []
    tertiary: list[str] = []

    # primary: 占比 ≥ 阈值的最高频
    top_event, top_count = sorted_events[0]
    if top_count / total >= primary_threshold:
        primary = top_event

    # secondary / tertiary: 剩余 event
    for event, count in sorted_events:
        if event == primary:
            continue
        ratio = count / total
        if ratio >= secondary_threshold:
            secondary.append(event)
        elif count >= tertiary_min_count:
            tertiary.append(event)

    return EventAggregation(
        primary=primary,
        secondary=secondary,
        tertiary=tertiary,
        distribution=dict(counter),
        total_events=total,
    )


# ═════════════════════════════════════════════════════════════════
# 匹配 (spec §五 5.3)
# ═════════════════════════════════════════════════════════════════

def match_event(
    new_event: str,
    event_agg: EventAggregation,
) -> EventMatchResult:
    """1 张新照片 event vs 老相册 event_agg 四档匹配.

    规则 (docs/15 §四):
      · unknown          → band="none" (reason="unknown_event")
      · == primary       → band="strong", matched_tier="primary"
      · in secondary     → band="medium", matched_tier="secondary"
      · in tertiary      → band="weak",   matched_tier="tertiary"
      · 其他             → band="none",   matched_tier="none"
      · 空 aggregation   → band="none" (reason="empty_aggregation")
    """
    # 空 aggregation 边界
    if event_agg.total_events == 0:
        return EventMatchResult(
            band="none",
            matched_tier="none",
            diagnostics={
                "new_event": new_event,
                "primary": None,
                "secondary": [],
                "tertiary": [],
            },
            reason="empty_aggregation",
        )

    # unknown 不参与匹配
    if new_event == "unknown":
        return EventMatchResult(
            band="none",
            matched_tier="none",
            diagnostics={
                "new_event": new_event,
                "primary": event_agg.primary,
                "secondary": event_agg.secondary,
                "tertiary": event_agg.tertiary,
            },
            reason="unknown_event",
        )

    diagnostics: dict = {
        "new_event": new_event,
        "primary": event_agg.primary,
        "secondary": list(event_agg.secondary),
        "tertiary": list(event_agg.tertiary),
    }

    if event_agg.primary is not None and new_event == event_agg.primary:
        return EventMatchResult(
            band="strong",
            matched_tier="primary",
            diagnostics=diagnostics,
        )
    if new_event in event_agg.secondary:
        return EventMatchResult(
            band="medium",
            matched_tier="secondary",
            diagnostics=diagnostics,
        )
    if new_event in event_agg.tertiary:
        return EventMatchResult(
            band="weak",
            matched_tier="tertiary",
            diagnostics=diagnostics,
        )
    return EventMatchResult(
        band="none",
        matched_tier="none",
        diagnostics=diagnostics,
    )


# ═════════════════════════════════════════════════════════════════
# 高层入口: 从 L1 photos 构造 event_agg
# ═════════════════════════════════════════════════════════════════

def build_event_aggregation(
    photos: list[L1Output],
    cfg: dict | None = None,
) -> tuple[EventAggregation, datetime]:
    """从相册照片列表生成 (event_agg, aggregated_at).

    流程: 直接调 aggregate_event.
    参考: docs/15 §六 (增量更新策略 = 全量重算).
    """
    cfg = cfg or load_config("event_aggregation.yaml")["event_aggregation"]
    event_agg = aggregate_event(photos, cfg)
    return event_agg, datetime.now()
