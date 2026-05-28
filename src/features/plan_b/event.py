"""L2 1.0 event score (v1.3 §3.2.5 抄本).

参考: docs/24_feature_assembler_plan_ab.md §2.4
"""
from __future__ import annotations

from src.contracts import L1Output


def compute_event_score_legacy(photos: list[L1Output]) -> tuple[float, dict]:
    """v1.3 §3.2.5: event_hint 一致 0.9 / activity 一致 0.6 / 否则 0.0.

    返回 (score, diagnostic_dict).
    """
    event_hints = [
        p.semantic_facts.event_hint
        for p in photos
        if p.semantic_facts and p.semantic_facts.event_hint
    ]
    activities = [
        p.semantic_facts.activity
        for p in photos
        if p.semantic_facts and getattr(p.semantic_facts, "activity", None)
    ]

    event_consistent = (
        len(event_hints) == len(photos)
        and len(set(event_hints)) == 1
        and event_hints[0] not in ("unknown", None)
    )
    activity_consistent = (
        len(activities) == len(photos)
        and len(set(activities)) == 1
        and activities[0] not in ("unknown", None)
    )

    if event_consistent:
        score = 0.9
    elif activity_consistent:
        score = 0.6
    else:
        score = 0.0

    return score, {
        "event_consistent": event_consistent,
        "activity_consistent": activity_consistent,
        "event_hints_unique": list(set(event_hints)),
    }
