"""动态生长候选 (路径 A · Step 1).

参考: docs/04_truth_table_growth.md §候选集
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from src.contracts import L1Output, MiniAlbumFingerprint


def filter_candidate_albums(
    new_photo: L1Output,
    albums: Iterable[MiniAlbumFingerprint],
    now: datetime | None = None,
) -> list[MiniAlbumFingerprint]:
    """筛选可作为生长候选的老相册.

    HRG-PRE 前置硬规则:
      · is_growing = True
      · growth_lock_at > now (尚未锁定)
      · photo_count < max_photo_capacity
      · new_photo.photo_id NOT IN album.excluded_photo_ids
      · new_photo.sensitive_level < medium (敏感 → 整个路径 A 跳过)

    `now` 语义: 用于判断相册是否过了生长窗口.
    默认使用新照片的 captured_at (产品语义: "这张照片拍的时候,相册还能长吗?")
    """
    if new_photo.sensitive_level in ("medium", "high"):
        return []

    albums_list = list(albums)
    if not albums_list:
        return []

    if now is None:
        now = new_photo.captured_at or datetime.now(timezone.utc)

    candidates: list[MiniAlbumFingerprint] = []
    for album in albums_list:
        if not album.is_growing:
            continue
        if album.growth_lock_at <= now:
            continue
        if album.photo_count >= album.max_photo_capacity:
            continue
        if new_photo.photo_id in album.excluded_photo_ids:
            continue
        candidates.append(album)
    return candidates
