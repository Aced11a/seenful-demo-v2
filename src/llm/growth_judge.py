"""动态生长 LLM Judge (路径 A · Step 5).

v0.1: MockGrowthJudge 直接 accept=True, evidence 占位.
v0.2 (ADR-0020): QwenGrowthJudge 接 DashScope qwen-turbo.
"""
from __future__ import annotations

import json
import os
from typing import Protocol

from src.contracts import (
    GrowthBands,
    GrowthFeatures,
    GrowthLLMJudgement,
    GrowthTruthTableMatch,
    L1Output,
    MiniAlbumFingerprint,
)
from src.policy.config_loader import load_config


class GrowthLLMJudge(Protocol):
    def judge(
        self,
        new_photo: L1Output,
        album: MiniAlbumFingerprint,
        features: GrowthFeatures,
        bands: GrowthBands,
        truth_table: GrowthTruthTableMatch,
    ) -> GrowthLLMJudgement: ...


class MockGrowthJudge:
    """v0.1 确定性 mock: 命中真值表 G-A/G-B/G-C 系 → accept=True; G-F1 不调."""

    def judge(
        self,
        new_photo: L1Output,
        album: MiniAlbumFingerprint,
        features: GrowthFeatures,
        bands: GrowthBands,
        truth_table: GrowthTruthTableMatch,
    ) -> GrowthLLMJudgement:
        return GrowthLLMJudgement(
            accept=truth_table.decision_tier != "no_merge",
            semantic_reason=f"mock:{truth_table.matched_pattern}",
            counter_evidence="v0.1 mock 占位",
            confidence_adjustment=0.0,
            is_mock=True,
        )


_GROWTH_SYSTEM_PROMPT = """你是 Seenful 的 L2.5 动态生长判断引擎.

你判断: 这张新照片**是否应该并入**这本已有相册?

严格约束:
1. 你只返回 accept (true/false) + 理由
2. 不输出 decision_tier (auto_merge/ask_user/no_merge 由 Policy Engine 决定)
3. confidence_adjustment 必须在 -0.1 到 +0.1

返回严格的 JSON, 不要 markdown."""


class QwenGrowthJudge:
    """ADR-0020: 路径 A 真 LLM 接入."""

    def __init__(self):
        cfg = load_config("llm_settings.yaml")
        self._cfg = cfg.get("qwen", {})
        self._degrade = bool(self._cfg.get("graceful_degrade_to_mock", True))

    def judge(
        self,
        new_photo: L1Output,
        album: MiniAlbumFingerprint,
        features: GrowthFeatures,
        bands: GrowthBands,
        truth_table: GrowthTruthTableMatch,
    ) -> GrowthLLMJudgement:
        from .qwen_judge import _call_dashscope
        user_prompt = (
            f"## 新照片\n"
            f"- id: {new_photo.photo_id}\n"
            f"- 标题: {new_photo.individual_title}\n"
            f"- 主题: {new_photo.theme_tags}\n"
            f"- event: {new_photo.semantic_facts.event_hint}\n"
            f"- tone: {new_photo.emotional_tone}\n"
            f"\n## 老相册\n"
            f"- id: {album.mini_album_id}\n"
            f"- 标题: {album.title}\n"
            f"- 主题簇: {[c.representative for c in album.theme_clusters]}\n"
            f"- primary event: {album.event_agg.primary}\n"
            f"\n## 4 维 bands\n"
            f"- location={bands.location} theme={bands.theme} "
            f"event={bands.event} anchor={bands.anchor}\n"
            f"\n## 真值表\n- pattern: {truth_table.matched_pattern}\n"
            f"\n## 你的任务\n"
            f"严格 JSON 返回:\n"
            f'{{"accept": true|false, "semantic_reason": "30 字以内",'
            f' "counter_evidence": "string|null", "confidence_adjustment": 0.0}}'
        )

        try:
            response = _call_dashscope(_GROWTH_SYSTEM_PROMPT, user_prompt, self._cfg)
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
                if text.startswith("json"):
                    text = text[4:]
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                s, e = text.find("{"), text.rfind("}")
                obj = json.loads(text[s:e + 1])

            ca = max(-0.1, min(0.1, float(obj.get("confidence_adjustment", 0.0))))
            return GrowthLLMJudgement(
                accept=bool(obj.get("accept", True)),
                semantic_reason=str(obj.get("semantic_reason", "qwen"))[:100],
                counter_evidence=(str(obj["counter_evidence"])[:200]
                                  if obj.get("counter_evidence") else "Qwen 未给反证"),
                confidence_adjustment=ca,
                is_mock=False,
            )
        except Exception as e:
            if self._degrade:
                fallback = MockGrowthJudge().judge(new_photo, album, features, bands, truth_table)
                fallback.semantic_reason = f"qwen_failed_mock_fallback: {str(e)[:50]}"
                return fallback
            raise


def get_growth_judge() -> GrowthLLMJudge:
    """ADR-0020: env var SEENFUL_LLM_MODE 优先."""
    mode = os.environ.get("SEENFUL_LLM_MODE")
    if mode == "real":
        return QwenGrowthJudge()
    if mode == "mock":
        return MockGrowthJudge()
    cfg = load_config("llm_settings.yaml")
    provider = cfg.get("provider", "mock")
    if provider == "qwen":
        return QwenGrowthJudge()
    return MockGrowthJudge()
