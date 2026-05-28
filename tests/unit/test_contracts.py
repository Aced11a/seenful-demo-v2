"""契约层 pydantic 实例化冒烟测试.

参考: ADR-0010 + ADR-0011, docs/02_data_contracts.md, docs/16_path_b_location.md, docs/17_path_b_time.md
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.contracts import (
    FeaturePackage,
    LocationFeature,
    LocationShape,
    TimeFeature,
    TimeShape,
    ThemeFeature,
    ThemeShape,
)


class TestLocationShape:
    def test_enum_values(self):
        assert LocationShape.COMPACT.value == "compact"
        assert LocationShape.LINEAR.value == "linear"
        assert LocationShape.LINEAR_CURVED.value == "linear_curved"
        assert LocationShape.LOOP.value == "loop"
        assert LocationShape.U_SHAPE.value == "u_shape"
        assert LocationShape.MULTI_CLOSE.value == "multi_close"
        assert LocationShape.MULTI_FAR.value == "multi_far"
        assert LocationShape.SCATTERED.value == "scattered"


class TestLocationFeature:
    """ADR-0010 升级版 LocationFeature."""

    def test_k_outer_1_compact_strong(self):
        """K_outer=1 + L ≤ 0.5 → A1.4 strong (compact)."""
        lf = LocationFeature(
            band="strong",
            rule_fired="A1.4",
            score=1.0,
            cluster_count_outer=1,
            cluster_count_inner=1,
            outlier_count=0,
            outer_length_km=0.3,
            outer_width_km=0.2,
            outer_ratio=1.5,
            convex_hull_diameter_km=0.3,
            trace_length_km=0.35,
            tortuosity=1.17,
            inter_outer_gap_km=None,
            max_transit_kmh=2.0,
            shape=LocationShape.COMPACT,
        )
        assert lf.band == "strong"
        assert lf.rule_fired == "A1.4"
        assert lf.shape == LocationShape.COMPACT
        assert lf.is_high_frequency_place is False
        assert lf.primary_signal == "exif_location"

    def test_k_outer_2_multi_far_none(self):
        """K_outer=2 + gap > 2km → B.4 none (multi_far)."""
        lf = LocationFeature(
            band="none",
            rule_fired="B.4",
            score=0.15,
            cluster_count_outer=2,
            cluster_count_inner=None,
            outlier_count=0,
            outer_length_km=None,
            outer_width_km=None,
            outer_ratio=None,
            convex_hull_diameter_km=None,
            trace_length_km=None,
            tortuosity=None,
            inter_outer_gap_km=25.0,
            max_transit_kmh=30.0,
            shape=LocationShape.MULTI_FAR,
        )
        assert lf.band == "none"
        assert lf.cluster_count_inner is None

    def test_scattered_zero_clusters(self):
        """K_outer=0 全 outlier → none (scattered)."""
        lf = LocationFeature(
            band="none",
            rule_fired="K_outer_0",
            score=0.0,
            cluster_count_outer=0,
            cluster_count_inner=None,
            outlier_count=4,
            shape=LocationShape.SCATTERED,
        )
        assert lf.outlier_count == 4

    def test_score_bounds_validation(self):
        with pytest.raises(ValidationError):
            LocationFeature(
                band="strong",
                rule_fired="A1.4",
                score=1.5,                # 越界
                cluster_count_outer=1,
                outlier_count=0,
                shape=LocationShape.COMPACT,
            )

    def test_rule_fired_required(self):
        with pytest.raises(ValidationError):
            LocationFeature(
                band="strong",
                rule_fired="",            # 空字符串不允许
                score=1.0,
                cluster_count_outer=1,
                outlier_count=0,
                shape=LocationShape.COMPACT,
            )


class TestTimeFeature:
    """ADR-0011 升级: band 直出 + rule_fired + shape + 完整落痕."""

    def test_minimum_required_fields(self):
        from src.contracts import TimeShape
        tf = TimeFeature(
            band="strong",
            rule_fired="T1.1",
            score=0.9,
            unique_days_count=1,
            span_days=1,
            total_span_hours=0.5,
            shape=TimeShape.SINGLE_EVENT_DENSE,
        )
        assert tf.band == "strong"
        assert tf.rule_fired == "T1.1"
        assert tf.shape == TimeShape.SINGLE_EVENT_DENSE
        # 默认值
        assert tf.fallback_count == 0
        assert tf.confidence == 1.0
        assert tf.near_eps_boundary_count == 0
        assert tf.has_overnight_chain is False

    def test_overnight_payload(self):
        from src.contracts import TimeShape
        tf = TimeFeature(
            band="strong",
            rule_fired="T2.1",
            score=0.9,
            unique_days_count=2,
            span_days=2,
            total_span_hours=13.0,
            has_overnight_chain=True,
            shape=TimeShape.OVERNIGHT,
        )
        assert tf.has_overnight_chain is True
        assert tf.shape == TimeShape.OVERNIGHT

    def test_full_fallback_confidence(self):
        from src.contracts import TimeShape
        tf = TimeFeature(
            band="medium",
            rule_fired="T3.1+k_days_uncertain",
            score=0.7,
            unique_days_count=5,
            span_days=5,
            total_span_hours=96.0,
            fallback_count=10,
            fallback_ratio=1.0,
            confidence=0.5,
            shape=TimeShape.SHORT_TRIP,
        )
        assert tf.confidence == 0.5
        assert "+k_days_uncertain" in tf.rule_fired


class TestThemeFeature:
    """ADR-0013 v0.3: 双层判定 (主 theme_tags + 次 main_subjects)."""

    def test_minimum_required_fields(self):
        from src.contracts import ThemeShape
        th = ThemeFeature(
            band="strong",
            rule_fired="TH.1",
            score=0.9,
            total_photos=5,
            valid_photo_count=5,
            shape=ThemeShape.FULL_COVERAGE_THEMED,
        )
        assert th.band == "strong"
        assert th.rule_fired == "TH.1"
        assert th.secondary_action == "none"
        assert th.secondary_coverage is None

    def test_with_secondary_boost(self):
        from src.contracts import ThemeShape
        th = ThemeFeature(
            band="strong",
            rule_fired="TH.2+secondary_boost",
            score=0.9,
            total_photos=5,
            valid_photo_count=5,
            primary_coverage=0.8,
            secondary_coverage=1.0,
            secondary_action="boost",
            shape=ThemeShape.DOMINANT_THEMED,
        )
        assert th.secondary_action == "boost"
        assert th.shape == ThemeShape.DOMINANT_THEMED


class TestAnchorFeature:
    """ADR-0014 v0.3: 双层判定 (主 meaning + 次 object)."""

    def test_minimum_required_fields(self):
        from src.contracts import AnchorFeature, AnchorShape
        af = AnchorFeature(
            band="strong",
            rule_fired="AN.1",
            score=0.9,
            total_photos=5,
            valid_photo_count=5,
            shape=AnchorShape.FULL_COVERAGE_ANCHORED,
        )
        assert af.band == "strong"
        assert af.rule_fired == "AN.1"
        assert af.primary_signal == "meaning_anchors"
        assert af.secondary_signal == "object_anchors"

    def test_with_secondary_demote(self):
        from src.contracts import AnchorFeature, AnchorShape
        af = AnchorFeature(
            band="weak",
            rule_fired="AN.2+secondary_demote",
            score=0.4,
            total_photos=5,
            valid_photo_count=5,
            primary_coverage=0.8,
            secondary_coverage=0.0,
            secondary_action="demote",
            shape=AnchorShape.DOMINANT_ANCHORED,
        )
        assert af.secondary_action == "demote"
        assert af.band == "weak"


class TestFeaturePackageBackcompat:
    def test_v01_scalar_fields_still_work(self):
        """v0.1 demo 现有代码不应该被打断."""
        fp = FeaturePackage(
            location_score=0.9, time_score=0.7, theme_score=0.5,
            event_score=0.6, people_score=0.4, anchor_score=0.3,
            emotional_score=0.55, photo_count=3,
        )
        assert fp.location is None
        assert fp.time is None
        assert fp.theme is None

    def test_with_adr_0010_submodels(self):
        """ADR-0010 落地后, 子模型字段同步填充."""
        fp = FeaturePackage(
            location_score=0.9, time_score=0.7, theme_score=0.5,
            event_score=0.6, people_score=0.4, anchor_score=0.3,
            emotional_score=0.55, photo_count=3,
            location=LocationFeature(
                band="strong",
                rule_fired="A1.6",
                score=0.9,
                cluster_count_outer=1,
                cluster_count_inner=1,
                outlier_count=0,
                outer_length_km=0.8,
                outer_width_km=0.4,
                outer_ratio=2.0,
                convex_hull_diameter_km=0.8,
                trace_length_km=1.0,
                tortuosity=1.25,
                max_transit_kmh=3.0,
                shape=LocationShape.COMPACT,
            ),
            time=TimeFeature(
                band="strong",
                rule_fired="T1.2",
                score=0.9,
                unique_days_count=1,
                span_days=1,
                total_span_hours=1.5,
                shape=TimeShape.SINGLE_EVENT_EXTENDED,
            ),
            theme=ThemeFeature(
                band="medium",
                rule_fired="TH.3",
                score=0.7,
                total_photos=3,
                valid_photo_count=3,
                shape=ThemeShape.PARTIAL_THEMED,
            ),
        )
        assert fp.location.band == "strong"
        assert fp.location.rule_fired == "A1.6"
        assert fp.location.shape == LocationShape.COMPACT
        assert fp.time.band == "strong"
        assert fp.time.rule_fired == "T1.2"
        assert fp.theme.band == "medium"
        assert fp.theme.rule_fired == "TH.3"
