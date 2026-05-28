"""L2 1.0 emotional score (v1.3 §3.2.6 抄本, 保留 neutral bug).

⚠ ADR-0018 拍板保留 v1.3 原貌:
   5 张 emotional_tone="neutral" 字面一致 → score=0.8 → strong
   命中真值表 emotional 强叠加可能出"平淡日常"强相册.
   L2 2.0 (ADR-0015) 用 EM.0 preempt 修了这个 bug, 此处不修.

参考: docs/24_feature_assembler_plan_ab.md §2.6
"""
from __future__ import annotations

from src.contracts import L1Output


def compute_emotional_score_legacy(photos: list[L1Output]) -> tuple[float, dict]:
    """v1.3 §3.2.6: 字面匹配, 完全一致 0.8 / ≤2 种 0.4 / 否则 0.0.

    ⚠ 保留 neutral bug (ADR-0018 拍板, 真实展示 v1.3 缺陷).
    """
    # emotional_tone 在 L1Output 直接挂载 (不是 semantic_facts 子)
    tones = [
        p.emotional_tone for p in photos
        if getattr(p, "emotional_tone", None)
    ]
    if not tones:
        return 0.0, {"unique_tones": [], "reason": "missing_emotional_tone"}

    unique_tones = set(tones)

    if len(unique_tones) == 1:
        score = 0.8     # ⚠ neutral bug: 5 张 neutral 也 0.8 strong
    elif len(unique_tones) <= 2:
        score = 0.4
    else:
        score = 0.0

    return score, {
        "unique_tones": list(unique_tones),
        "tone_count": len(unique_tones),
        "neutral_bug_active": len(unique_tones) == 1 and "neutral" in unique_tones,
    }
