"""三路仲裁器单测 (4 个 case + 策略 3 禁用 + ask_user)."""
from __future__ import annotations

from datetime import datetime, timezone

from src.arbitration.merge_results import arbitrate
from src.contracts import (
    Association,
    AssociationDecision,
    BackfillDecision,
    BackfillDecisionLog,
    DecisionLog,
    GrowthDecision,
    GrowthDecisionLog,
)


def make_growth(tier: str, target: str = "ma_x") -> GrowthDecisionLog:
    return GrowthDecisionLog(
        decision_id="d1", new_photo_id="p_new",
        candidate_album_ids=[target],
        per_album_evaluations=[],
        final_decision=GrowthDecision(
            growth_decision_id="gd1",
            new_photo_id="p_new",
            decision_tier=tier,  # type: ignore[arg-type]
            merge_target_album_id=target,
            primary_signal="exif_location",
            reason="test",
        ),
    )


def make_l2(display: str = "show_mini_album") -> DecisionLog:
    return DecisionLog(
        decision_id="d2",
        path_taken="path_B",
        stages={},
        decision_source="policy_engine_with_llm_support",
        final_decision=AssociationDecision(
            association_id="a1",
            photo_ids=["p_new"],
            association=Association(
                score=0.7, type="location", strength="medium",
                primary_signal="exif_location", reason="t",
                display_decision=display,  # type: ignore[arg-type]
            ),
            decision_source="policy_engine_with_llm_support",
        ),
    )


def make_backfill(tier: str = "create_new_album") -> BackfillDecisionLog:
    return BackfillDecisionLog(
        decision_id="d3",
        new_photo_id="p_new",
        coarse_filter_candidates=["r1", "r2"],
        final_decision=BackfillDecision(
            backfill_decision_id="bd1",
            new_photo_id="p_new",
            decision_tier=tier,  # type: ignore[arg-type]
            recalled_photo_ids=["r1", "r2"],
            target_album_strength="strong",
            primary_signal="event_hint",
            reason="t",
        ),
    )


class TestArbitration:
    def test_case_1_auto_merge_wins(self):
        result = arbitrate(
            make_growth("auto_merge", "ma_lakeside"),
            make_l2("show_mini_album"),
            make_backfill("create_new_album"),
        )
        assert result.arbitration_winner == "path_A"
        assert result.ending == "add_to_existing_album"
        assert result.target_album_id == "ma_lakeside"
        assert "path_B" in result.discarded_paths
        assert "path_C" in result.discarded_paths
        assert result.case_matched == "Case 1"

    def test_case_1_ask_user(self):
        result = arbitrate(make_growth("ask_user"), None, None)
        assert result.arbitration_winner == "path_A"
        assert result.ending == "ask_user_confirm"

    def test_case_2_no_growth_l2_wins(self):
        result = arbitrate(
            make_growth("no_merge"),
            make_l2("show_mini_album"),
            make_backfill("create_new_album"),
        )
        assert result.arbitration_winner == "path_B"
        assert result.ending == "create_new_album_path_b"
        assert "path_C" in result.discarded_paths
        assert result.case_matched == "Case 2"

    def test_case_2_no_growth_at_all(self):
        result = arbitrate(None, make_l2("show_mini_album"), None)
        assert result.arbitration_winner == "path_B"

    def test_case_3_only_backfill_wins(self):
        result = arbitrate(
            make_growth("no_merge"),
            make_l2("suppress"),
            make_backfill("create_new_album"),
        )
        assert result.arbitration_winner == "path_C"
        assert result.ending == "create_new_album_backfill"
        assert result.case_matched == "Case 3"

    def test_case_3_no_l2(self):
        result = arbitrate(None, None, make_backfill("create_new_album"))
        assert result.arbitration_winner == "path_C"

    def test_case_4_all_empty(self):
        result = arbitrate(None, None, None)
        assert result.arbitration_winner == "none"
        assert result.ending == "single_photo_sediment"
        assert result.case_matched == "Case 4"

    def test_case_4_all_negative(self):
        result = arbitrate(
            make_growth("no_merge"),
            make_l2("suppress"),
            make_backfill("no_backfill"),
        )
        assert result.arbitration_winner == "none"
        assert result.ending == "single_photo_sediment"

    def test_strategy_3_disabled_backfill_discarded_when_a_hits(self):
        """A 命中时, C 即使 create_new_album 也作废 (策略 3 禁用)."""
        result = arbitrate(
            make_growth("auto_merge"),
            None,
            make_backfill("create_new_album"),
        )
        assert "path_C" in result.discarded_paths
