"""三路仲裁器契约.

参考: docs/09_arbitration.md + docs/23_pipeline_cascade_backfill.md (ADR-0017)
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .backfill import BackfillDecisionLog
from .decision import Association, DecisionLog
from .growth import GrowthDecisionLog

ArbitrationWinner = Literal["path_A", "path_B", "path_C", "cascade", "none"]
ArbitrationEnding = Literal[
    "add_to_existing_album",
    "ask_user_confirm",
    "create_new_album_path_b",
    "create_new_album_backfill",
    "create_multiple_cascade_albums",       # ADR-0017
    "single_photo_sediment",
    "ask_user_pending",
]


class GrowthMergeRecord(BaseModel):
    """ADR-0017: 单张照片加入老相册的记录 (拆 N 张 dispatch 时用)."""
    photo_id: str
    target_album_id: str
    decision_tier: Literal["auto_merge", "ask_user"]


class ArbitrationResult(BaseModel):
    arbitration_id: str
    scenario: str | None = None

    # 三路原始日志 (落痕用)
    growth_log: GrowthDecisionLog | None = None
    l2_log: DecisionLog | None = None
    backfill_log: BackfillDecisionLog | None = None       # 兼容老入口 (N=1 走 C)

    # ─── ADR-0017 新增: 多产物 (多张 B 失败拆 N 张时填) ───
    cascade_albums: list[Association] = Field(
        default_factory=list,
        description="cascade 产出的新相册 (拆 N 张时 0~N 个)",
    )
    growth_merges: list[GrowthMergeRecord] = Field(
        default_factory=list,
        description="拆 N 张走 A 加入老相册的记录",
    )
    settled_photo_ids: list[str] = Field(
        default_factory=list,
        description="拆 N 张 A C 都失败进 sediment 的 photos",
    )
    cascade_logs: list[BackfillDecisionLog] = Field(
        default_factory=list,
        description="各 P_i cascade 单次完整 log",
    )

    # 最终判决
    arbitration_winner: ArbitrationWinner
    ending: ArbitrationEnding
    target_album_id: str | None = None
    target_album_strength: str | None = None
    user_facing_message: str = ""

    # 仲裁过程留痕
    discarded_paths: list[str] = Field(default_factory=list)
    case_matched: str = ""    # "Case 1-8" (Case 5-8 = ADR-0017 多张拆 N 张)
