"""Policy Engine clamp + 后置硬规则单测."""
from __future__ import annotations

import pytest

from src.contracts import (
    Bands,
    FeaturePackage,
    LLMJudgement,
    TruthTableMatch,
)
from src.policy.engine import run_post_truth_table


def make_features(
    location_score=0.9, time_score=0.9, theme_score=0.6,
    event_score=0.0, people_score=0.0, anchor_score=0.5,
    emotional_score=0.6, is_hfp=False,
) -> FeaturePackage:
    return FeaturePackage(
        location_score=location_score, time_score=time_score,
        theme_score=theme_score, event_score=event_score,
        people_score=people_score, anchor_score=anchor_score,
        emotional_score=emotional_score, is_high_frequency_place=is_hfp,
        photo_count=3,
    )


def make_bands(**kwargs) -> Bands:
    defaults = dict(location="strong", time="strong", theme="medium",
                    event="none", people="none", anchor="weak", emotional="medium")
    defaults.update(kwargs)
    return Bands(**defaults)


def make_tt(pat="A1", t="location", bmin="medium", bmax="strong") -> TruthTableMatch:
    return TruthTableMatch(matched_pattern=pat, type=t, bounds_min=bmin, bounds_max=bmax)


def make_llm(strength="strong", proposed_type="location") -> LLMJudgement:
    return LLMJudgement(
        proposed_type=proposed_type,
        proposed_strength=strength,
        semantic_reason="test",
        evidence=[],
        counter_evidence="test",
        is_mock=True,
    )


class TestClamp:
    def test_no_clamp_when_in_bounds(self):
        draft = run_post_truth_table(
            make_features(), make_bands(), make_tt(), make_llm("strong"),
        )
        assert draft.final_strength == "strong"
        assert len(draft.policy_overrides) == 0
        assert draft.display_decision == "show_mini_album"

    def test_clamp_up_when_below_min(self):
        # bounds=[medium, strong], LLM 输出 weak → clamp 到 medium
        draft = run_post_truth_table(
            make_features(), make_bands(), make_tt(bmin="medium", bmax="strong"),
            make_llm("weak"),
        )
        assert draft.final_strength == "medium"
        assert any(o.rule_id == "STAGE5_CLAMP" for o in draft.policy_overrides)

    def test_clamp_down_when_above_max(self):
        # bounds=[light, medium], LLM strong → clamp 到 medium
        draft = run_post_truth_table(
            make_features(),
            make_bands(),
            make_tt(pat="C1", bmin="light", bmax="medium"),
            make_llm("strong"),
        )
        assert draft.final_strength == "medium"
        assert any(o.rule_id == "STAGE5_CLAMP" for o in draft.policy_overrides)


class TestF1Suppress:
    def test_f1_directly_suppress(self):
        draft = run_post_truth_table(
            make_features(),
            make_bands(location="none", theme="none", event="none", people="none"),
            make_tt(pat="F1", t="weak", bmin="none", bmax="none"),
            llm=None,
        )
        assert draft.display_decision == "suppress"
        assert draft.decision_source == "truth_table_f1_suppress"


class TestHighFrequencyPlaceCap:
    def test_hfp_no_theme_event_caps_to_medium(self):
        # 高频地点 + 仅靠 location + 无 theme/event 中以上 → 强制 <= medium
        draft = run_post_truth_table(
            make_features(is_hfp=True, theme_score=0.1, event_score=0.0),
            make_bands(location="strong", theme="none", event="none"),
            make_tt(pat="A1"),
            make_llm("strong"),
        )
        assert draft.final_strength == "medium"
        assert any(o.rule_id == "HR-POST-03" for o in draft.policy_overrides)

    def test_hfp_with_theme_no_cap(self):
        # 有 theme=medium 叠加 → 允许 strong
        draft = run_post_truth_table(
            make_features(is_hfp=True),
            make_bands(location="strong", theme="medium"),
            make_tt(pat="A1"),
            make_llm("strong"),
        )
        assert draft.final_strength == "strong"


class TestDisplayDecisionMapping:
    @pytest.mark.parametrize("strength,expected", [
        ("strong", "show_mini_album"),
        ("medium", "show_mini_album"),
        ("weak", "show_inline_hint"),
        ("none", "suppress"),
    ])
    def test_strength_to_display(self, strength, expected):
        # 走 C1 (bounds=[light, medium]),不会因 clamp 干扰
        # bounds_min=light → BandLevel weak; bounds_max=medium
        # 测试时直接构造允许 medium 的 bounds
        draft = run_post_truth_table(
            make_features(),
            make_bands(location="medium", theme="none", event="none", anchor="medium"),
            make_tt(pat="C1", bmin="light", bmax="medium"),
            make_llm(strength=strength if strength in ("medium", "weak") else "medium"),
        )
        # 这个测试我们关心 _display_from_strength 的逻辑
        from src.policy.engine import _display_from_strength
        assert _display_from_strength(strength) == expected
