"""兜底回扫 (路径 C) 契约.

参考: docs/05_truth_table_backfill.md + docs/23_pipeline_cascade_backfill.md (ADR-0017)
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .decision import LLMJudgement, TruthTableMatch

BackfillTier = Literal[
    "create_new_album",
    "no_backfill",
    "insufficient_candidates",
]


class BackfillCap(BaseModel):
    rule: str
    passed: bool
    detail: str = ""


class PriorityRankingEntry(BaseModel):
    """ADR-0017: cascade 粗筛后每候选的维度强度总分 (落痕用).

    参考: docs/23_pipeline_cascade_backfill.md §二.
    score = (gps<1km ? 1.0 : 0) + (theme>0.5 ? 1.0 : 0) + (event 一致 ? 0.5 : 0)
    """
    photo_id: str
    gps_within_1km: bool
    theme_jaccard_above_0_5: bool
    event_match: bool
    score: float
    selected: bool                                # 是否进入 top max_recall_photos (PRD §3.10.5)


class BackfillDecision(BaseModel):
    backfill_decision_id: str
    new_photo_id: str
    decision_tier: BackfillTier
    recalled_photo_ids: list[str] = Field(default_factory=list)
    target_album_strength: str | None = None
    primary_signal: str = ""
    reason: str = ""


class BackfillDecisionLog(BaseModel):
    decision_id: str
    scenario: str | None = None
    path_taken: Literal["path_C"] = "path_C"
    new_photo_id: str
    coarse_filter_candidates: list[str] = Field(default_factory=list)
    priority_ranking: list[PriorityRankingEntry] = Field(
        default_factory=list,
        description="ADR-0017: cascade_backfill_single 落痕所有粗筛候选的 score",
    )
    main_truth_table_match: TruthTableMatch | None = None
    llm_judgement: LLMJudgement | None = None
    backfill_caps_applied: list[BackfillCap] = Field(default_factory=list)
    policy_overrides: list[dict[str, Any]] = Field(default_factory=list)
    final_decision: BackfillDecision
