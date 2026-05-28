"""L2 1.0 theme score (v1.3 §3.2.3 抄本 + schema 适配 scene_type=0).

参考: docs/24_feature_assembler_plan_ab.md §2.3
"""
from __future__ import annotations

from src.contracts import L1Output


def _jaccard(sets: list[set]) -> float:
    """多集合 Jaccard = |交集| / |并集|."""
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0
    intersection = set.intersection(*sets)
    union = set.union(*sets)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def compute_theme_score_legacy(photos: list[L1Output]) -> tuple[float, dict]:
    """v1.3 §3.2.3: 0.5 × theme_tags_jaccard + 0.4 × main_subjects_jaccard + 0.1 × scene_consistent.

    ⚠ ADR-0018 schema 适配: scene_type 字段已从 SemanticFacts 删除 (ADR-0013),
    scene_consistent 子信号设 0, score ∈ [0, 0.9]. 不重新归一化权重.

    返回 (score, diagnostic_dict).
    """
    # theme_tags Jaccard
    tag_sets = [set(p.theme_tags) for p in photos if p.theme_tags]
    tag_jaccard = _jaccard(tag_sets)

    # main_subjects Jaccard (来自 semantic_facts)
    subject_sets = []
    for p in photos:
        if p.semantic_facts and p.semantic_facts.main_subjects:
            subject_sets.append(set(p.semantic_facts.main_subjects))
    subject_jaccard = _jaccard(subject_sets) if subject_sets else 0.0

    # scene_type 已删, 子信号设 0 (ADR-0018 schema 适配)
    scene_consistent = 0.0

    score = (
        0.5 * tag_jaccard
        + 0.4 * subject_jaccard
        + 0.1 * scene_consistent
    )

    return score, {
        "tag_jaccard": tag_jaccard,
        "subject_jaccard": subject_jaccard,
        "scene_consistent": False,
        "scene_type_adapter": "v1.3 scene_type 字段已删, 子信号设 0",
    }
