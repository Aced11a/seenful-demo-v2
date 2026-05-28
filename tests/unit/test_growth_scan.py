"""growth_scan 候选集筛选单测."""
from __future__ import annotations

from datetime import datetime, timezone

from src.candidate_builder.growth_scan import filter_candidate_albums
from src.contracts import L1Output, MiniAlbumFingerprint, PlaceAnchor
from src.contracts.l1_output import SafetyFlags


def mk_album(
    aid: str = "ma_a",
    is_growing: bool = True,
    growth_lock: datetime | None = None,
    photo_count: int = 3,
    max_capacity: int = 30,
    excluded: list[str] | None = None,
) -> MiniAlbumFingerprint:
    # 候选集筛选不关心 place_anchor 内容, 用空 PlaceAnchor 即可 (ADR-0005)
    return MiniAlbumFingerprint(
        mini_album_id=aid,
        user_id="user_demo",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        last_updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        growth_lock_at=growth_lock or datetime(2026, 5, 31, tzinfo=timezone.utc),
        is_growing=is_growing,
        photo_count=photo_count,
        max_photo_capacity=max_capacity,
        excluded_photo_ids=excluded or [],
        place_anchor=PlaceAnchor(clusters=[], outliers=[]),
    )


def mk_photo(
    pid: str = "p_new",
    sensitive: str = "none",
    captured: datetime | None = None,
) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=captured or datetime(2026, 5, 8, tzinfo=timezone.utc),
        safety_flags=SafetyFlags(sensitive_level=sensitive),  # type: ignore[arg-type]
    )


class TestFilterCandidate:
    def test_basic_pass(self):
        result = filter_candidate_albums(mk_photo(), [mk_album()])
        assert len(result) == 1

    def test_sensitive_blocks_all(self):
        result = filter_candidate_albums(
            mk_photo(sensitive="medium"),
            [mk_album()],
        )
        assert result == []

    def test_not_growing_skipped(self):
        result = filter_candidate_albums(
            mk_photo(),
            [mk_album(is_growing=False)],
        )
        assert result == []

    def test_locked_skipped(self):
        # growth_lock 在新照片之前 → 已锁
        result = filter_candidate_albums(
            mk_photo(captured=datetime(2026, 6, 10, tzinfo=timezone.utc)),
            [mk_album(growth_lock=datetime(2026, 5, 31, tzinfo=timezone.utc))],
        )
        assert result == []

    def test_capacity_full_skipped(self):
        result = filter_candidate_albums(
            mk_photo(),
            [mk_album(photo_count=30, max_capacity=30)],
        )
        assert result == []

    def test_excluded_photo_skipped(self):
        result = filter_candidate_albums(
            mk_photo(pid="p_new"),
            [mk_album(excluded=["p_new"])],
        )
        assert result == []

    def test_multi_albums_partial_pass(self):
        result = filter_candidate_albums(
            mk_photo(),
            [
                mk_album(aid="ma_pass"),
                mk_album(aid="ma_locked", is_growing=False),
                mk_album(aid="ma_pass2"),
            ],
        )
        assert {a.mini_album_id for a in result} == {"ma_pass", "ma_pass2"}
