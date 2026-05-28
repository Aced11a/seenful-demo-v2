"""兜底专用 Policy Engine 封顶.

参考: docs/05_truth_table_backfill.md §兜底专用 Policy Engine 封顶
"""
from __future__ import annotations

from dataclasses import dataclass

from src.contracts import (
    BackfillCap,
    BackfillDecision,
    L1Output,
    LLMJudgement,
    TruthTableMatch,
)
from src.contracts.backfill import BackfillTier
from src.policy.config_loader import load_config


@dataclass
class BackfillEngineResult:
    decision: BackfillDecision
    caps: list[BackfillCap]


def apply_backfill_caps(
    new_photo: L1Output,
    recalled_photos: list[L1Output],
    truth_table: TruthTableMatch | None,
    llm: LLMJudgement | None,
) -> BackfillEngineResult:
    """三条硬性封顶:
      1. truth_table.bounds_max == strong
      2. llm.proposed_strength == strong
      3. recalled_photos >= min_recalled_photos (默认 2)
    全部满足 → create_new_album, 否则 no_backfill / insufficient_candidates.
    """
    cfg = load_config("truth_table_backfill.yaml")
    caps_cfg = cfg["caps"]
    min_recall = int(caps_cfg["min_recalled_photos"])
    max_recall = int(cfg.get("max_recall_photos", 4))

    caps: list[BackfillCap] = []

    # CAP-03 召回数量先判 (insufficient_candidates 是独立 tier)
    insufficient = len(recalled_photos) < min_recall
    caps.append(BackfillCap(
        rule="BACKFILL-CAP-03-recall_count",
        passed=not insufficient,
        detail=f"recalled={len(recalled_photos)}, min_required={min_recall}",
    ))

    if insufficient:
        return BackfillEngineResult(
            decision=BackfillDecision(
                backfill_decision_id="",
                new_photo_id=new_photo.photo_id,
                decision_tier="insufficient_candidates",
                recalled_photo_ids=[p.photo_id for p in recalled_photos],
                target_album_strength=None,
                primary_signal="none",
                reason=f"recall_count {len(recalled_photos)} < {min_recall}",
            ),
            caps=caps,
        )

    # CAP-01 主真值表 bounds_max
    tt_strong = (
        truth_table is not None
        and truth_table.bounds_max == "strong"
        and caps_cfg.get("require_truth_table_bounds_max_strong", True)
    )
    caps.append(BackfillCap(
        rule="BACKFILL-CAP-01-bounds_max_strong",
        passed=tt_strong,
        detail=(
            f"matched_pattern={truth_table.matched_pattern}, "
            f"bounds_max={truth_table.bounds_max}"
        ) if truth_table else "no truth_table match",
    ))

    # CAP-02 LLM proposed_strength
    llm_strong = (
        llm is not None
        and llm.proposed_strength == "strong"
        and caps_cfg.get("require_llm_proposed_strength_strong", True)
    )
    caps.append(BackfillCap(
        rule="BACKFILL-CAP-02-llm_strength_strong",
        passed=llm_strong,
        detail=(
            f"proposed_strength={llm.proposed_strength}" if llm else "no llm"
        ),
    ))

    all_pass = tt_strong and llm_strong

    if all_pass:
        recalled_capped = recalled_photos[:max_recall]
        decision = BackfillDecision(
            backfill_decision_id="",
            new_photo_id=new_photo.photo_id,
            decision_tier="create_new_album",
            recalled_photo_ids=[p.photo_id for p in recalled_capped],
            target_album_strength="strong",
            primary_signal=_primary_signal(truth_table.type if truth_table else "weak"),
            reason=f"backfill_{truth_table.matched_pattern}_strong",
        )
    else:
        failed_caps = [c.rule for c in caps if not c.passed]
        decision = BackfillDecision(
            backfill_decision_id="",
            new_photo_id=new_photo.photo_id,
            decision_tier="no_backfill",
            recalled_photo_ids=[p.photo_id for p in recalled_photos],
            target_album_strength=None,
            primary_signal="none",
            reason="caps_failed: " + ",".join(failed_caps),
        )

    return BackfillEngineResult(decision=decision, caps=caps)


def _primary_signal(tt_type: str) -> str:
    mapping = {
        "location": "exif_location",
        "thematic": "theme_tags",
        "event": "event_hint",
        "people": "people_presence",
        "temporal": "captured_at",
        "mixed": "mixed",
        "weak": "weak",
        "emotional": "emotional_tone",
    }
    return mapping.get(tt_type, tt_type)
