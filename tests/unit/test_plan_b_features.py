"""ADR-0018: Plan B (L2 1.0) 7 维度 v1.3 §3.2 抄本单测.

验证:
  · 各维度 score 范围 + 算法正确
  · scene_type 子信号设 0 (schema 适配)
  · emotional neutral bug 保留 (5 张 neutral 字面一致 → 0.8 strong)
  · plan A vs plan B 同输入差异演示
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.contracts import L1Output
from src.contracts.l1_output import ImageFacts, SafetyFlags, SemanticFacts
from src.features.assemble import assemble_features
from src.features.plan_b import (
    compute_anchor_score_legacy,
    compute_emotional_score_legacy,
    compute_event_score_legacy,
    compute_location_score_legacy,
    compute_theme_score_legacy,
    compute_time_score_legacy,
)


NOW = datetime(2026, 5, 10, tzinfo=timezone.utc)


def mk(
    pid: str,
    captured: datetime = NOW,
    gps: tuple[float, float] | None = (30.28, 120.16),
    theme: list[str] | None = None,
    event: str = "outing",
    sensitive: str = "none",
    emotional_tone: str = "calm",
    main_subjects: list[str] | None = None,
    meaning_anchors: list[str] | None = None,
) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=captured,
        theme_tags=theme if theme is not None else ["sunset"],
        # meaning_anchors + emotional_tone 在 L1Output 直接挂载
        meaning_anchors=meaning_anchors or [],
        emotional_tone=emotional_tone,
        image_facts=ImageFacts(exif_location=gps) if gps else ImageFacts(),
        safety_flags=SafetyFlags(sensitive_level=sensitive),  # type: ignore[arg-type]
        semantic_facts=SemanticFacts(
            event_hint=event,  # type: ignore[arg-type]
            main_subjects=main_subjects or [],
        ),
    )


# ═════════════════════════════════════════════════════════════════
# location (v1.3 §3.2.1)
# ═════════════════════════════════════════════════════════════════

class TestPlanBLocation:
    def test_within_200m_score_1(self):
        photos = [
            mk("p1", gps=(30.28, 120.16)),
            mk("p2", gps=(30.281, 120.161)),  # ~140m
        ]
        score, diag = compute_location_score_legacy(photos)
        assert score == 1.0
        assert diag["max_distance_m"] < 200

    def test_within_500m_score_08(self):
        photos = [
            mk("p1", gps=(30.28, 120.16)),
            mk("p2", gps=(30.282, 120.162)),  # ~280m
        ]
        score, _ = compute_location_score_legacy(photos)
        assert score == 0.8

    def test_within_2km_score_05(self):
        photos = [
            mk("p1", gps=(30.28, 120.16)),
            mk("p2", gps=(30.29, 120.17)),  # ~1.4km
        ]
        score, _ = compute_location_score_legacy(photos)
        assert score == 0.5

    def test_over_2km_score_01(self):
        photos = [
            mk("p1", gps=(30.28, 120.16)),
            mk("p2", gps=(30.32, 120.20)),  # ~5km
        ]
        score, _ = compute_location_score_legacy(photos)
        assert score == 0.1

    def test_missing_gps_score_0(self):
        photos = [mk("p1", gps=None), mk("p2", gps=(30.28, 120.16))]
        score, _ = compute_location_score_legacy(photos)
        assert score == 0.0


# ═════════════════════════════════════════════════════════════════
# time (v1.3 §3.2.2)
# ═════════════════════════════════════════════════════════════════

class TestPlanBTime:
    def test_30min_score_1(self):
        photos = [mk("p1", NOW), mk("p2", NOW + timedelta(minutes=20))]
        score, _ = compute_time_score_legacy(photos)
        assert score == 1.0

    def test_2h_score_09(self):
        photos = [mk("p1", NOW), mk("p2", NOW + timedelta(hours=1))]
        score, _ = compute_time_score_legacy(photos)
        assert score == 0.9

    def test_12h_score_07(self):
        photos = [mk("p1", NOW), mk("p2", NOW + timedelta(hours=6))]
        score, _ = compute_time_score_legacy(photos)
        assert score == 0.7

    def test_48h_score_05(self):
        photos = [mk("p1", NOW), mk("p2", NOW + timedelta(hours=24))]
        score, _ = compute_time_score_legacy(photos)
        assert score == 0.5

    def test_over_48h_score_02(self):
        photos = [mk("p1", NOW), mk("p2", NOW + timedelta(hours=60))]
        score, _ = compute_time_score_legacy(photos)
        assert score == 0.2


# ═════════════════════════════════════════════════════════════════
# theme (v1.3 §3.2.3, scene_type=0 适配)
# ═════════════════════════════════════════════════════════════════

class TestPlanBTheme:
    def test_full_theme_tags_overlap(self):
        photos = [
            mk("p1", theme=["sunset", "lake"], main_subjects=["sky"]),
            mk("p2", theme=["sunset", "lake"], main_subjects=["sky"]),
        ]
        score, diag = compute_theme_score_legacy(photos)
        # 0.5×1.0 + 0.4×1.0 + 0.1×0 = 0.9
        assert score == 0.9
        assert diag["scene_consistent"] is False
        assert "scene_type_adapter" in diag

    def test_partial_overlap(self):
        photos = [
            mk("p1", theme=["sunset", "lake"]),
            mk("p2", theme=["sunset", "bridge"]),
        ]
        score, _ = compute_theme_score_legacy(photos)
        # tag_jaccard = 1/3, subject_jaccard = 0 → 0.5×0.333 + 0 = 0.167
        assert 0.15 < score < 0.20

    def test_no_overlap(self):
        photos = [
            mk("p1", theme=["sunset"]),
            mk("p2", theme=["meal"]),
        ]
        score, _ = compute_theme_score_legacy(photos)
        assert score == 0.0

    def test_scene_type_field_does_not_break(self):
        """ADR-0018 schema 适配: scene_type 字段已删, plan B 不应崩."""
        photos = [mk("p1", theme=["a"]), mk("p2", theme=["b"])]
        # 不会抛 AttributeError
        score, diag = compute_theme_score_legacy(photos)
        assert isinstance(score, float)
        assert diag["scene_consistent"] is False


# ═════════════════════════════════════════════════════════════════
# event (v1.3 §3.2.5)
# ═════════════════════════════════════════════════════════════════

class TestPlanBEvent:
    def test_event_consistent_09(self):
        photos = [mk("p1", event="outing"), mk("p2", event="outing")]
        score, _ = compute_event_score_legacy(photos)
        assert score == 0.9

    def test_event_unknown_excludes(self):
        photos = [mk("p1", event="unknown"), mk("p2", event="unknown")]
        score, _ = compute_event_score_legacy(photos)
        assert score == 0.0

    def test_event_mixed_score_0(self):
        photos = [mk("p1", event="outing"), mk("p2", event="meal")]
        score, _ = compute_event_score_legacy(photos)
        assert score == 0.0


# ═════════════════════════════════════════════════════════════════
# anchor (v1.3 §3.2.4)
# ═════════════════════════════════════════════════════════════════

class TestPlanBAnchor:
    def test_meaning_overlap_max(self):
        photos = [
            mk("p1", meaning_anchors=["nostalgia", "family"]),
            mk("p2", meaning_anchors=["nostalgia"]),
        ]
        score, diag = compute_anchor_score_legacy(photos)
        # meaning_jaccard = 1/2
        assert score == 0.5

    def test_no_anchors_score_0(self):
        photos = [mk("p1"), mk("p2")]
        score, _ = compute_anchor_score_legacy(photos)
        assert score == 0.0


# ═════════════════════════════════════════════════════════════════
# emotional (v1.3 §3.2.6, 保留 neutral bug)
# ═════════════════════════════════════════════════════════════════

class TestPlanBEmotional:
    def test_all_same_tone_score_08(self):
        photos = [mk("p1", emotional_tone="calm"), mk("p2", emotional_tone="calm")]
        score, _ = compute_emotional_score_legacy(photos)
        assert score == 0.8

    def test_neutral_bug_preserved(self):
        """⚠ ADR-0018 拍板保留 v1.3 bug: 5 张 neutral 字面一致 → 0.8 strong.

        L2 2.0 (ADR-0015) 用 EM.0 preempt 强制 cap weak, 修了这个 bug.
        L2 1.0 (plan B) 必须保留, 真实展示 v1.3 弱点.
        """
        photos = [mk(f"p{i}", emotional_tone="neutral") for i in range(5)]
        score, diag = compute_emotional_score_legacy(photos)
        assert score == 0.8        # bug 保留, 没 cap weak
        assert diag["neutral_bug_active"] is True

    def test_two_tones_score_04(self):
        photos = [mk("p1", emotional_tone="calm"), mk("p2", emotional_tone="joyful")]
        score, _ = compute_emotional_score_legacy(photos)
        assert score == 0.4

    def test_three_tones_score_0(self):
        photos = [
            mk("p1", emotional_tone="calm"),
            mk("p2", emotional_tone="joyful"),
            mk("p3", emotional_tone="melancholic"),
        ]
        score, _ = compute_emotional_score_legacy(photos)
        assert score == 0.0


# ═════════════════════════════════════════════════════════════════
# Plan A vs Plan B 端到端对比 (assemble_features)
# ═════════════════════════════════════════════════════════════════

class TestPlanABCompare:
    def test_plan_attribute_set_correctly(self):
        """FeaturePackage.plan 字段正确反映版本."""
        photos = [mk("p1"), mk("p2"), mk("p3")]

        fp_a = assemble_features(photos, plan="L2_2.0")
        assert fp_a.plan == "L2_2.0"
        assert fp_a.location is not None    # 子 Feature 填充

        fp_b = assemble_features(photos, plan="L2_1.0")
        assert fp_b.plan == "L2_1.0"
        assert fp_b.location is None        # 子 Feature 全 None
        assert fp_b.time is None
        assert fp_b.theme is None
        assert fp_b.event is None
        assert fp_b.anchor is None
        assert fp_b.emotional is None

    def test_default_plan_is_l2_2_0(self):
        """不指定 plan 默认走 L2_2.0 (向后兼容)."""
        photos = [mk("p1"), mk("p2"), mk("p3")]
        fp = assemble_features(photos)
        assert fp.plan == "L2_2.0"
