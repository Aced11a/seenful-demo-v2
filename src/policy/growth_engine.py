"""动态生长 Policy Engine · 集成 features/bands/truth_table/llm + 后置硬规则.

参考: docs/04_truth_table_growth.md §后置硬规则
"""
from __future__ import annotations

from dataclasses import dataclass

from src.contracts import (
    GrowthBands,
    GrowthCandidateEvaluation,
    GrowthFeatures,
    GrowthLLMJudgement,
    GrowthTruthTableMatch,
    L1Output,
    MiniAlbumFingerprint,
)
from src.contracts.growth import DecisionTier


@dataclass
class GrowthEngineResult:
    evaluation: GrowthCandidateEvaluation
    policy_overrides: list[dict]


def apply_post_hard_rules(
    new_photo: L1Output,
    album: MiniAlbumFingerprint,
    features: GrowthFeatures,
    bands: GrowthBands,
    truth_table: GrowthTruthTableMatch,
    llm: GrowthLLMJudgement,
) -> GrowthEngineResult:
    """跑完真值表 + LLM 之后, 应用后置硬规则得到 final decision_tier."""
    overrides: list[dict] = []
    tier: DecisionTier = truth_table.decision_tier

    # HRG-POST-01: 敏感照片 → no_merge
    if new_photo.sensitive_level in ("medium", "high"):
        overrides.append({
            "rule_id": "HRG-POST-01",
            "before": tier,
            "after": "no_merge",
            "reason": "sensitive_photo",
        })
        tier = "no_merge"

    # HRG-POST-02: 高频地点 + 无 theme/event 中以上 → auto_merge 降为 ask_user
    if (
        features.is_high_frequency_place
        and bands.theme not in ("medium", "strong")
        and bands.event not in ("medium", "strong")
        and tier == "auto_merge"
    ):
        overrides.append({
            "rule_id": "HRG-POST-02",
            "before": "auto_merge",
            "after": "ask_user",
            "reason": "high_frequency_place_without_theme_event_overlay",
        })
        tier = "ask_user"

    # HRG-POST-05: excluded_photo_ids 兜底 (候选集层应已过滤)
    if new_photo.photo_id in album.excluded_photo_ids:
        overrides.append({
            "rule_id": "HRG-POST-05",
            "before": tier,
            "after": "no_merge",
            "reason": "photo_in_excluded_list",
        })
        tier = "no_merge"

    # LLM 复核覆盖 (LLM accept=False 时整体降 1 档)
    if not llm.accept and tier != "no_merge":
        new_tier: DecisionTier = "ask_user" if tier == "auto_merge" else "no_merge"
        overrides.append({
            "rule_id": "LLM_REJECT_DOWNGRADE",
            "before": tier,
            "after": new_tier,
            "reason": "llm_judged_not_belonging",
        })
        tier = new_tier

    primary_signal = {
        "location": "exif_location",
        "thematic": "theme_tags",
        "event": "event_hint",
        "anchor": "meaning_anchors",
        "mixed": "mixed",
        "weak": "weak",
    }.get(truth_table.type, truth_table.type)

    evaluation = GrowthCandidateEvaluation(
        album_id=album.mini_album_id,
        features=features,
        bands=bands,
        truth_table_match=truth_table,
        llm=llm,
        decision_tier=tier,
        primary_signal=primary_signal,
    )
    return GrowthEngineResult(evaluation=evaluation, policy_overrides=overrides)


def resolve_multi_album_conflict(
    evals: list[GrowthCandidateEvaluation],
    albums_by_id: dict[str, MiniAlbumFingerprint],
) -> GrowthCandidateEvaluation | None:
    """HRG-POST-03: 多本相册命中冲突 → 按优先级排序选一本.

    优先级:
      1. location strong > medium > weak > none
      2. 创建时间更晚 (last_updated_at 最新) 优先
    """
    eligible = [e for e in evals if e.decision_tier in ("auto_merge", "ask_user")]
    if not eligible:
        return None

    location_score_order = {"strong": 3, "medium": 2, "weak": 1, "none": 0}

    def sort_key(e: GrowthCandidateEvaluation):
        album = albums_by_id[e.album_id]
        return (
            location_score_order.get(e.bands.location, 0),
            album.last_updated_at,
        )

    eligible.sort(key=sort_key, reverse=True)
    return eligible[0]
