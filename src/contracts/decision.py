"""真值表命中 / LLM 判定 / 最终裁决 / 决策日志契约。

参考: docs/02_data_contracts.md, docs/11_observability.md
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .features import BandLevel, Bands

DisplayDecision = Literal[
    "show_mini_album",
    "show_inline_hint",
    "suppress",
    "merge_into_existing",
    "ask_user_merge",
]
AssociationType = Literal[
    "location", "temporal", "event", "thematic",
    "people", "emotional", "visual", "mixed", "weak",
]
BoundsLevel = Literal["strong", "medium", "light", "none"]  # 真值表 bounds 用 light


class TruthTableMatch(BaseModel):
    """Step 3 Stage 3 输出: 命中的真值表行。

    重要语义区分 (见 docs/02_data_contracts.md):
      · bounds_min/bounds_max = 输出约束 (LLM proposed_strength 允许区间)
      · bands_snapshot         = 输入快照 (命中时 7 维 Bands 全部钉住, 自包含)
    """
    matched_pattern: str  # "A1" | "B7" | "F1" ...
    type: AssociationType
    bounds_min: BoundsLevel
    bounds_max: BoundsLevel
    bands_snapshot: Bands | None = None    # ★ v0.1.1: 输入快照, 默认 None 兼容旧数据


class EvidenceItem(BaseModel):
    photo_id: str
    evidence: str


class LLMJudgement(BaseModel):
    """Step 4 LLM 输出。绝不含 score / display_decision。"""
    proposed_type: AssociationType
    proposed_strength: BandLevel
    semantic_reason: str = Field(default="", max_length=200)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    counter_evidence: str = ""
    confidence_adjustment: float = Field(default=0.0, ge=-0.1, le=0.1)
    is_mock: bool = False


class PolicyOverride(BaseModel):
    """Policy Engine 改写 LLM/真值表输出时的留痕。"""
    rule_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str


class Association(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    type: AssociationType
    strength: BandLevel
    primary_signal: str
    reason: str
    display_decision: DisplayDecision


class AssociationDecision(BaseModel):
    association_id: str
    photo_ids: list[str]
    association: Association
    decision_source: Literal[
        "policy_engine_with_llm_support",
        "policy_override",
        "pre_filter_strong",
        "pre_filter_reject",
        "truth_table_f1_suppress",
    ]


class DecisionLog(BaseModel):
    """完整决策日志,落痕用。"""
    decision_id: str
    scenario: str | None = None
    path_taken: Literal["path_A", "path_B", "path_C"] = "path_B"
    feature_assembler_plan: Literal["L2_2.0", "L2_1.0"] = "L2_2.0"   # ADR-0018
    stages: dict[str, Any] = Field(default_factory=dict)
    policy_overrides: list[PolicyOverride] = Field(default_factory=list)
    decision_source: str
    final_decision: AssociationDecision
