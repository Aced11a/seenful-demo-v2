"""动态生长真值表 10 条规则单测.

参考: docs/04_truth_table_growth.md, config/truth_table_growth.yaml
"""
from __future__ import annotations

import pytest

from src.contracts import GrowthBands
from src.contracts.features import BandLevel
from src.policy.truth_table_growth import lookup_growth


def mk(
    location: BandLevel = "none",
    theme: BandLevel = "none",
    event: BandLevel = "none",
    anchor: BandLevel = "none",
) -> GrowthBands:
    return GrowthBands(location=location, theme=theme, event=event, anchor=anchor)


class TestGAseries:
    def test_g_a1_location_strong_with_theme(self):
        tt = lookup_growth(mk(location="strong", theme="medium"))
        assert tt.matched_pattern == "G-A1"
        assert tt.decision_tier == "auto_merge"

    def test_g_a1_location_strong_with_event(self):
        tt = lookup_growth(mk(location="strong", event="medium"))
        assert tt.matched_pattern == "G-A1"

    def test_g_a1_location_strong_with_anchor(self):
        tt = lookup_growth(mk(location="strong", anchor="medium"))
        assert tt.matched_pattern == "G-A1"

    def test_g_a2_location_strong_alone(self):
        tt = lookup_growth(mk(location="strong"))
        assert tt.matched_pattern == "G-A2"
        assert tt.decision_tier == "ask_user"


class TestGBseries:
    def test_g_b1_theme_strong(self):
        tt = lookup_growth(mk(theme="strong"))
        assert tt.matched_pattern == "G-B1"
        assert tt.decision_tier == "auto_merge"

    def test_g_b2_event_strong(self):
        tt = lookup_growth(mk(event="strong"))
        assert tt.matched_pattern == "G-B2"

    def test_g_b3_anchor_strong(self):
        tt = lookup_growth(mk(anchor="strong"))
        assert tt.matched_pattern == "G-B3"


class TestGCseries:
    def test_g_c1_location_medium_with_theme(self):
        tt = lookup_growth(mk(location="medium", theme="medium"))
        assert tt.matched_pattern == "G-C1"
        assert tt.decision_tier == "auto_merge"

    def test_g_c1_location_medium_with_event(self):
        tt = lookup_growth(mk(location="medium", event="medium"))
        assert tt.matched_pattern == "G-C1"

    def test_g_c2_location_medium_only_anchor(self):
        tt = lookup_growth(mk(location="medium", anchor="medium"))
        assert tt.matched_pattern == "G-C2"
        assert tt.decision_tier == "ask_user"


class TestGD_E_F:
    def test_g_d1_single_medium(self):
        tt = lookup_growth(mk(theme="medium"))
        assert tt.matched_pattern == "G-D1"
        assert tt.decision_tier == "ask_user"

    def test_g_e1_two_weak_mains(self):
        tt = lookup_growth(mk(location="weak", theme="weak"))
        assert tt.matched_pattern == "G-E1"
        assert tt.decision_tier == "ask_user"

    def test_g_f1_all_none(self):
        tt = lookup_growth(mk())
        assert tt.matched_pattern == "G-F1"
        assert tt.decision_tier == "no_merge"


class TestPriority:
    @pytest.mark.parametrize("bands,expected", [
        # location 强 + theme 中 → G-A1 (不退 G-B/G-C)
        (mk(location="strong", theme="medium"), "G-A1"),
        # location 强 单独 → G-A2 (G-B1 也需要 theme 强,这里 theme=none)
        (mk(location="strong"), "G-A2"),
        # theme 强 + location 中 → G-A1 (因为 location strong 优先, 但 here location=medium)
        # 实际: theme strong, location medium → 应该 G-B1 (G-A 要 location strong)
        (mk(theme="strong", location="medium"), "G-B1"),
        # G-C1 优于 G-D1
        (mk(location="medium", theme="medium"), "G-C1"),
        # anchor 在 path A 是主载体之一 (4 维含 anchor) → 单 medium → G-D1
        (mk(anchor="medium"), "G-D1"),
    ])
    def test_priority(self, bands, expected):
        assert lookup_growth(bands).matched_pattern == expected
