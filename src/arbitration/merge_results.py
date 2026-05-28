"""三路结果汇合 · 严格优先级仲裁.

参考: docs/09_arbitration.md + docs/23_pipeline_cascade_backfill.md (ADR-0017)
"""
from __future__ import annotations

import uuid

from src.contracts import (
    ArbitrationEnding,
    ArbitrationResult,
    ArbitrationWinner,
    Association,
    BackfillDecisionLog,
    DecisionLog,
    GrowthDecisionLog,
    GrowthMergeRecord,
)

USER_MESSAGES: dict[ArbitrationEnding, str] = {
    "add_to_existing_album": "那本《{album}》又添了一笔",
    "ask_user_confirm": "这张和《{album}》有点接得上,要不要放进去?",
    "create_new_album_path_b": "这几张接得上,我帮你收好了",
    "create_new_album_backfill": "这几张拼起来,像是一段日子",
    "create_multiple_cascade_albums": "我把这阵子的几张拢成了几本",     # ADR-0017
    "single_photo_sediment": "",
    "ask_user_pending": "(等待用户回应)",
}


def arbitrate(
    growth: GrowthDecisionLog | None,
    l2: DecisionLog | None,
    backfill: BackfillDecisionLog | None,
    scenario: str | None = None,
) -> ArbitrationResult:
    """严格优先级: A > B > C > 沉淀.

    Case 1: A 命中 (auto_merge / ask_user) → 走 A, B/C 作废
    Case 2: A 未命中 + B 命中 (show_mini_album) → 走 B, C 作废
    Case 3: A + B 都未命中 + C 命中 (create_new_album) → 走 C
    Case 4: 三路全空 → 单图沉淀
    """
    arb_id = f"arb_{uuid.uuid4().hex[:8]}"
    discarded: list[str] = []

    # ─── Case 1: 路径 A 命中 ────────────────────────
    if growth and growth.final_decision.decision_tier in ("auto_merge", "ask_user"):
        tier = growth.final_decision.decision_tier
        ending: ArbitrationEnding = (
            "add_to_existing_album" if tier == "auto_merge" else "ask_user_confirm"
        )
        if l2:
            discarded.append("path_B")
        if backfill:
            discarded.append("path_C")
        return ArbitrationResult(
            arbitration_id=arb_id,
            scenario=scenario,
            growth_log=growth,
            l2_log=l2,
            backfill_log=backfill,
            arbitration_winner="path_A",
            ending=ending,
            target_album_id=growth.final_decision.merge_target_album_id,
            user_facing_message=USER_MESSAGES[ending].format(
                album=growth.final_decision.merge_target_album_id or "X"
            ),
            discarded_paths=discarded,
            case_matched="Case 1",
        )

    # ─── Case 2: 路径 B 命中 ────────────────────────
    if l2 and l2.final_decision.association.display_decision == "show_mini_album":
        if backfill:
            discarded.append("path_C")
        return ArbitrationResult(
            arbitration_id=arb_id,
            scenario=scenario,
            growth_log=growth,
            l2_log=l2,
            backfill_log=backfill,
            arbitration_winner="path_B",
            ending="create_new_album_path_b",
            target_album_id=None,
            target_album_strength=l2.final_decision.association.strength,
            user_facing_message=USER_MESSAGES["create_new_album_path_b"],
            discarded_paths=discarded,
            case_matched="Case 2",
        )

    # ─── Case 3: 路径 C 命中 ────────────────────────
    if backfill and backfill.final_decision.decision_tier == "create_new_album":
        return ArbitrationResult(
            arbitration_id=arb_id,
            scenario=scenario,
            growth_log=growth,
            l2_log=l2,
            backfill_log=backfill,
            arbitration_winner="path_C",
            ending="create_new_album_backfill",
            target_album_id=None,
            target_album_strength=backfill.final_decision.target_album_strength,
            user_facing_message=USER_MESSAGES["create_new_album_backfill"],
            discarded_paths=discarded,
            case_matched="Case 3",
        )

    # ─── Case 4: 三路全空 → 单图沉淀 ────────────────
    return ArbitrationResult(
        arbitration_id=arb_id,
        scenario=scenario,
        growth_log=growth,
        l2_log=l2,
        backfill_log=backfill,
        arbitration_winner="none",
        ending="single_photo_sediment",
        target_album_id=None,
        user_facing_message="",
        discarded_paths=[],
        case_matched="Case 4",
    )


# ═════════════════════════════════════════════════════════════════
# ADR-0017: 多产物仲裁 (N≥3 拆 N 张 dispatch)
# ═════════════════════════════════════════════════════════════════

def arbitrate_cascade(
    l2_log: DecisionLog,
    growth_merges: list[GrowthMergeRecord],
    cascade_albums: list[Association],
    settled_photo_ids: list[str],
    cascade_logs: list[BackfillDecisionLog],
    scenario: str | None = None,
) -> ArbitrationResult:
    """ADR-0017: N≥3 B 失败拆 N 张后, 合并多产物.

    Case 5: B 失败, 仅 A 命中部分 (growth_merges)
    Case 6: B 失败, 仅 cascade 命中 (cascade_albums)
    Case 7: B 失败, A + cascade 都命中
    Case 8: B 失败, 全部沉淀
    """
    arb_id = f"arb_{uuid.uuid4().hex[:8]}"

    has_growth = len(growth_merges) > 0
    has_cascade = len(cascade_albums) > 0

    if not has_growth and not has_cascade:
        ending: ArbitrationEnding = "single_photo_sediment"
        winner: ArbitrationWinner = "none"
        case = "Case 8"
        message = ""
    elif has_cascade and has_growth:
        ending = "create_multiple_cascade_albums"
        winner = "cascade"
        case = "Case 7"
        message = USER_MESSAGES[ending]
    elif has_cascade:
        ending = "create_multiple_cascade_albums" if len(cascade_albums) > 1 else "create_new_album_backfill"
        winner = "cascade"
        case = "Case 6"
        message = USER_MESSAGES[ending]
    else:  # only growth
        # 部分张走 A 命中, 但没成 cascade 集
        # 等价于"多张拆 N 张, 部分进老相册, 其余沉淀"
        ending = "add_to_existing_album"
        winner = "path_A"
        case = "Case 5"
        first = growth_merges[0]
        message = USER_MESSAGES[ending].format(album=first.target_album_id)

    return ArbitrationResult(
        arbitration_id=arb_id,
        scenario=scenario,
        growth_log=None,
        l2_log=l2_log,
        backfill_log=None,
        cascade_albums=cascade_albums,
        growth_merges=growth_merges,
        settled_photo_ids=settled_photo_ids,
        cascade_logs=cascade_logs,
        arbitration_winner=winner,
        ending=ending,
        target_album_id=growth_merges[0].target_album_id if growth_merges else None,
        user_facing_message=message,
        discarded_paths=["path_B"] if not has_growth and not has_cascade else [],
        case_matched=case,
    )
