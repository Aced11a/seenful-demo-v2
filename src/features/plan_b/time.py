"""L2 1.0 time score (v1.3 §3.2.2 抄本).

参考: docs/24_feature_assembler_plan_ab.md §2.2
"""
from __future__ import annotations

from src.contracts import L1Output


def compute_time_score_legacy(photos: list[L1Output]) -> tuple[float, dict]:
    """v1.3 §3.2.2: time_span_hours → 分档 (×fallback factor).

    0.5h=1.0 / 2h=0.9 / 12h=0.7 / 48h=0.5 / 否则 0.2
    all_fallback ×0.5
    """
    timestamps = [p.captured_at for p in photos if p.captured_at is not None]
    if len(timestamps) < 2:
        return 0.0, {"time_span_hours": 0.0, "reason": "insufficient_timestamps"}

    sources = [
        getattr(p, "captured_at_source", "exif_time") for p in photos
    ]
    all_fallback = all(s == "upload_time_fallback" for s in sources)
    confidence_factor = 0.5 if all_fallback else 1.0

    time_span_hours = (
        max(timestamps) - min(timestamps)
    ).total_seconds() / 3600.0

    if time_span_hours < 0.5:
        base_score = 1.0
    elif time_span_hours < 2:
        base_score = 0.9
    elif time_span_hours < 12:
        base_score = 0.7
    elif time_span_hours < 48:
        base_score = 0.5
    else:
        base_score = 0.2

    score = base_score * confidence_factor

    return score, {
        "time_span_hours": time_span_hours,
        "all_fallback": all_fallback,
        "confidence_factor": confidence_factor,
        "primary_signal": "exif_time" if not all_fallback else "upload_time_fallback",
    }
