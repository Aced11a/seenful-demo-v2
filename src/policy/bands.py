"""维度分档 + 高频地点降一档.

参考:
  docs/07_dimension_thresholds.md
  docs/06_hard_rules.md HR-BANDS-01
"""
from __future__ import annotations

from typing import cast

from src.contracts import Bands, FeaturePackage
from src.contracts.features import BandLevel

from .config_loader import load_config

LEVELS: list[BandLevel] = ["strong", "medium", "weak", "none"]


def _classify(score: float, dim_cfg: dict) -> BandLevel:
    """按阈值表把 score 归档."""
    if score >= dim_cfg["strong"]:
        return "strong"
    if score >= dim_cfg["medium"]:
        return "medium"
    if score >= dim_cfg["weak"]:
        return "weak"
    return "none"


def _downgrade_one(level: BandLevel) -> BandLevel:
    idx = LEVELS.index(level)
    if idx + 1 >= len(LEVELS):
        return "none"
    return LEVELS[idx + 1]


def compute_bands(features: FeaturePackage) -> Bands:
    """把 FeaturePackage 转换为 Bands.

    plan=L2_2.0 (默认): location/time/event/theme/anchor/emotional 6 维直读对应
      Feature.band (ADR-0010~0015). 仅 people 走 score → 阈值.
    plan=L2_1.0 (ADR-0018): 子 Feature 字段全 None → 全 7 维走 score → 阈值,
      阈值表读 feature_assembler.yaml::legacy_thresholds (v1.3 §5.3.5).
    """
    # ADR-0018: 按 plan 选阈值源
    if features.plan == "L2_1.0":
        fa_cfg = load_config("feature_assembler.yaml")
        db = fa_cfg["feature_assembler"]["legacy_thresholds"]
        cfg = {"dimension_bands": db, "high_frequency_place_downgrade": True}
    else:
        cfg = load_config("dimension_thresholds.yaml")
        db = cfg["dimension_bands"]

    # location 走 ADR-0010 直出 band
    if features.location is not None:
        location = features.location.band
    else:
        location = _classify(features.location_score, db["location"])
        if features.is_high_frequency_place and cfg.get("high_frequency_place_downgrade", True):
            location = _downgrade_one(location)

    # time 走 ADR-0011 直出 band
    if features.time is not None:
        time_band = features.time.band
    else:
        time_band = _classify(features.time_score, db["time"])

    # event 走 ADR-0012 直出 band
    if features.event is not None:
        event_band = features.event.band
    else:
        event_band = _classify(features.event_score, db["event"])

    # theme 走 ADR-0013 直出 band
    if features.theme is not None:
        theme_band = features.theme.band
    else:
        theme_band = _classify(features.theme_score, db["theme"])

    # anchor 走 ADR-0014 直出 band
    if features.anchor is not None:
        anchor_band = features.anchor.band
    else:
        anchor_band = _classify(features.anchor_score, db["anchor"])

    # emotional 走 ADR-0015 直出 band
    if features.emotional is not None:
        emotional_band = features.emotional.band
    else:
        emotional_band = _classify(features.emotional_score, db["emotional"])

    return Bands(
        location=location,
        time=time_band,
        theme=theme_band,
        event=event_band,
        people=_classify(features.people_score, db["people"]),
        anchor=anchor_band,
        emotional=emotional_band,
    )
