"""L2 1.0 location score (v1.3 §3.2.1 抄本).

参考: docs/24_feature_assembler_plan_ab.md §2.1
"""
from __future__ import annotations

from src.contracts import L1Output
from src.features.location import haversine_km


def compute_location_score_legacy(photos: list[L1Output]) -> tuple[float, dict]:
    """v1.3 §3.2.1: max_pairwise_distance → 分档.

    200m=1.0 / 500m=0.8 / 2000m=0.5 / 否则 0.1
    高频地点对半折扣 (0.5/0.4/0.2/0.1).

    返回 (score, diagnostic_dict).
    """
    locations = [p.exif_location for p in photos]
    has_gps = [loc for loc in locations if loc is not None]

    if not has_gps or len(has_gps) != len(photos):
        return 0.0, {
            "max_distance_m": None,
            "is_high_frequency_place": False,
            "reason": "missing_gps",
        }

    # 两两 GPS 距离 (转米)
    max_distance_m = 0.0
    n = len(locations)
    for i in range(n):
        for j in range(i + 1, n):
            d_km = haversine_km(locations[i], locations[j])
            d_m = d_km * 1000.0
            if d_m > max_distance_m:
                max_distance_m = d_m

    is_high_freq = any(p.is_high_frequency_place for p in photos)

    if max_distance_m < 200:
        score = 0.5 if is_high_freq else 1.0
    elif max_distance_m < 500:
        score = 0.4 if is_high_freq else 0.8
    elif max_distance_m < 2000:
        score = 0.2 if is_high_freq else 0.5
    else:
        score = 0.1

    return score, {
        "max_distance_m": max_distance_m,
        "is_high_frequency_place": is_high_freq,
        "primary_signal": "exif_gps",
    }
