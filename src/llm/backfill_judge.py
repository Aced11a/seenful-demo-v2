"""兜底回扫 LLM Judge (路径 C · Step 5 复核).

v0.1: 复用 MockJudge, system prompt 追加兜底场景指引 (落痕).
v0.2 (ADR-0020): QwenBackfillJudge 接 DashScope qwen-turbo, system prompt 加兜底指引.
"""
from __future__ import annotations

import os

from src.contracts import (
    Bands,
    FeaturePackage,
    L1Output,
    LLMJudgement,
    TruthTableMatch,
)
from src.llm.judge import LLMJudge, MockJudge
from src.policy.config_loader import load_config


class MockBackfillJudge:
    """v0.1 mock 兜底专用."""

    def __init__(self, base: LLMJudge | None = None) -> None:
        self.base = base or MockJudge()

    def judge(
        self,
        photos: list[L1Output],
        features: FeaturePackage,
        bands: Bands,
        truth_table: TruthTableMatch,
    ) -> LLMJudgement:
        judgement = self.base.judge(photos, features, bands, truth_table)
        if truth_table.bounds_max == "strong":
            judgement.proposed_strength = "strong"
        addendum = load_config("truth_table_backfill.yaml").get(
            "llm_system_prompt_addendum", ""
        ).strip()
        judgement.semantic_reason = (
            f"{judgement.semantic_reason} | backfill_context: "
            + addendum.split("\n")[0]
        )
        return judgement


class QwenBackfillJudge:
    """ADR-0020: 路径 C cascade 真 LLM 接入. 复用 QwenJudge 但 system prompt 追加兜底指引."""

    def __init__(self):
        cfg = load_config("llm_settings.yaml")
        self._cfg = cfg.get("qwen", {})
        self._degrade = bool(self._cfg.get("graceful_degrade_to_mock", True))
        # 加载 backfill 兜底 prompt 追加
        bf_cfg = load_config("truth_table_backfill.yaml")
        self._addendum = bf_cfg.get("llm_system_prompt_addendum", "").strip()

    def judge(
        self,
        photos: list[L1Output],
        features: FeaturePackage,
        bands: Bands,
        truth_table: TruthTableMatch,
    ) -> LLMJudgement:
        from .qwen_judge import _SYSTEM_PROMPT_BASE, _build_user_prompt, _call_dashscope, _parse_judgement

        # 系统 prompt 追加兜底场景说明
        system_prompt = _SYSTEM_PROMPT_BASE + "\n\n## 兜底场景特别提示\n" + self._addendum
        user_prompt = _build_user_prompt(photos, features, bands, truth_table)

        try:
            response = _call_dashscope(system_prompt, user_prompt, self._cfg)
            judgement = _parse_judgement(response, truth_table)
            judgement.semantic_reason = f"{judgement.semantic_reason} | backfill_qwen"
            return judgement
        except Exception as e:
            if self._degrade:
                fallback = MockBackfillJudge().judge(photos, features, bands, truth_table)
                fallback.semantic_reason = f"qwen_failed_mock_fallback: {str(e)[:50]}"
                return fallback
            raise


def get_backfill_judge():
    """ADR-0020: env var SEENFUL_LLM_MODE 优先."""
    mode = os.environ.get("SEENFUL_LLM_MODE")
    if mode == "real":
        return QwenBackfillJudge()
    if mode == "mock":
        return MockBackfillJudge()
    cfg = load_config("llm_settings.yaml")
    provider = cfg.get("provider", "mock")
    if provider == "qwen":
        return QwenBackfillJudge()
    return MockBackfillJudge()
