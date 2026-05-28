"""backfill_scan 候选筛选 + 粗筛 单测."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.candidate_builder.backfill_scan import filter_backfill_candidates
from src.contracts import L1Output
from src.contracts.l1_output import ImageFacts, SafetyFlags, SemanticFacts


def mk(
    pid: str,
    captured: datetime,
    gps: tuple[float, float] | None = (30.28, 120.16),
    theme: list[str] | None = None,
    event: str = "outing",
    sensitive: str = "none",
) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=captured,
        theme_tags=theme if theme is not None else ["sunset"],
        image_facts=ImageFacts(exif_location=gps) if gps else ImageFacts(),
        safety_flags=SafetyFlags(sensitive_level=sensitive),  # type: ignore[arg-type]
        semantic_facts=SemanticFacts(event_hint=event),  # type: ignore[arg-type]
    )


NOW = datetime(2026, 5, 10, tzinfo=timezone.utc)


class TestBackfillScan:
    def test_gps_within_1km_passes(self):
        new = mk("new", NOW, gps=(30.28, 120.16))
        pool = [mk("p1", NOW - timedelta(days=5), gps=(30.281, 120.161))]
        assert {p.photo_id for p in filter_backfill_candidates(new, pool)} == {"p1"}

    def test_gps_over_1km_fails(self):
        new = mk("new", NOW, gps=(30.28, 120.16))
        pool = [mk("p1", NOW - timedelta(days=5), gps=(30.32, 120.20), theme=["x"], event="meal")]
        assert filter_backfill_candidates(new, pool) == []

    def test_theme_jaccard_above_threshold(self):
        new = mk("new", NOW, gps=None, theme=["sunset", "city"])
        pool = [mk("p1", NOW - timedelta(days=5), gps=None,
                   theme=["sunset", "city", "rooftop"], event="meal")]
        # jaccard {sunset,city} ∩ ... = 2/3 > 0.5 → 命中
        assert {p.photo_id for p in filter_backfill_candidates(new, pool)} == {"p1"}

    def test_event_match(self):
        new = mk("new", NOW, gps=None, theme=["a"], event="outing")
        pool = [mk("p1", NOW - timedelta(days=5), gps=None, theme=["b"], event="outing")]
        assert {p.photo_id for p in filter_backfill_candidates(new, pool)} == {"p1"}

    def test_lookback_30_days_cutoff(self):
        new = mk("new", NOW)
        pool = [mk("p_old", NOW - timedelta(days=40))]
        assert filter_backfill_candidates(new, pool) == []

    def test_sensitive_blocks_all(self):
        new = mk("new", NOW, sensitive="medium")
        pool = [mk("p1", NOW - timedelta(days=5))]
        assert filter_backfill_candidates(new, pool) == []

    def test_already_in_album_skipped(self):
        new = mk("new", NOW)
        pool = [mk("p1", NOW - timedelta(days=5))]
        assert filter_backfill_candidates(
            new, pool, already_in_album_ids={"p1"}
        ) == []

    def test_global_excluded_skipped(self):
        new = mk("new", NOW)
        pool = [mk("p1", NOW - timedelta(days=5))]
        assert filter_backfill_candidates(
            new, pool, global_excluded_ids={"p1"}
        ) == []

    def test_max_candidates_capped_at_5(self):
        new = mk("new", NOW)
        pool = [mk(f"p{i}", NOW - timedelta(days=5)) for i in range(10)]
        result = filter_backfill_candidates(new, pool)
        assert len(result) <= 5

    def test_self_excluded(self):
        new = mk("self", NOW)
        pool = [mk("self", NOW - timedelta(days=2))]
        assert filter_backfill_candidates(new, pool) == []
