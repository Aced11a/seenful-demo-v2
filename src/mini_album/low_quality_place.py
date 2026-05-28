"""高频低质量地点判定 (ADR-0006) · 纯 Python 实现.

参考:
  docs/13_low_quality_place_detection.md
  decisions/0006-high-freq-low-quality-place.md
  archive/specs/high_frequency_Place_Detection_Spec.md (已归档原始 spec)

提供:
  · pass_frequency_check          — 频率门槛 (硬约束)
  · compute_user_density_baseline — 用户个人 25 分位
  · signal_l1_density             — Plan A 双低占比
  · is_low_quality_plan_a         — Plan A 主入口
  · is_low_quality_plan_b         — Plan B stub (NotImplementedError)
  · is_low_quality_place          — 主分发 (按 config 选 Plan A/B)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from src.contracts import (
    Cluster,
    L1Output,
    LowQualityResult,
    UserContext,
    UserDensityBaseline,
)
from src.policy.config_loader import load_config


# ═════════════════════════════════════════════════════════════════
# 频率门槛 (Plan A/B 共用硬约束)
# ═════════════════════════════════════════════════════════════════

def pass_frequency_check(
    cluster: Cluster,
    user_ctx: UserContext,
    cfg: dict,
    now: datetime | None = None,
) -> tuple[bool, dict]:
    """spec §三 + docs/13 §三

    返回 (passed, diagnostics).
    任一不过 → False.
    """
    freq_cfg = cfg["frequency"]

    if user_ctx.account_age_days < freq_cfg["new_user_min_age_days"]:
        return False, {
            "reason": "new_user_protection",
            "account_age_days": user_ctx.account_age_days,
            "threshold": freq_cfg["new_user_min_age_days"],
        }

    if len(user_ctx.user_history) < freq_cfg["new_user_min_photos"]:
        return False, {
            "reason": "user_history_too_small",
            "user_history_size": len(user_ctx.user_history),
            "threshold": freq_cfg["new_user_min_photos"],
        }

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(freq_cfg["lookback_days"]))

    cluster_photo_ids = set(cluster.member_photo_ids)
    recent_in_cluster = [
        p for p in user_ctx.user_history
        if (
            getattr(p, "photo_id", None) in cluster_photo_ids
            and getattr(p, "captured_at", None) is not None
            and p.captured_at >= cutoff
        )
    ]

    distinct_days = len({p.captured_at.date() for p in recent_in_cluster})
    passed = distinct_days >= int(freq_cfg["min_distinct_days"])

    return passed, {
        "reason": "frequency_passed" if passed else "frequency_failed",
        "distinct_days": distinct_days,
        "threshold": freq_cfg["min_distinct_days"],
        "lookback_days": freq_cfg["lookback_days"],
        "recent_count": len(recent_in_cluster),
    }


# ═════════════════════════════════════════════════════════════════
# Plan A · 用户 baseline
# ═════════════════════════════════════════════════════════════════

def _percentile(values: list[float], p: float) -> float:
    """简易 percentile (linear), 不引 numpy. p 取 [0, 100]."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_v) - 1)
    if f == c:
        return sorted_v[f]
    return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])


def compute_user_density_baseline(
    user_id: str,
    user_history: list[L1Output],
    cfg: dict,
    now: datetime | None = None,
) -> UserDensityBaseline | None:
    """spec §四.1

    用户照片不足 min_samples_for_baseline 时返回 None
    → baseline 不可用 → is_low_quality_plan_a 保守 return False.
    """
    plan_a = cfg["plan_a"]
    min_samples = int(plan_a["min_samples_for_baseline"])
    percentile = float(plan_a["baseline_percentile"])

    valid = [
        p for p in user_history
        if (
            getattr(p, "meaning_density", None) is not None
            and getattr(p, "aesthetic_density", None) is not None
        )
    ]
    if len(valid) < min_samples:
        return None

    meaning_vals = [p.meaning_density for p in valid]
    aesthetic_vals = [p.aesthetic_density for p in valid]

    return UserDensityBaseline(
        user_id=user_id,
        meaning_threshold=_percentile(meaning_vals, percentile),
        aesthetic_threshold=_percentile(aesthetic_vals, percentile),
        last_computed_at=now or datetime.now(timezone.utc),
        sample_size=len(valid),
    )


# ═════════════════════════════════════════════════════════════════
# Plan A · 双低占比判定
# ═════════════════════════════════════════════════════════════════

