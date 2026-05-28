"""路径 B emotional 维度单测 (ADR-0015 v0.2 单层语义聚类).

覆盖:
  - EM.0 preempt (neutral baseline cap weak)
  - EM.1 strong (主簇非 neutral 全员一致)
  - EM.2/EM.3 medium (主簇主导)
  - EM.4 weak (散乱)
  - EM.5 none (N_valid≤1)
  - 红线落痕 (推断情绪词违规)
  - 复用 _two_tier_cluster(enable_secondary=False)

参考: docs/21_path_b_emotional.md, decisions/0015-path-b-emotional-single-tier-cluster.md
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.contracts import EmotionalShape, L1Output
from src.features.emotional import build_emotional_feature


def make_photo(pid: str, tone: str = "neutral") -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 1, 12, 0),
        emotional_tone=tone,
    )


# ─── EM.1 strong (主簇非 neutral 全员一致) ──────────────────


class TestEM1Strong:
    def test_all_same_awe(self):
        ps = [make_photo(f"p{i}", "awe") for i in range(5)]
        ef = build_emotional_feature(ps)
        assert ef.band == "strong"
        assert ef.rule_fired == "EM.1"
        assert ef.shape == EmotionalShape.UNANIMOUS_EMOTION
        assert ef.is_neutral_baseline is False
        assert ef.coverage == 1.0
        assert ef.primary_dominant_tone == "awe"

    def test_open_vocab_strong(self):
        """画面氛围开放词 (诗意), v0.2 关键: mock 表外但同字面 → 同簇."""
        ps = [make_photo(f"p{i}", "诗意") for i in range(5)]
        ef = build_emotional_feature(ps)
        # mock 表外但字面 5 张全同 → 1 cluster, hit_count=5
        assert ef.band == "strong"
        assert ef.rule_fired == "EM.1"


# ─── EM.0 preempt (neutral baseline cap weak, 核心修复) ────


class TestEM0NeutralBaseline:
    def test_all_neutral_cap_weak(self):
        """[neutral × 5] 老 0.85 strong → v0.2 weak (核心修复)."""
        ps = [make_photo(f"p{i}", "neutral") for i in range(5)]
        ef = build_emotional_feature(ps)
        assert ef.band == "weak"
        assert ef.rule_fired == "EM.0"
        assert ef.shape == EmotionalShape.NEUTRAL_BASELINE
        assert ef.is_neutral_baseline is True
        assert ef.primary_dominant_tone == "neutral"
        # coverage 仍 1.0, 但 EM.0 preempt cap
        assert ef.coverage == 1.0


# ─── EM.2 medium (0.8-1.0 主导) ──────────────────────────


class TestEM2Dominant:
    def test_4_1_majority(self):
        ps = (
            [make_photo(f"p{i}", "诗意") for i in range(4)]
            + [make_photo("p5", "喧闹")]
        )
        ef = build_emotional_feature(ps)
        # 诗意 hit_rate=0.8 → emotion_cluster
        # 喧闹 hit_count=1 < 2 → 不入
        # coverage = 4/5 = 0.8 → EM.2
        assert ef.band == "medium"
        assert ef.rule_fired == "EM.2"
        assert ef.shape == EmotionalShape.DOMINANT_EMOTION


# ─── EM.3 medium (0.5-0.8 mixed) ────────────────────────


class TestEM3Mixed:
    def test_3_2_mixed(self):
        ps = (
            [make_photo(f"p{i}", "静谧") for i in range(3)]
            + [make_photo(f"p{i}", "戏剧化") for i in range(3, 5)]
        )
        ef = build_emotional_feature(ps)
        # 静谧 hit_rate=0.6 ≥ 0.5 ✓ hit_count=3 ≥ 2 ✓
        # 戏剧化 hit_count=2 ≥ 2 ✓ hit_rate=0.4 < 0.5 ✗
        # coverage = 3/5 = 0.6 → EM.3
        assert ef.band == "medium"
        assert ef.rule_fired == "EM.3"
        assert ef.shape == EmotionalShape.MIXED_EMOTION


# ─── EM.4 weak (散乱) ──────────────────────────────────


class TestEM4Scattered:
    def test_all_different_tones(self):
        tones = ["诗意", "喧闹", "怀旧", "温馨", "极简"]
        ps = [make_photo(f"p{i}", t) for i, t in enumerate(tones)]
        ef = build_emotional_feature(ps)
        # 5 unique tones, mock 表外 → 5 独立簇, 各 hit_count=1 < 2 → 无 cluster
        # coverage = 0 → EM.4
        assert ef.band == "weak"
        assert ef.rule_fired == "EM.4"
        assert ef.shape == EmotionalShape.SCATTERED_EMOTION


# ─── EM.5 none (N_valid ≤ 1) ────────────────────────────


class TestEM5None:
    def test_empty(self):
        ef = build_emotional_feature([])
        assert ef.band == "none"
        assert ef.rule_fired == "EM.5"

    def test_single_photo(self):
        """N=1 → N_valid ≤ 1 → none (path B 红线 §3)."""
        ps = [make_photo("p1", "awe")]
        ef = build_emotional_feature(ps)
        assert ef.band == "none"


# ─── 红线诊断 (落痕不阻断) ────────────────────────────


class TestInferredEmotionDiagnostic:
    """违反红线 §1 '不做情绪推断' 落痕给上游."""

    def test_happy_5_strong_with_diagnostic(self):
        """[happy × 5] 字面 5 张全同 → 仍 EM.1 strong, 但 detected_inferred=5 落痕."""
        ps = [make_photo(f"p{i}", "happy") for i in range(5)]
        ef = build_emotional_feature(ps)
        assert ef.band == "strong"
        assert ef.detected_inferred_emotion_count == 5
        assert "happy" in ef.detected_inferred_emotions

    def test_chinese_inferred_emotion(self):
        """中文推断情绪 (开心/悲伤) 同样落痕."""
        ps = [make_photo(f"p{i}", "开心") for i in range(3)] + [
            make_photo(f"p{i}", "悲伤") for i in range(3, 5)
        ]
        ef = build_emotional_feature(ps)
        assert ef.detected_inferred_emotion_count == 5
        assert "开心" in ef.detected_inferred_emotions
        assert "悲伤" in ef.detected_inferred_emotions

    def test_no_violation_zero_count(self):
        ps = [make_photo(f"p{i}", "awe") for i in range(5)]
        ef = build_emotional_feature(ps)
        assert ef.detected_inferred_emotion_count == 0
        assert ef.detected_inferred_emotions == []


# ─── 2 张边界 ──────────────────────────────────────────


class TestTwoPhotos:
    def test_2_same_strong(self):
        ps = [make_photo("p1", "诗意"), make_photo("p2", "诗意")]
        ef = build_emotional_feature(ps)
        # 2 张全同 → hit_count=2 ≥ 2 ✓, coverage=1.0 → EM.1
        assert ef.band == "strong"

    def test_2_different_weak(self):
        ps = [make_photo("p1", "诗意"), make_photo("p2", "喧闹")]
        ef = build_emotional_feature(ps)
        # 2 簇各 hit_count=1 < 2 → 无 cluster → coverage=0 → EM.4 weak
        assert ef.band == "weak"
        assert ef.rule_fired == "EM.4"


# ─── 老 API 已删 (compute_emotional_score) ──────────────


class TestOldAPIRemoved:
    def test_compute_emotional_score_removed(self):
        from src.features import emotional as emotional_module
        assert not hasattr(emotional_module, "compute_emotional_score")
