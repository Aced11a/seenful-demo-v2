"""ADR-0020: Qwen LLM Judge (DashScope qwen-turbo, no-thinking).

3 路统一: QwenJudge (path B) / QwenGrowthJudge (path A) / QwenBackfillJudge (path C)

配置: config/llm_settings.yaml::qwen
认证: env var DASHSCOPE_API_KEY
特性: temperature=0 + seed 固定 + retry 2 次 + 失败 graceful_degrade_to_mock
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import urllib.error
import urllib.request

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

_BOUNDS_TO_BAND: dict[BoundsLevel, BandLevel] = {
    "strong": "strong", "medium": "medium", "light": "weak", "none": "none",
}


# ═══════════════════════════════════════════════════════════════
# Prompt 模板
# ═══════════════════════════════════════════════════════════════

_SYSTEM_PROMPT_BASE = """你是 Seenful 的 L2 关联判断引擎.

你**只做语义判断**: 这几张照片放在一起在讲什么共同的事?

严格约束:
1. 你不输出 final score 数值
2. 你不输出 display_decision
3. confidence_adjustment 必须在 -0.1 到 +0.1
4. evidence 必须基于真实可见信号 (不能脑补)
5. proposed_strength 必须在真值表给定的 bounds 内
6. people 类型 P0 阶段最高 medium (不可 strong)

返回严格的 JSON, 不要 markdown 包裹, 不要解释."""


_USER_PROMPT_TEMPLATE = """## 照片列表 ({n_photos} 张)
{photos_block}

## 客观特征 (代码算)
{features_block}

## 真值表命中
- pattern: {matched_pattern}
- type: {type}
- bounds: [{bounds_min}, {bounds_max}]

## 你的任务
在 bounds 区间内给出语义判断, 严格 JSON 返回:
{{
  "proposed_type": "location | temporal | event | thematic | people | mixed | weak",
  "proposed_strength": "strong | medium | weak | none",
  "semantic_reason": "30 字以内核心理由",
  "evidence": [
    {{"photo_id": "p1", "evidence": "这两张为什么并入"}}
  ],
  "counter_evidence": "string | null",
  "confidence_adjustment": 0.0
}}"""


def _build_user_prompt(
    photos: list[L1Output],
    features: FeaturePackage,
    bands: Bands,
    truth_table: TruthTableMatch,
) -> str:
    photos_block = "\n".join([
        f"- {p.photo_id}: {p.individual_title} / 主题 {p.theme_tags} / "
        f"event {p.semantic_facts.event_hint} / tone {p.emotional_tone}"
        for p in photos
    ])
    features_block = (
        f"- 7 维 bands: location={bands.location} time={bands.time} "
        f"event={bands.event} theme={bands.theme} people={bands.people} "
        f"anchor={bands.anchor} emotional={bands.emotional}\n"
        f"- 高频地点: {features.is_high_frequency_place}\n"
        f"- 照片数: {features.photo_count}"
    )
    return _USER_PROMPT_TEMPLATE.format(
        n_photos=len(photos),
        photos_block=photos_block,
        features_block=features_block,
        matched_pattern=truth_table.matched_pattern,
        type=truth_table.type,
        bounds_min=truth_table.bounds_min,
        bounds_max=truth_table.bounds_max,
    )


# ═══════════════════════════════════════════════════════════════
# DashScope HTTP 调用 (OpenAI-compatible)
# ═══════════════════════════════════════════════════════════════

def _call_dashscope(
    system_prompt: str,
    user_prompt: str,
    cfg: dict,
) -> str:
    """调用 DashScope API, 返回 LLM 文本输出."""
    api_key_env = cfg.get("api_key_env", "DASHSCOPE_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"missing env var {api_key_env}. "
            f"set: export {api_key_env}=sk-xxx"
        )

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(cfg.get("temperature", 0.0)),
        "top_p": float(cfg.get("top_p", 1.0)),
        "seed": int(cfg.get("seed", 42)),
        "max_tokens": int(cfg.get("max_tokens", 1024)),
        "stream": False,
    }
    # Qwen3 no-thinking
    if cfg.get("enable_thinking") is False:
        payload["enable_thinking"] = False

    url = cfg["endpoint"].rstrip("/") + "/chat/completions"
    timeout = float(cfg.get("timeout_s", 30))
    retry_max = int(cfg.get("retry_max", 2))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_err: Exception | None = None
    for attempt in range(retry_max + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"),
                headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                obj = json.loads(body)
                return obj["choices"][0]["message"]["content"]
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            last_err = e
            if attempt < retry_max:
                time.sleep(1 * (attempt + 1))
                continue
    raise RuntimeError(f"DashScope failed after {retry_max + 1} attempts: {last_err}")


def _parse_judgement(
    response_text: str,
    truth_table: TruthTableMatch,
) -> LLMJudgement:
    """解析 LLM JSON 输出, 容错 + clamp 到 bounds."""
    text = response_text.strip()
    # 容错: 去掉 markdown 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        if text.startswith("json"):
            text = text[4:]

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # 兜底: 找 JSON 子串
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            obj = json.loads(text[start:end + 1])
        else:
            raise ValueError(f"cannot parse LLM JSON: {text[:200]}")

    # 解析 evidence
    evidence: list[EvidenceItem] = []
    for e in obj.get("evidence", [])[:5]:
        if isinstance(e, dict) and "photo_id" in e and "evidence" in e:
            evidence.append(EvidenceItem(
                photo_id=str(e["photo_id"]),
                evidence=str(e["evidence"])[:200],
            ))

    # clamp confidence_adjustment 到 [-0.1, 0.1]
    ca = float(obj.get("confidence_adjustment", 0.0))
    ca = max(-0.1, min(0.1, ca))

    proposed_strength = obj.get("proposed_strength", _BOUNDS_TO_BAND[truth_table.bounds_min])
    if proposed_strength not in ("strong", "medium", "weak", "none"):
        proposed_strength = _BOUNDS_TO_BAND[truth_table.bounds_min]

    proposed_type = obj.get("proposed_type", truth_table.type)

    return LLMJudgement(
        proposed_type=proposed_type,
        proposed_strength=proposed_strength,
        semantic_reason=str(obj.get("semantic_reason", "qwen"))[:100],
        evidence=evidence,
        counter_evidence=(str(obj["counter_evidence"])[:200]
                          if obj.get("counter_evidence") else "Qwen 未给反证"),
        confidence_adjustment=ca,
        is_mock=False,
    )


# ═══════════════════════════════════════════════════════════════
# QwenJudge (path B 主)
# ═══════════════════════════════════════════════════════════════

class QwenJudge:
    """ADR-0020: 接 DashScope qwen-turbo (no-thinking, temperature=0)."""

    def __init__(self):
        cfg = load_config("llm_settings.yaml")
        self._cfg = cfg.get("qwen", {})
        self._degrade = bool(self._cfg.get("graceful_degrade_to_mock", True))

    def judge(
        self,
        photos: list[L1Output],
        features: FeaturePackage,
        bands: Bands,
        truth_table: TruthTableMatch,
    ) -> LLMJudgement:
        user_prompt = _build_user_prompt(photos, features, bands, truth_table)
        try:
            response = _call_dashscope(_SYSTEM_PROMPT_BASE, user_prompt, self._cfg)
            return _parse_judgement(response, truth_table)
        except Exception as e:
            if self._degrade:
                # 失败退回 mock
                from .judge import MockJudge
                fallback = MockJudge().judge(photos, features, bands, truth_table)
                fallback.semantic_reason = f"qwen_failed_mock_fallback: {str(e)[:50]}"
                return fallback
            raise