def signal_l1_density(
    cluster: Cluster,
    l1_data: dict[str, L1Output],
    baseline: UserDensityBaseline | None,
    cfg: dict,
) -> tuple[bool, dict]:
    """spec §四.2 — 簇内双低占比 ≥ double_low_ratio → 低质量"""
    if baseline is None:
        return False, {"reason": "baseline_missing"}

    plan_a = cfg["plan_a"]
    ratio_threshold = float(plan_a["double_low_ratio"])

    members: list[L1Output] = [
        l1_data[pid] for pid in cluster.member_photo_ids if pid in l1_data
    ]
    if not members:
        return False, {"reason": "no_l1_data_for_cluster"}

    double_low = sum(
        1 for p in members
        if (
            p.meaning_density < baseline.meaning_threshold
            and p.aesthetic_density < baseline.aesthetic_threshold
        )
    )
    ratio = double_low / len(members)
    passed = ratio >= ratio_threshold
    return passed, {
        "reason": "double_low_passed" if passed else "double_low_failed",
        "double_low_count": double_low,
        "total": len(members),
        "ratio": ratio,
        "threshold": ratio_threshold,
        "meaning_threshold": baseline.meaning_threshold,
        "aesthetic_threshold": baseline.aesthetic_threshold,
    }


# ═════════════════════════════════════════════════════════════════
# Plan A 主入口
# ═════════════════════════════════════════════════════════════════

def is_low_quality_plan_a(
    cluster: Cluster,
    user_ctx: UserContext,
    l1_data: dict[str, L1Output],
    cfg: dict,
    now: datetime | None = None,
) -> LowQualityResult:
    """spec §四.3

    Step 1 频率门槛 → False 即返
    Step 2 双 density 占比判定
    """
    diag: dict[str, Any] = {}

    # Step 1 频率门槛
    freq_passed, freq_diag = pass_frequency_check(cluster, user_ctx, cfg, now=now)
    diag["frequency"] = freq_diag
    if not freq_passed:
        return LowQualityResult(
            is_low_quality=False,
            signal_source="frequency_failed",
            diagnostics=diag,
        )

    # Step 2 双 density
    baseline = user_ctx.baseline
    if baseline is None:
        baseline = compute_user_density_baseline(
            user_ctx.user_id, user_ctx.user_history, cfg, now=now,
        )
    if baseline is None:
        diag["baseline"] = "missing"
        return LowQualityResult(
            is_low_quality=False,
            signal_source="baseline_missing",
            diagnostics=diag,
        )

    is_lq, density_diag = signal_l1_density(cluster, l1_data, baseline, cfg)
    diag["density"] = density_diag
    diag["baseline"] = {
        "meaning_threshold": baseline.meaning_threshold,
        "aesthetic_threshold": baseline.aesthetic_threshold,
        "sample_size": baseline.sample_size,
    }
    return LowQualityResult(
        is_low_quality=is_lq,
        signal_source="plan_a",
        diagnostics=diag,
    )


# ═════════════════════════════════════════════════════════════════
# Plan B (stub, 见 OQ-016)
# ═════════════════════════════════════════════════════════════════

def is_low_quality_plan_b(
    cluster: Cluster,
    user_ctx: UserContext,
    l1_data: dict[str, L1Output],
    cfg: dict,
    now: datetime | None = None,
) -> LowQualityResult:
    """Plan B 留 stub — 待 OQ-016 (L1 改输出 NIMA) 完成后实现."""
    raise NotImplementedError(
        "Plan B 尚未实现, 见 OQ-016. "
        "当前 config 应保持 plan_b.enabled=false, plan_a.enabled=true."
    )


# ═════════════════════════════════════════════════════════════════
# 主分发
# ═════════════════════════════════════════════════════════════════

def is_low_quality_place(
    cluster: Cluster,
    user_ctx: UserContext | None,
    l1_data: dict[str, L1Output] | None = None,
    cfg: dict | None = None,
    now: datetime | None = None,
) -> LowQualityResult:
    """spec §六 + docs/13 §六

    v0.1 简化:
      · user_ctx=None → 跳过判定 (signal_source=no_user_context, is_low_quality=False)
        当前 demo / 单测大多走这条
      · plan_a.enabled=true → is_low_quality_plan_a
      · plan_b.enabled=true → is_low_quality_plan_b (stub)
      · 都关 → signal_source=disabled
    """
    if user_ctx is None:
        return LowQualityResult(
            is_low_quality=False,
            signal_source="no_user_context",
            diagnostics={"note": "v0.1 demo 默认跳过, 不降档"},
        )

    cfg = cfg or load_config("low_quality_place.yaml")
    l1_data = l1_data or {}

    plan_a_enabled = bool(cfg["plan_a"]["enabled"])
    plan_b_enabled = bool(cfg.get("plan_b", {}).get("enabled", False))

    if plan_a_enabled:
        return is_low_quality_plan_a(cluster, user_ctx, l1_data, cfg, now=now)
    if plan_b_enabled:
        return is_low_quality_plan_b(cluster, user_ctx, l1_data, cfg, now=now)
    return LowQualityResult(
        is_low_quality=False,
        signal_source="disabled",
        diagnostics={"note": "plan_a / plan_b 都关闭"},
    )
