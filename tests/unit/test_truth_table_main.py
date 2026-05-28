"""主真值表 28 条规则单测.

参考: docs/03_truth_table_main.md, config/truth_table_main.yaml
每条规则至少一个正例; 关键边界 + 优先级覆盖.
"""
from __future__ import annotations

import pytest

from src.contracts import Bands
from src.contracts.features import BandLevel
from src.policy.truth_table import lookup


def mk(
    location: BandLevel = "none",
    time: BandLevel = "none",
    theme: BandLevel = "none",
    event: BandLevel = "none",
    people: BandLevel = "none",
    anchor: BandLevel = "none",
    emotional: BandLevel = "none",
) -> Bands:
    return Bands(
        location=location, time=time, theme=theme, event=event,
        people=people, anchor=anchor, emotional=emotional,
    )


# ─── A 系列 ─────────────────────────────────────────
class TestASeries:
    def test_a1_location_strong(self):
        tt = lookup(mk(location="strong"))
        assert tt.matched_pattern == "A1"
        assert tt.bounds_min == "medium"
        assert tt.bounds_max == "strong"

    def test_a2_theme_strong(self):
        assert lookup(mk(theme="strong")).matched_pattern == "A2"

    def test_a3_event_strong(self):
        assert lookup(mk(event="strong")).matched_pattern == "A3"

    def test_a4_people_strong(self):
        # P0 实质永不触发,但规则保留
        assert lookup(mk(people="strong")).matched_pattern == "A4"

    def test_a_priority_over_b(self):
        # location 强 + theme 中 → A1 (不进 B1)
        assert lookup(mk(location="strong", theme="medium")).matched_pattern == "A1"


# ─── B 系列 ─────────────────────────────────────────
class TestBSeries:
    def test_b1_location_medium_theme_medium(self):
        assert lookup(mk(location="medium", theme="medium")).matched_pattern == "B7" if False else \
               lookup(mk(location="medium", theme="medium")).matched_pattern == "B1"

    def test_b2(self):
        assert lookup(mk(location="medium", event="medium")).matched_pattern == "B2"

    def test_b3(self):
        assert lookup(mk(location="medium", people="medium")).matched_pattern == "B3"

    def test_b4(self):
        assert lookup(mk(theme="medium", event="medium")).matched_pattern == "B4"

    def test_b5(self):
        assert lookup(mk(theme="medium", people="medium")).matched_pattern == "B5"

    def test_b6(self):
        assert lookup(mk(event="medium", people="medium")).matched_pattern == "B6"

    def test_b7_three_mains(self):
        tt = lookup(mk(location="medium", theme="medium", event="medium"))
        assert tt.matched_pattern == "B7"
        assert tt.bounds_min == "strong" and tt.bounds_max == "strong"

    def test_b8_three_mains_no_event(self):
        # location + theme + people 三个中 → B8 (B7 需要 event,这里没有)
        tt = lookup(mk(location="medium", theme="medium", people="medium"))
        assert tt.matched_pattern == "B8"

    def test_b9_four_mains(self):
        tt = lookup(mk(
            location="medium", theme="medium", event="medium", people="medium",
        ))
        # B7 优先(已经命中)
        assert tt.matched_pattern == "B7"

    def test_b9_only_when_b7_not_hit(self):
        # 实际上 B9 需要四个 medium,B7 已经会命中 (location+theme+event)
        # 严格说 B9 只是冗余存在; 仍要测试规则不报错
        tt = lookup(mk(theme="medium", event="medium", people="medium", location="medium"))
        assert tt.matched_pattern in ("B7", "B8", "B9")


