"""动态生长真值表 (路径 A · Step 3 / Step 4 等价).

参考: docs/04_truth_table_growth.md, config/truth_table_growth.yaml
DSL 与 main 同, 但分档对象只有 4 维 (location/theme/event/anchor).
"""
from __future__ import annotations

from typing import Any, cast

from src.contracts import GrowthBands, GrowthFeatures, GrowthTruthTableMatch
from src.contracts.features import BandLevel
from src.contracts.growth import DecisionTier, GrowthType

from .config_loader import load_config

LEVEL_ORDER: dict[BandLevel, int] = {"strong": 3, "medium": 2, "weak": 1, "none": 0}
GROWTH_MAIN = ("location", "theme", "event", "anchor")


def _level_ge(level: BandLevel, threshold: BandLevel) -> bool:
    return LEVEL_ORDER[level] >= LEVEL_ORDER[threshold]


def _get(bands: GrowthBands, name: str) -> BandLevel:
    return cast(BandLevel, getattr(bands, name))


def _compare(lhs: int, op: str, rhs: int) -> bool:
    return {
        ">=": lhs >= rhs, ">": lhs > rhs,
        "<=": lhs <= rhs, "<": lhs < rhs,
        "==": lhs == rhs,
    }[op]


def _eval(when: str, bands: GrowthBands) -> bool:
    if when.strip() == "true":
        return True
    namespace: dict[str, Any] = {
        **{name: name for name in GROWTH_MAIN},
        **{lvl: lvl for lvl in ("strong", "medium", "weak", "none")},
        "eq": lambda b, lvl: _get(bands, b) == lvl,
        "ge": lambda b, lvl: _level_ge(_get(bands, b), lvl),
        "any_main_eq": lambda lvl: any(_get(bands, m) == lvl for m in GROWTH_MAIN),
        "count_main_eq": lambda lvl, op, n: _compare(
            sum(1 for m in GROWTH_MAIN if _get(bands, m) == lvl), op, n,
        ),
        # 单一主载体=lvl, 其他全弱/none
        "all_other_mains_weak_or_none": lambda lvl: True,  # 配合 count_main_eq 使用
    }
    # all_other_mains_weak_or_none 需要更精确的实现:
    # 含义: 命中维度的 band == lvl, 其他维度 ∈ {weak, none}
    def all_others_weak_or_none(focus_level: BandLevel) -> bool:
        focus_count = sum(1 for m in GROWTH_MAIN if _get(bands, m) == focus_level)
        if focus_count != 1:
            return False
        others = [m for m in GROWTH_MAIN if _get(bands, m) != focus_level]
        return all(_get(bands, m) in ("weak", "none") for m in others)
    namespace["all_other_mains_weak_or_none"] = all_others_weak_or_none

    return bool(eval(when, {"__builtins__": {}}, namespace))  # noqa: S307


def lookup_growth(bands: GrowthBands) -> GrowthTruthTableMatch:
    cfg = load_config("truth_table_growth.yaml")
    order: list[str] = cfg["priority_order"]
    rules: dict[str, dict[str, Any]] = {r["id"]: r for r in cfg["rules"]}
    for rule_id in order:
        rule = rules[rule_id]
        if _eval(rule["when"], bands):
            return GrowthTruthTableMatch(
                matched_pattern=rule_id,
                type=cast(GrowthType, rule["type"]),
                decision_tier=cast(DecisionTier, rule["decision_tier"]),
                bands_snapshot=bands,   # ★ 输入快照
            )
    raise RuntimeError("growth truth table did not match G-F1 fallback")


def compute_growth_bands(features: GrowthFeatures) -> GrowthBands:
    """4 维分档.

    location: 优先用 features.location_match.band (DBCH 直出, ADR-0005);
              缺失时 fallback 旧的 score → 阈值
    theme:    优先用 features.theme_match.band (语义簇匹配直出, ADR-0008);
              缺失时 fallback dimension_bands.theme 阈值
    event:    优先用 features.event_match.band (三级分层匹配直出, ADR-0009);
              缺失时 fallback dimension_bands.event 阈值
    anchor:   仍走 dimension_bands.yaml 阈值
    """
    cfg = load_config("dimension_thresholds.yaml")
    db = cfg["dimension_bands"]

    # location: DBCH 优先
    if features.location_match is not None:
        location = features.location_match.band
        # DBCH 内部已处理 cluster 级 is_low_quality 降档 (ADR-0006);
        # 这里的 is_high_frequency_place 是相册级 OR 新照片级, 兜底再降一次
        if (
            features.is_high_frequency_place
            and cfg.get("high_frequency_place_downgrade", True)
            and not features.location_match.diagnostics.get("is_low_quality", False)
        ):
            location = _downgrade(location)
    else:
        # 兼容路径 (无 DBCH 输入时)
        location = _classify(features.location_score, db["location"])
        if features.is_high_frequency_place and cfg.get("high_frequency_place_downgrade", True):
            location = _downgrade(location)

    # theme: 语义簇匹配优先 (ADR-0008)
    if features.theme_match is not None:
        theme = features.theme_match.band
    else:
        theme = _classify(features.theme_overlap_score, db["theme"])

    # event: 三级分层匹配优先 (ADR-0009)
    if features.event_match is not None:
        event = features.event_match.band
    else:
        event = _classify(features.event_similarity_score, db["event"])

    return GrowthBands(
        location=location,
        theme=theme,
        event=event,
        anchor=_classify(features.anchor_overlap_score, db["anchor"]),
    )


def _classify(score: float, dim_cfg: dict) -> BandLevel:
    if score >= dim_cfg["strong"]:
        return "strong"
    if score >= dim_cfg["medium"]:
        return "medium"
    if score >= dim_cfg["weak"]:
        return "weak"
    return "none"


def _downgrade(level: BandLevel) -> BandLevel:
    order: list[BandLevel] = ["strong", "medium", "weak", "none"]
    idx = order.index(level)
    return order[min(idx + 1, len(order) - 1)]
