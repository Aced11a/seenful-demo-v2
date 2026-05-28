"""L2 1.0 anchor score (v1.3 §3.2.4 抄本).

参考: docs/24_feature_assembler_plan_ab.md §2.5
"""
from __future__ import annotations

from src.contracts import L1Output


def _jaccard(sets: list[set]) -> float:
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0
    intersection = set.intersection(*sets)
    union = set.union(*sets)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def compute_anchor_score_legacy(photos: list[L1Output]) -> tuple[float, dict]:
    """v1.3 §3.2.4: max(meaning_anchors Jaccard, object_anchors Jaccard).

    返回 (score, diagnostic_dict).
    """
    meaning_sets = []
    object_sets = []
    for p in photos:
        # meaning_anchors 在 L1Output 直接挂载 (不是 semantic_facts 子)
        if getattr(p, "meaning_anchors", None):
            meaning_sets.append(set(p.meaning_anchors))
        # object_anchors 在 semantic_facts 子对象
        if p.semantic_facts and getattr(p.semantic_facts, "object_anchors", None):
            object_sets.append(set(p.semantic_facts.object_anchors))

    meaning_overlap = _jaccard(meaning_sets)
    object_overlap = _jaccard(object_sets)

    score = max(meaning_overlap, object_overlap)

    return score, {
        "meaning_anchor_overlap": meaning_overlap,
        "object_anchor_overlap": object_overlap,
    }