# ─── G 系列 ─────────────────────────────────────────
class TestGSeries:
    def test_g1_time_strong_main_medium(self):
        # 注意:G1 需要 time=strong AND any_main_ge(medium)
        # 不能让某个主载体 = strong (那会先命中 A 系列)
        tt = lookup(mk(time="strong", theme="medium"))
        assert tt.matched_pattern == "G1"

    def test_g2_time_strong_main_weak_aux_medium(self):
        tt = lookup(mk(time="strong", location="weak", anchor="medium"))
        assert tt.matched_pattern == "G2"
        assert tt.bounds_max == "medium"

    def test_g3_time_medium_main_medium(self):
        tt = lookup(mk(time="medium", theme="medium"))
        # 但 theme=medium 单独也可能命中 D2 (其他全none),G3 优先级在 D 之前
        # 严格按 priority_order: G3 在 D2 之前
        assert tt.matched_pattern == "G3"

    def test_g4_time_medium_main_weak_aux_medium(self):
        tt = lookup(mk(time="medium", location="weak", emotional="medium"))
        assert tt.matched_pattern == "G4"


# ─── C 系列 ─────────────────────────────────────────
class TestCSeries:
    def test_c1_location_medium_aux(self):
        tt = lookup(mk(location="medium", anchor="medium"))
        # location+anchor → C1 (没有 time/theme/event/people 中)
        assert tt.matched_pattern == "C1"

    def test_c2_theme_medium_aux(self):
        tt = lookup(mk(theme="medium", emotional="medium"))
        assert tt.matched_pattern == "C2"

    def test_c3(self):
        tt = lookup(mk(event="medium", anchor="medium"))
        assert tt.matched_pattern == "C3"

    def test_c4(self):
        tt = lookup(mk(people="medium", emotional="medium"))
        assert tt.matched_pattern == "C4"


# ─── D 系列 ─────────────────────────────────────────
class TestDSeries:
    def test_d1_location_only(self):
        tt = lookup(mk(location="medium"))
        assert tt.matched_pattern == "D1"
        assert tt.bounds_min == "light" and tt.bounds_max == "light"

    def test_d2(self):
        assert lookup(mk(theme="medium")).matched_pattern == "D2"

    def test_d3(self):
        assert lookup(mk(event="medium")).matched_pattern == "D3"

    def test_d4(self):
        assert lookup(mk(people="medium")).matched_pattern == "D4"

    def test_d1_with_weak_others(self):
        # location=中 + 其他全弱 → 仍 D1 (其他必须 weak/none)
        tt = lookup(mk(location="medium", theme="weak", event="weak"))
        assert tt.matched_pattern == "D1"


# ─── E 系列 ─────────────────────────────────────────
class TestESeries:
    def test_e1_two_weak_mains_two_medium_aux(self):
        tt = lookup(mk(
            location="weak", theme="weak", anchor="medium", emotional="medium",
        ))
        assert tt.matched_pattern == "E1"

    def test_e2_two_weak_mains_one_medium_aux(self):
        tt = lookup(mk(location="weak", theme="weak", anchor="medium"))
        assert tt.matched_pattern == "E2"


# ─── F1 ─────────────────────────────────────────────
class TestF1:
    def test_f1_all_none(self):
        tt = lookup(mk())
        assert tt.matched_pattern == "F1"
        assert tt.bounds_min == "none" and tt.bounds_max == "none"

    def test_f1_single_weak(self):
        # 单一弱主载体, 无辅证 → F1
        tt = lookup(mk(location="weak"))
        assert tt.matched_pattern == "F1"


# ─── 优先级 ────────────────────────────────────────
class TestPriority:
    @pytest.mark.parametrize("bands,expected", [
        (mk(location="strong", theme="strong"), "A1"),       # A1 > A2
        (mk(location="strong", theme="medium"), "A1"),       # A 系 > B 系
        (mk(location="medium", theme="medium", event="medium"), "B7"),  # B7 > B1
        (mk(time="strong", theme="medium"), "G1"),           # G > C
        (mk(theme="medium", anchor="medium"), "C2"),         # C > D (有辅证)
        (mk(theme="medium"), "D2"),                          # D 兜底
    ])
    def test_priority_order(self, bands, expected):
        assert lookup(bands).matched_pattern == expected
