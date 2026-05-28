"""LLM Judge · 语义复核.

v0.1: MockJudge (确定性, 给真值表 bounds_min 同等强度)
v0.2: AnthropicJudge (claude-sonnet-4-6) — 留接口, 不实现

参考: docs/01_architecture.md §4
"""
from __future__ import annotations

from typing import Protocol, cast

from src.contracts import (
    Bands,
    EvidenceItem,
    FeaturePackage,
    L1Output,
    LLMJudgement,
    TruthTableMatch,
)
from src.contracts.decision import BoundsLevel
from src.contracts.features import BandLevel
from src.policy.config_loader import load_config

# bounds level → BandLevel
_BOUNDS_TO_BAND: dict[BoundsLevel, BandLevel] = {
    "strong": "strong",
    "medium": "medium",
    "light": "weak",
    "none": "none",
}


class LLMJudge(Protocol):
    """LLM Judge 接口."""

    def judge(
        self,
        photos: list[L1Output],
        features: FeaturePackage,
        bands: Bands,
        truth_table: TruthTableMatch,
    ) -> LLMJudgement:
        ...


class MockJudge:
    """v0.1 确定性 mock.

    策略:
      - proposed_strength = bounds_min (保证 clamp 后落在合规区间最低值)
      - proposed_type = 真值表给出的 type
      - evidence 从 photo.individual_understanding 构造一句话
      - counter_evidence 占位

    这样保证测试可复现,且 G1 在 mock 阶段不达 strong (符合 OQ-001).
    """

    def judge(
        self,
        photos: list[L1Output],
        features: FeaturePackage,
        bands: Bands,
        truth_table: TruthTableMatch,
    ) -> LLMJudgement:
        cfg = load_config("llm_settings.yaml")
        mock_cfg = cfg.get("mock", {})

        proposed_strength = _BOUNDS_TO_BAND[truth_table.bounds_min]

        evidence_count = int(mock_cfg.get("default_evidence_count", 3))
        evidence: list[EvidenceItem] = []
        for p in photos[:evidence_count]:
            evidence.append(EvidenceItem(
                photo_id=p.photo_id,
                evidence=(p.individual_understanding[:60] + "…")
                if len(p.individual_understanding) > 60
                else p.individual_understanding,
            ))

        return LLMJudgement(
            proposed_type=truth_table.type,
            proposed_strength=proposed_strength,
            semantic_reason=f"mock:{truth_table.matched_pattern}",
            evidence=evidence,
            counter_evidence=str(mock_cfg.get(
                "default_counter_evidence",
                "v0.1 mock 阶段, counter_evidence 占位",
            )),
            confidence_adjustment=float(mock_cfg.get("default_confidence_adjustment", 0.0)),
            is_mock=True,
        )


class AnthropicJudge:
    """v0.2 真 LLM 接入 (留接口)."""

    def judge(
        self,
        photos: list[L1Output],
        features: FeaturePackage,
        bands: Bands,
        truth_table: TruthTableMatch,
    ) -> LLMJudgement:
        raise NotImplementedError(
            "AnthropicJudge not implemented in v0.1. Use MockJudge.",
        )


def get_judge() -> LLMJudge:
    """按 config/llm_settings.yaml 的 provider 选择实现.

    ADR-0020: env var SEENFUL_LLM_MODE 优先 (mock/real).
    """
    import os
    mode = os.environ.get("SEENFUL_LLM_MODE")
    if mode == "real":
        from .qwen_judge import QwenJudge
        return QwenJudge()
    if mode == "mock":
        return MockJudge()

    cfg = load_config("llm_settings.yaml")
    provider = cfg.get("provider", "mock")
    if provider == "mock":
        return MockJudge()
    if provider == "qwen":
        from .qwen_judge import QwenJudge
        return QwenJudge()
    if provider == "anthropic":
        return AnthropicJudge()
    raise ValueError(f"unsupported LLM provider: {provider}")
