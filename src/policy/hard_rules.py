"""前置 / 后置硬规则.

参考: docs/06_hard_rules.md
Policy Engine 100% 执行, LLM 无权覆盖.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.contracts import L1Output

PreFilterReason = Literal[
    "all_sensitive",
    "any_sensitive",
    "weak_fallback_time_only",
    "below_min_photo_count",
    "passed",
]


@dataclass
class PreFilterResult:
    passed: bool
    reason: PreFilterReason
    blocking_photo_ids: list[str]


def pre_filter(photos: list[L1Output], min_photos: int = 3) -> PreFilterResult:
    """Stage 1 · 前置硬规则. 命中即 suppress.

    HR-PRE-01: 任一 photo sensitive_level >= medium → suppress
    HR-PRE-03: 全部 fallback 时间且无 GPS → suppress
    HR-PRE-04: photo_count < min_photos → suppress (v0.1 简化)
    """
    if len(photos) < min_photos:
        return PreFilterResult(
            passed=False,
            reason="below_min_photo_count",
            blocking_photo_ids=[p.photo_id for p in photos],
        )

    sensitive_ids = [
        p.photo_id for p in photos
        if p.sensitive_level in ("medium", "high")
    ]
    if sensitive_ids:
        all_sensitive = len(sensitive_ids) == len(photos)
        return PreFilterResult(
            passed=False,
            reason="all_sensitive" if all_sensitive else "any_sensitive",
            blocking_photo_ids=sensitive_ids,
        )

    all_fallback = all(p.captured_at_source == "upload_time_fallback" for p in photos)
    no_gps = all(p.exif_location is None for p in photos)
    if all_fallback and no_gps:
        return PreFilterResult(
            passed=False,
            reason="weak_fallback_time_only",
            blocking_photo_ids=[p.photo_id for p in photos],
        )

    return PreFilterResult(passed=True, reason="passed", blocking_photo_ids=[])
