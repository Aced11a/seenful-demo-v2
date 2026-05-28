"""Feature Assembler · 把 7 维分数装到 FeaturePackage (ADR-0018 双版本).

参考:
  docs/01_architecture.md §2
  docs/24_feature_assembler_plan_ab.md (ADR-0018)
  ADR-0010 (location) / ADR-0011 (time) / ADR-0012 (event)
  ADR-0013 (theme) / ADR-0014 (anchor) / ADR-0015 (emotional)

分发:
  · plan="L2_2.0" (默认): ADR-0010~0015 升级版, 各维度直出 band
  · plan="L2_1.0": v1.3 §3.2 抄本, score-based (compute_bands fallback 走 legacy_thresholds)
"""
from __future__ import annotations

from src.contracts import FeaturePackage, L1Output
from src.policy.config_loader import load_config

from .anchor import build_anchor_feature
from .emotional import build_emotional_feature
from .event import build_event_feature
from .location import build_location_feature
from .people import compute_people_score
from .theme import build_theme_feature
from .time import build_time_feature


def assemble_features(
    photos: list[L1Output],
    plan: str | None = None,
) -> FeaturePackage:
    """7 维计算 + 上下文标志 (ADR-0018 双版本).

    plan 优先级:
      1. 函数参数 (测试/显式调用)
      2. 环境变量 SEENFUL_FEATURE_ASSEMBLER_PLAN (demo CLI --plan flag)
      3. config/feature_assembler.yaml::plan (默认配置)
    """
    if plan is None:
        import os
        plan = os.environ.get("SEENFUL_FEATURE_ASSEMBLER_PLAN")
    if plan is None:
        cfg = load_config("feature_assembler.yaml")
        plan = cfg["feature_assembler"]["plan"]

    if plan == "L2_1.0":
        return _assemble_plan_b(photos)
    return _assemble_plan_a(photos)


def _assemble_plan_a(photos: list[L1Output]) -> FeaturePackage:
    """L2 2.0 (默认): ADR-0010~0015 升级版, 各维度直出 band."""
    location_feature = build_location_feature(photos)
    time_feature = build_time_feature(photos)
    event_feature = build_event_feature(photos)
    theme_feature = build_theme_feature(photos)
    anchor_feature = build_anchor_feature(photos)
    emotional_feature = build_emotional_feature(photos)
    people_score = compute_people_score(photos)

    is_hfp = any(p.is_high_frequency_place for p in photos)
    time_is_fallback = time_feature.fallback_ratio == 1.0

    return FeaturePackage(
        plan="L2_2.0",
        location_score=location_feature.score,
        time_score=time_feature.score,
        theme_score=theme_feature.score,
        event_score=event_feature.score,
        people_score=people_score,
        anchor_score=anchor_feature.score,
        emotional_score=emotional_feature.score,
        is_high_frequency_place=is_hfp,
        time_is_fallback=time_is_fallback,
        photo_count=len(photos),
        location=location_feature,
        time=time_feature,
        event=event_feature,
        theme=theme_feature,
        anchor=anchor_feature,
        emotional=emotional_feature,
    )


def _assemble_plan_b(photos: list[L1Output]) -> FeaturePackage:
    """L2 1.0 (副): v1.3 §3.2 score-based 抄本.

    7 维各自算 score, FeaturePackage 子 Feature 字段全 None,
    compute_bands 自动 fallback 走 legacy_thresholds (ADR-0018).
    """
    from .plan_b import (
        compute_anchor_score_legacy,
        compute_emotional_score_legacy,
        compute_event_score_legacy,
        compute_location_score_legacy,
        compute_theme_score_legacy,
        compute_time_score_legacy,
    )

    location_score, _ = compute_location_score_legacy(photos)
    time_score, _ = compute_time_score_legacy(photos)
    theme_score, _ = compute_theme_score_legacy(photos)
    event_score, _ = compute_event_score_legacy(photos)
    anchor_score, _ = compute_anchor_score_legacy(photos)
    emotional_score, _ = compute_emotional_score_legacy(photos)

    # People 跨版本共享 (v0.1 简化版本身就是 v1.3 §3.2.7 实现)
    people_score = compute_people_score(photos)

    is_hfp = any(p.is_high_frequency_place for p in photos)

    # time_is_fallback: 检查所有 photo 的 captured_at_source
    time_is_fallback = all(
        getattr(p, "captured_at_source", "exif_time") == "upload_time_fallback"
        for p in photos
    )

    return FeaturePackage(
        plan="L2_1.0",
        location_score=location_score,
        time_score=time_score,
        theme_score=theme_score,
        event_score=event_score,
        people_score=people_score,
        anchor_score=anchor_score,
        emotional_score=emotional_score,
        is_high_frequency_place=is_hfp,
        time_is_fallback=time_is_fallback,
        photo_count=len(photos),
        # 子 Feature 字段全 None, compute_bands 自动走 score → legacy_thresholds
        location=None,
        time=None,
        event=None,
        theme=None,
        anchor=None,
        emotional=None,
    )
