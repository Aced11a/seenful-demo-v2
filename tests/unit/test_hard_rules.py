"""前置硬规则单测.

参考: docs/06_hard_rules.md
"""
from __future__ import annotations

from datetime import datetime

from src.contracts import L1Output
from src.contracts.l1_output import ImageFacts, SafetyFlags
from src.policy.hard_rules import pre_filter


def mk_photo(
    pid: str,
    sensitive: str = "none",
    has_gps: bool = True,
    captured_source: str = "exif",
) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 1, 14, 0),
        captured_at_source=captured_source,  # type: ignore[arg-type]
        image_facts=ImageFacts(exif_location=(30.0, 120.0)) if has_gps else ImageFacts(),
        safety_flags=SafetyFlags(sensitive_level=sensitive),  # type: ignore[arg-type]
    )


class TestPreFilter:
    def test_below_min_count(self):
        result = pre_filter([mk_photo("p1"), mk_photo("p2")])
        assert not result.passed
        assert result.reason == "below_min_photo_count"

    def test_passes_with_three_clean(self):
        result = pre_filter([mk_photo(f"p{i}") for i in range(3)])
        assert result.passed
        assert result.reason == "passed"

    def test_any_sensitive_blocks(self):
        photos = [
            mk_photo("p1"),
            mk_photo("p2", sensitive="medium"),
            mk_photo("p3"),
        ]
        result = pre_filter(photos)
        assert not result.passed
        assert result.reason == "any_sensitive"
        assert "p2" in result.blocking_photo_ids

    def test_all_sensitive(self):
        photos = [mk_photo(f"p{i}", sensitive="high") for i in range(3)]
        result = pre_filter(photos)
        assert not result.passed
        assert result.reason == "all_sensitive"

    def test_low_sensitive_does_not_block(self):
        photos = [mk_photo(f"p{i}", sensitive="low") for i in range(3)]
        result = pre_filter(photos)
        assert result.passed

    def test_all_fallback_no_gps_suppress(self):
        photos = [
            mk_photo(f"p{i}", has_gps=False, captured_source="upload_time_fallback")
            for i in range(3)
        ]
        result = pre_filter(photos)
        assert not result.passed
        assert result.reason == "weak_fallback_time_only"

    def test_fallback_with_gps_passes(self):
        photos = [
            mk_photo(f"p{i}", has_gps=True, captured_source="upload_time_fallback")
            for i in range(3)
        ]
        result = pre_filter(photos)
        assert result.passed
