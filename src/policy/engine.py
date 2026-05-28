"""Policy Engine · 整合 bands / truth_table / hard_rules / clamp / 后置.

参考:
  docs/01_architecture.md
  docs/03_truth_table_main.md
  docs/06_hard_rules.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from src.contracts import (
    Association,
    Bands,
    FeaturePackage,
    LLMJudgement,
    PolicyOverride,
    TruthTableMatch,
)
from src.contracts.decision import BoundsLevel, DisplayDecision
from src.contracts.features import BandLevel

from .bands import compute_bands
from .truth_table import lookup as truth_table_lookup

# light (bounds 层) == weak (BandLevel)
BOUNDS_TO_BAND: dict[BoundsLevel, BandLevel] = {
    "strong": "strong",
    "medium": "medium",
    "light": "weak",
    "none": "none",
}
BAND_ORDER: dict[BandLevel, int] = {"strong": 3, "medium": 2, "weak": 1, "none": 0}


@dataclass
class FinalDecisionDraft:
    bands: Bands
    truth_table: TruthTableMatch
    llm: LLMJudgement | None
    final_strength: BandLevel
    final_type: str
    primary_signal: str
    display_decision: DisplayDecision
    reason: str
    score: float
    decision_source: str
    policy_overrides: list[PolicyOverride] = field(default_factory=list)


def _bounds_to_band(b: BoundsLevel) -> BandLevel:
    return BOUNDS_TO_BAND[b]


def _clamp_to_bounds(
    llm_strength: BandLevel,
    bounds_min_band: BandLevel,
    bounds_max_band: BandLevel,
) -> tuple[BandLevel, bool]:
    """clamp(LLM_proposed, [min, max]). 返回 (clamped, was_clamped)."""
    lo = BAND_ORDER[bounds_min_band]
    hi = BAND_ORDER[bounds_max_band]
    cur = BAND_ORDER[llm_strength]
    if cur < lo:
        for lvl, idx in BAND_ORDER.items():
            if idx == lo:
                return lvl, True
    if cur > hi:
        for lvl, idx in BAND_ORDER.items():
            if idx == hi:
                return lvl, True
    return llm_strength, False


def _primary_signal_of(bands: Bands, tt: TruthTableMatch) -> str:
    """根据真值表类型选 primary_signal 字段名."""
    mapping = {
        "location": "exif_location",
        "thematic": "theme_tags",
        "event": "event_hint",
        "people": "people_presence",
        "temporal": "captured_at",
        "mixed": "mixed",
        "weak": "weak",
        "emotional": "emotional_tone",
        "visual": "visual",
    }
    return mapping.get(tt.type, tt.type)


def _display_from_strength(strength: BandLevel) -> DisplayDecision:
    """HR-POST-01/02/04."""
    if strength in ("strong", "medium"):
        return "show_mini_album"
    if strength == "weak":
        return "show_inline_hint"
    return "suppress"


def _composite_score(features: FeaturePackage, strength: BandLevel) -> float:
    """监控用综合 score (不参与决策).

    简易版:主载体 0.6 权,放大器 0.2 权,辅证 0.2 权,叠加 strength 校准.
    """
    main_avg = (
        features.location_score + features.theme_score
        + features.event_score + features.people_score
    ) / 4
    amp = features.time_score
    aux_avg = (features.anchor_score + features.emotional_score) / 2

    base = 0.6 * main_avg + 0.2 * amp + 0.2 * aux_avg
    strength_boost = {"strong": 0.15, "medium": 0.05, "weak": -0.05, "none": -0.20}[strength]
    return max(0.0, min(1.0, base + strength_boost))


def run_post_truth_table(
    features: FeaturePackage,
    bands: Bands,
    tt: TruthTableMatch,
    llm: LLMJudgement | None,
) -> FinalDecisionDraft:
    """从 Truth Table 命中之后 → 最终裁决.

    Stage 4-7 (见 docs/01_architecture.md).
    F1 → 直接 suppress, llm 应为 None.
    """
    overrides: list[PolicyOverride] = []

    if tt.matched_pattern == "F1":
        return FinalDecisionDraft(
            bands=bands,
            truth_table=tt,
            llm=None,
            final_strength="none",
            final_type="weak",
            primary_signal="weak",
            display_decision="suppress",
            reason="truth_table_f1_no_signal",
            score=_composite_score(features, "none"),
            decision_source="truth_table_f1_suppress",
            policy_overrides=overrides,
        )

    assert llm is not None, "non-F1 must have LLM judgement"

    bounds_min_band = _bounds_to_band(tt.bounds_min)
    bounds_max_band = _bounds_to_band(tt.bounds_max)

    # Stage 5 · clamp
    final_strength, clamped = _clamp_to_bounds(
        llm.proposed_strength, bounds_min_band, bounds_max_band,
    )
    if clamped:
        overrides.append(PolicyOverride(
            rule_id="STAGE5_CLAMP",
            before={"strength": llm.proposed_strength},
            after={"strength": final_strength},
            reason=f"LLM proposed outside bounds [{tt.bounds_min},{tt.bounds_max}]",
        ))

    # Stage 6 · 后置硬规则
    # HR-POST-05 (light_judge_only) v0.1 不实现 (只跑 ≥3 张)
    # HR-POST-03: 高频地点 + 无 theme/event 中以上 → 强制 <= medium
    if features.is_high_frequency_place:
        theme_or_event_strong_enough = bands.theme in ("medium", "strong") or bands.event in ("medium", "strong")
        if not theme_or_event_strong_enough and final_strength == "strong":
            overrides.append(PolicyOverride(
                rule_id="HR-POST-03",
                before={"strength": "strong"},
                after={"strength": "medium"},
                reason="high_frequency_place_without_theme_event_overlay",
            ))
            final_strength = "medium"

    display = _display_from_strength(final_strength)
    primary = _primary_signal_of(bands, tt)
    score = _composite_score(features, final_strength)

    decision_source = (
        "policy_override" if overrides else "policy_engine_with_llm_support"
    )

    return FinalDecisionDraft(
        bands=bands,
        truth_table=tt,
        llm=llm,
        final_strength=final_strength,
        final_type=llm.proposed_type if llm.proposed_type else tt.type,
        primary_signal=primary,
        display_decision=display,
        reason=llm.semantic_reason or tt.matched_pattern,
        score=score,
        decision_source=decision_source,
        policy_overrides=overrides,
    )


def to_association(draft: FinalDecisionDraft) -> Association:
    return Association(
        score=draft.score,
        type=cast(str, draft.final_type),  # validated via Literal in Pydantic
        strength=draft.final_strength,
        primary_signal=draft.primary_signal,
        reason=draft.reason,
        display_decision=draft.display_decision,
    )
