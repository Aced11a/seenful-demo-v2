"""backfill_engine 封顶规则单测."""
from __future__ import annotations

from datetime import datetime, timezone

from src.contracts import L1Output, LLMJudgement, TruthTableMatch
from src.policy.backfill_engine import apply_backfill_caps


def mk_photo(pid: str) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )


def mk_tt(pattern: str = "A3", bmax: str = "strong") -> TruthTableMatch:
    return TruthTableMatch(
        matched_pattern=pattern, type="event",
        bounds_min="medium", bounds_max=bmax,  # type: ignore[arg-type]
    )


def mk_llm(strength: str = "strong") -> LLMJudgement:
    return LLMJudgement(
        proposed_type="event", proposed_strength=strength,  # type: ignore[arg-type]
        semantic_reason="mock", counter_evidence="", is_mock=True,
    )


class TestBackfillCaps:
    def test_happy_path_creates_album(self):
        new = mk_photo("new")
        recalled = [mk_photo(f"r{i}") for i in range(3)]
        result = apply_backfill_caps(new, recalled, mk_tt(), mk_llm())
        assert result.decision.decision_tier == "create_new_album"
        assert len(result.decision.recalled_photo_ids) == 3
        assert all(c.passed for c in result.caps)

    def test_insufficient_recall_blocks(self):
        new = mk_photo("new")
        recalled = [mk_photo("r1")]  # < 2
        result = apply_backfill_caps(new, recalled, mk_tt(), mk_llm())
        assert result.decision.decision_tier == "insufficient_candidates"

    def test_bounds_max_not_strong_blocks(self):
        new = mk_photo("new")
        recalled = [mk_photo(f"r{i}") for i in range(2)]
        result = apply_backfill_caps(
            new, recalled,
            mk_tt(pattern="C1", bmax="medium"),
            mk_llm(),
        )
        assert result.decision.decision_tier == "no_backfill"

    def test_llm_strength_not_strong_blocks(self):
        new = mk_photo("new")
        recalled = [mk_photo(f"r{i}") for i in range(2)]
        result = apply_backfill_caps(new, recalled, mk_tt(), mk_llm("medium"))
        assert result.decision.decision_tier == "no_backfill"

    def test_max_recall_caps_at_4(self):
        new = mk_photo("new")
        recalled = [mk_photo(f"r{i}") for i in range(6)]  # 6 张, 应被裁到 4
        result = apply_backfill_caps(new, recalled, mk_tt(), mk_llm())
        assert result.decision.decision_tier == "create_new_album"
        assert len(result.decision.recalled_photo_ids) == 4

    def test_no_truth_table_match_blocks(self):
        new = mk_photo("new")
        recalled = [mk_photo(f"r{i}") for i in range(2)]
        result = apply_backfill_caps(new, recalled, None, mk_llm())
        assert result.decision.decision_tier == "no_backfill"

    def test_no_llm_blocks(self):
        new = mk_photo("new")
        recalled = [mk_photo(f"r{i}") for i in range(2)]
        result = apply_backfill_caps(new, recalled, mk_tt(), None)
        assert result.decision.decision_tier == "no_backfill"
