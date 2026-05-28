"""高频低质量地点判定契约 (ADR-0006).

参考: docs/13_low_quality_place_detection.md
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SignalSource = Literal[
    "plan_a",                # Plan A 判定 (双 density)
    "plan_b",                # Plan B 判定 (POI + NIMA + 行为)
    "frequency_failed",      # 频率门槛不过
    "baseline_missing",      # 用户 baseline 数据不足
    "disabled",              # plan_a + plan_b 都关闭
    "no_user_context",       # v0.1: 没传 user_context → 跳过判定
]


class UserDensityBaseline(BaseModel):
    """用户个人 L1 双 density 的 25 分位 (Plan A).

    阈值用用户自己的 25 分位数, 防"不会拍照"用户被全部误判.
    """
    user_id: str
    meaning_threshold: float = Field(ge=0.0, le=1.0)
    aesthetic_threshold: float = Field(ge=0.0, le=1.0)
    last_computed_at: datetime
    sample_size: int = Field(
        ge=0,
        description="参与计算的照片数, 须 ≥ min_samples_for_baseline 才视为有效",
    )


class LowQualityResult(BaseModel):
    """is_low_quality_place 返回结构, 含完整诊断."""
    is_low_quality: bool
    signal_source: SignalSource
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class UserContext(BaseModel):
    """运行时上下文 — match_against_cluster 调 is_low_quality_place 所需输入.

    生产环境从用户档案 / 历史照片库构造; v0.1 demo 可传 None 跳过判定.
    """
    user_id: str
    account_age_days: int = Field(ge=0)
    user_history: list[Any] = Field(
        default_factory=list,
        description="用户历史照片 list[L1Output] 等价表示 (前向引用避免循环)",
    )
    baseline: UserDensityBaseline | None = None    # 缓存的 baseline (重算成本高)
