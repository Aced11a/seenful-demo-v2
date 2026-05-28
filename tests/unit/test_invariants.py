"""ADR-0019 v0.4 invariants 单测 (CLAUDE.md 第 5 条 测试驱动收尾).

8 条产品红线 invariants 校验, 每条独立测正例 + 反例.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.test_utils.invariants import (
    ALL_INVARIANTS,
    check_invariants,
    check_inv01_weak_no_create_new_album,
    check_inv04_cascade_min_recall,
    check_inv05_cascade_strong_only,
    check_inv06_cascade_max_recall,
    check_inv07_event_weight,
    check_inv08_plan_logged,
)


def _make_backfill_log(decision_tier, recalled_ids=None, strength="strong",
                       priority_ranking=None):
    """造个 BackfillDecisionLog-like 对象."""
    fd = SimpleNamespace(
        decision_tier=decision_tier,
        recalled_photo_ids=recalled_ids or [],
        target_album_strength=strength,
    )
    return SimpleNamespace(
        final_decision=fd,
        priority_ranking=priority_ranking or [],
        feature_assembler_plan="L2_2.0",
    )


def _make_l2_log(strength, display_decision, plan="L2_2.0"):
    """造个 DecisionLog-like 对象."""
    assoc = SimpleNamespace(strength=strength, display_decision=display_decision)
    fd = SimpleNamespace(association=assoc)
    return SimpleNamespace(
        final_decision=fd,
        feature_assembler_plan=plan,
    )


class TestINV01:
    """INV-01: 弱关联绝不 create_new_album (红线 #5)."""

    def test_cascade_strong_create_album_passes(self):
        log = _make_backfill_log("create_new_album", strength="strong")
        passed, _ = check_inv01_weak_no_create_new_album(log)
        assert passed

    def test_cascade_weak_create_album_violates(self):
        log = _make_backfill_log("create_new_album", strength="weak")
        passed, msg = check_inv01_weak_no_create_new_album(log)
        assert not passed
        assert "weak" in msg.lower()

    def test_path_b_weak_show_mini_album_violates(self):
        log = _make_l2_log(strength="weak", display_decision="show_mini_album")
        passed, msg = check_inv01_weak_no_create_new_album(log)
        assert not passed


class TestINV04:
    """INV-04: cascade 召回 ≥ 2 张才能成集."""

    def test_recall_2_passes(self):
        log = _make_backfill_log("create_new_album", recalled_ids=["p1", "p2"])
        passed, _ = check_inv04_cascade_min_recall(log)
        assert passed

    def test_recall_1_violates(self):
        log = _make_backfill_log("create_new_album", recalled_ids=["p1"])
        passed, msg = check_inv04_cascade_min_recall(log)
        assert not passed
        assert "recall=1" in msg

    def test_no_backfill_skips(self):
        log = _make_backfill_log("no_backfill", recalled_ids=[])
        passed, _ = check_inv04_cascade_min_recall(log)
        assert passed


class TestINV05:
    """INV-05: cascade strong-only."""

    def test_strong_passes(self):
        log = _make_backfill_log("create_new_album", strength="strong")
        passed, _ = check_inv05_cascade_strong_only(log)
        assert passed

    def test_medium_violates(self):
        log = _make_backfill_log("create_new_album", strength="medium")
        passed, msg = check_inv05_cascade_strong_only(log)
        assert not passed
        assert "medium" in msg


class TestINV06:
    """INV-06: cascade 召回 ≤ 4 张 (ADR-0017 PRD §3.10.5)."""

    def test_recall_4_passes(self):
        log = _make_backfill_log(
            "create_new_album",
            recalled_ids=["p1", "p2", "p3", "p4"],
        )
        passed, _ = check_inv06_cascade_max_recall(log)
        assert passed

    def test_recall_5_violates(self):
        log = _make_backfill_log(
            "create_new_album",
            recalled_ids=["p1", "p2", "p3", "p4", "p5"],
        )
        passed, msg = check_inv06_cascade_max_recall(log)
        assert not passed
        assert "5" in msg


class TestINV07:
    """INV-07: event 权重 0.5 (ADR-0017 priority_weight)."""

    def test_event_only_score_05_passes(self):
        entry = SimpleNamespace(
            event_match=True, gps_within_1km=False,
            theme_jaccard_above_0_5=False, score=0.5,
        )
        log = _make_backfill_log(
            "no_backfill",
            priority_ranking=[entry],
        )
        passed, _ = check_inv07_event_weight(log)
        assert passed

    def test_event_only_wrong_score_violates(self):
        entry = SimpleNamespace(
            event_match=True, gps_within_1km=False,
            theme_jaccard_above_0_5=False, score=1.0,    # 应该 0.5 但 1.0
        )
        log = _make_backfill_log(
            "no_backfill",
            priority_ranking=[entry],
        )
        passed, msg = check_inv07_event_weight(log)
        assert not passed
        assert "score=1.0" in msg


class TestINV08:
    """INV-08: plan A/B 切换 + DecisionLog 落痕 (ADR-0018)."""

    def test_plan_L2_2_passes(self):
        log = _make_l2_log("strong", "show_mini_album", plan="L2_2.0")
        passed, _ = check_inv08_plan_logged(log)
        assert passed

    def test_plan_L2_1_passes(self):
        log = _make_l2_log("strong", "show_mini_album", plan="L2_1.0")
        passed, _ = check_inv08_plan_logged(log)
        assert passed

    def test_invalid_plan_violates(self):
        log = _make_l2_log("strong", "show_mini_album", plan="L3_5.0")
        passed, msg = check_inv08_plan_logged(log)
        assert not passed


class TestCheckInvariants:
    """check_invariants() 整体入口."""

    def test_all_passes_returns_empty(self):
        log = _make_backfill_log("create_new_album",
                                 recalled_ids=["p1", "p2", "p3"], strength="strong")
        violations = check_invariants(log)
        assert violations == []

    def test_only_filter_works(self):
        log = _make_backfill_log("create_new_album",
                                 recalled_ids=["p1"], strength="strong")
        # 全跑会触发 INV-04
        all_v = check_invariants(log)
        assert any("INV-04" in v for v in all_v)
        # 只跑 INV-05 不触发
        only_v = check_invariants(log, only=["INV-05"])
        assert only_v == []

    def test_all_invariants_registered(self):
        """8 条 invariants 都在 ALL_INVARIANTS 注册."""
        assert len(ALL_INVARIANTS) == 8
        for i in range(1, 9):
            inv_id = f"INV-0{i}"
            assert inv_id in ALL_INVARIANTS
