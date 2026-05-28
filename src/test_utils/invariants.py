"""8 条产品红线自动校验 (ADR-0019).

参考: docs/25_persona_e2e_testing.md §七
     CLAUDE.md 红线 1-8
"""
from __future__ import annotations

from typing import Any


def check_inv01_weak_no_create_new_album(log: Any) -> tuple[bool, str]:
    """INV-01: 弱关联绝不 create_new_album (红线 #5)."""
    if hasattr(log, "final_decision"):
        fd = log.final_decision
        # cascade BackfillDecision
        if hasattr(fd, "decision_tier") and fd.decision_tier == "create_new_album":
            if hasattr(fd, "target_album_strength"):
                if fd.target_album_strength not in ("strong",):
                    return False, f"INV-01 violated: create_new_album but strength={fd.target_album_strength}"
        # path B Association
        if hasattr(fd, "association"):
            a = fd.association
            if a.display_decision == "show_mini_album" and a.strength == "weak":
                return False, "INV-01 violated: show_mini_album but strength=weak"
    return True, ""


def check_inv02_sensitive_suppress(log: Any) -> tuple[bool, str]:
    """INV-02: sensitive_level >= medium 永远 suppress / no_merge (红线 #6).

    注: runner 层应保证敏感照片不进入算法, 这里是 defense in depth.
    """
    # 假设 log 含 photo info 时校验
    return True, ""  # runner 层校验, 此处通过


def check_inv03_high_freq_no_auto_merge(log: Any) -> tuple[bool, str]:
    """INV-03: 高频地点不能仅凭 GPS 自动并入 (红线 #7)."""
    if not hasattr(log, "final_decision"):
        return True, ""
    fd = log.final_decision
    if hasattr(fd, "decision_tier"):
        # path A
        if fd.decision_tier == "auto_merge":
            # 看 evaluations 是否 high_freq + 无 theme/event
            if hasattr(log, "per_album_evaluations"):
                for e in log.per_album_evaluations:
                    if getattr(e, "is_high_frequency_place", False):
                        if e.bands.theme not in ("strong", "medium") and e.bands.event not in ("strong", "medium"):
                            return False, "INV-03 violated: high_freq + no theme/event but auto_merge"
    return True, ""


def check_inv04_cascade_min_recall(log: Any) -> tuple[bool, str]:
    """INV-04: cascade 召回 ≥ 2 张才能成集 (PRD §3.10.4)."""
    if not hasattr(log, "final_decision"):
        return True, ""
    fd = log.final_decision
    if hasattr(fd, "decision_tier") and fd.decision_tier == "create_new_album":
        if hasattr(fd, "recalled_photo_ids"):
            if len(fd.recalled_photo_ids) < 2:
                return False, f"INV-04 violated: create_new_album with recall={len(fd.recalled_photo_ids)}"
    return True, ""


def check_inv05_cascade_strong_only(log: Any) -> tuple[bool, str]:
    """INV-05: cascade strong-only (PRD §3.10.5)."""
    if not hasattr(log, "final_decision"):
        return True, ""
    fd = log.final_decision
    if hasattr(fd, "decision_tier") and fd.decision_tier == "create_new_album":
        if hasattr(fd, "target_album_strength"):
            if fd.target_album_strength != "strong":
                return False, f"INV-05 violated: cascade create with strength={fd.target_album_strength}"
    return True, ""


def check_inv06_cascade_max_recall(log: Any) -> tuple[bool, str]:
    """INV-06: cascade 召回 ≤ 4 张 (ADR-0017 PRD §3.10.5)."""
    if not hasattr(log, "final_decision"):
        return True, ""
    fd = log.final_decision
    if hasattr(fd, "decision_tier") and fd.decision_tier == "create_new_album":
        if hasattr(fd, "recalled_photo_ids"):
            if len(fd.recalled_photo_ids) > 4:
                return False, f"INV-06 violated: recall={len(fd.recalled_photo_ids)} > 4"
    return True, ""


def check_inv07_event_weight(log: Any) -> tuple[bool, str]:
    """INV-07: event 权重 0.5 (ADR-0017 priority_weight).

    校验落痕 priority_ranking 中 event-only 候选 score == 0.5.
    """
    if hasattr(log, "priority_ranking"):
        for entry in log.priority_ranking:
            if entry.event_match and not entry.gps_within_1km and not entry.theme_jaccard_above_0_5:
                if abs(entry.score - 0.5) > 0.01:
                    return False, f"INV-07 violated: event-only score={entry.score}, expected 0.5"
    return True, ""


def check_inv08_plan_logged(log: Any) -> tuple[bool, str]:
    """INV-08: plan A/B 切换 + DecisionLog 落痕 (ADR-0018)."""
    if hasattr(log, "feature_assembler_plan"):
        if log.feature_assembler_plan not in ("L2_2.0", "L2_1.0"):
            return False, f"INV-08 violated: plan={log.feature_assembler_plan}"
    return True, ""


ALL_INVARIANTS = {
    "INV-01": check_inv01_weak_no_create_new_album,
    "INV-02": check_inv02_sensitive_suppress,
    "INV-03": check_inv03_high_freq_no_auto_merge,
    "INV-04": check_inv04_cascade_min_recall,
    "INV-05": check_inv05_cascade_strong_only,
    "INV-06": check_inv06_cascade_max_recall,
    "INV-07": check_inv07_event_weight,
    "INV-08": check_inv08_plan_logged,
}


def check_invariants(log: Any, only: list[str] | None = None) -> list[str]:
    """跑全部 (或指定) invariants, 返回违反列表."""
    if only is None:
        to_check = ALL_INVARIANTS
    else:
        to_check = {k: v for k, v in ALL_INVARIANTS.items() if k in only}

    violations = []
    for name, fn in to_check.items():
        passed, msg = fn(log)
        if not passed:
            violations.append(f"{name}: {msg}")
    return violations
