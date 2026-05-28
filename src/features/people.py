"""people_score 计算 (主载体, P0 上限 0.65).

参考: docs/07_dimension_thresholds.md §people_score
"""
from __future__ import annotations

from src.contracts import L1Output
from src.policy.config_loader import load_config


def compute_people_score(photos: list[L1Output]) -> float:
    if len(photos) < 2:
        return 0.0

    presences = [p.semantic_facts.people_presence for p in photos]
    face_counts = [p.semantic_facts.face_count for p in photos]

    if all(pr == "none" for pr in presences):
        return 0.0

    valid_presences = [pr for pr in presences if pr != "unknown"]
    if not valid_presences or len(set(valid_presences)) != 1:
        # 有人但 presence 不一致
        return 0.3

    cap = float(load_config("dimension_thresholds.yaml")["people_score_cap_p0"])

    # presence 一致 (非 unknown 非 none)
    if valid_presences[0] == "none":
        return 0.0

    if face_counts and max(face_counts) - min(face_counts) <= 1:
        return min(0.65, cap)
    return 0.45
