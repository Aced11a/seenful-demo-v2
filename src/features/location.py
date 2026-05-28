"""路径 B Location 维度 (ADR-0010): 分级 DBSCAN + PCA OBB + 形状校正 + transit 降档.

参考:
  docs/16_path_b_location.md (完整算法规范)
  decisions/0010-path-b-location-dbch-pca-shape.md
  config/path_b_location.yaml

输出: LocationFeature (含 band 终值 + 完整诊断字段)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from src.contracts import BandLevel, L1Output, LocationFeature, LocationShape
from src.policy.config_loader import load_config


# ─── 几何工具 ────────────────────────────────────────────────


def haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """两点 GPS (lat, lng) 球面距离, km."""
    lat1, lng1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lng2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def haversine_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return haversine_km(p1, p2) * 1000.0


def to_local_meters(
    gps_list: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    """GPS (lat, lng) → 局部平面 (x_m, y_m), 同时返回 centroid GPS.

    参考: docs/16 §2.2.1. 线性近似, v0.1 单次上传跨度 ≤ 数十 km 精度足够.
    """
    lat0 = sum(lat for lat, _ in gps_list) / len(gps_list)
    lng0 = sum(lng for _, lng in gps_list) / len(gps_list)
    lat0_rad = math.radians(lat0)
    coords: list[tuple[float, float]] = []
    for lat, lng in gps_list:
        x = (lng - lng0) * 111_000.0 * math.cos(lat0_rad)
        y = (lat - lat0) * 111_000.0
        coords.append((x, y))
    return coords, (lat0, lng0)


def euclidean_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


# ─── DBSCAN 手撸 (docs/16 §2.2.2) ────────────────────────────


def dbscan(
    points_xy: list[tuple[float, float]],
    eps_m: float,
    min_samples: int,
) -> list[int]:
    """返回每个点的 cluster_id (0/1/2/..) 或 -1 (outlier).

    时间 O(n²), 对 v0.1 ≤ 50 张照片足够.
    """
    n = len(points_xy)
    labels = [-1] * n
    visited = [False] * n
    cluster_id = 0

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = [j for j in range(n) if euclidean_m(points_xy[i], points_xy[j]) <= eps_m]
        if len(neighbors) < min_samples:
            continue  # outlier (后续可能转 border)
        # 起新簇
        labels[i] = cluster_id
        queue = list(neighbors)
        while queue:
            j = queue.pop()
            if not visited[j]:
                visited[j] = True
                j_neighbors = [
                    k for k in range(n) if euclidean_m(points_xy[j], points_xy[k]) <= eps_m
                ]
                if len(j_neighbors) >= min_samples:
                    queue.extend(j_neighbors)
            if labels[j] == -1:
                labels[j] = cluster_id
        cluster_id += 1

    return labels


# ─── PCA OBB (docs/16 §2.3.1, 2×2 协方差矩阵闭式解) ──────────


def pca_obb(cluster_xy: list[tuple[float, float]]) -> tuple[float, float, float]:
    """返回 (L_km, W_km, R). 输入米制坐标."""
    n = len(cluster_xy)
    if n < 2:
        return 0.0, 0.0, 1.0

    cx = sum(x for x, _ in cluster_xy) / n
    cy = sum(y for _, y in cluster_xy) / n

    a = sum((x - cx) ** 2 for x, _ in cluster_xy) / n
    d = sum((y - cy) ** 2 for _, y in cluster_xy) / n
    b = sum((x - cx) * (y - cy) for x, y in cluster_xy) / n

    trace = a + d
    det = a * d - b * b
    disc = max(0.0, (trace / 2) ** 2 - det)
    sqrt_disc = math.sqrt(disc)
    lam_max = trace / 2 + sqrt_disc

    if abs(b) > 1e-9:
        v1 = (lam_max - d, b)
    else:
        v1 = (1.0, 0.0) if a >= d else (0.0, 1.0)
    norm = math.hypot(v1[0], v1[1])
    if norm < 1e-12:
        v1 = (1.0, 0.0)
    else:
        v1 = (v1[0] / norm, v1[1] / norm)
    v2 = (-v1[1], v1[0])

    proj_v1 = [(x - cx) * v1[0] + (y - cy) * v1[1] for x, y in cluster_xy]
    proj_v2 = [(x - cx) * v2[0] + (y - cy) * v2[1] for x, y in cluster_xy]

    L_km = (max(proj_v1) - min(proj_v1)) / 1000.0
    W_km = (max(proj_v2) - min(proj_v2)) / 1000.0
    R = L_km / W_km if W_km > 1e-6 else float("inf")
    return L_km, W_km, R


# ─── 凸包 (Andrew's monotone chain) + 直径 ───────────────────


def convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """返回凸包顶点 (逆时针)."""
    pts = sorted(set(points))
    if len(pts) <= 1:
        return list(pts)

    def cross(o, a, c):
        return (a[0] - o[0]) * (c[1] - o[1]) - (a[1] - o[1]) * (c[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def convex_hull_diameter_km(cluster_xy_m: list[tuple[float, float]]) -> float:
    """凸包顶点两两最远距离, km. 输入米制坐标."""
    hull = convex_hull(cluster_xy_m)
    if len(hull) < 2:
        return 0.0
    max_d_m = 0.0
    for i in range(len(hull)):
        for j in range(i + 1, len(hull)):
            d = euclidean_m(hull[i], hull[j])
            if d > max_d_m:
                max_d_m = d
    return max_d_m / 1000.0


def cluster_gap_km(cluster_a_xy: list[tuple[float, float]], cluster_b_xy: list[tuple[float, float]]) -> float:
    """两个簇凸包间最小距离 (近似: 顶点 vs 顶点最小), km."""
    hull_a = convex_hull(cluster_a_xy)
    hull_b = convex_hull(cluster_b_xy)
    if not hull_a or not hull_b:
        return float("inf")
    min_d_m = float("inf")
    for pa in hull_a:
        for pb in hull_b:
            d = euclidean_m(pa, pb)
            if d < min_d_m:
                min_d_m = d
    return min_d_m / 1000.0


# ─── 轨迹长度 + transit ──────────────────────────────────────


def trace_length_km(photos_sorted_by_ts: list[L1Output]) -> float:
    """按 timestamp 升序连相邻点折线, 累加 haversine 距离, km."""
    total_m = 0.0
    for i in range(len(photos_sorted_by_ts) - 1):
        p1, p2 = photos_sorted_by_ts[i].exif_location, photos_sorted_by_ts[i + 1].exif_location
        if p1 is None or p2 is None:
            continue
        total_m += haversine_m(p1, p2)
    return total_m / 1000.0


def max_transit_kmh(
    photos_sorted_by_ts: list[L1Output],
    min_interval_minutes: int,
) -> float | None:
    """时序相邻对 (Δt ≥ min_interval_minutes) 的距离 / 时间最大值, kmh.

    全部相邻对 Δt < min_interval_minutes → 返回 None (transit_unknown).
    防 GPS 漂移瞬时膨胀.
    """
    speeds: list[float] = []
    for i in range(len(photos_sorted_by_ts) - 1):
        a, c = photos_sorted_by_ts[i], photos_sorted_by_ts[i + 1]
        if a.captured_at is None or c.captured_at is None:
            continue
        if a.exif_location is None or c.exif_location is None:
            continue
        delta_min = (c.captured_at - a.captured_at).total_seconds() / 60.0
        if delta_min < min_interval_minutes:
            continue
        d_km = haversine_km(a.exif_location, c.exif_location)
        speeds.append(d_km / (delta_min / 60.0))
    return max(speeds) if speeds else None


# ─── 派生 score (老 score 字段兼容计算) ──────────────────────


def _derived_score(band: BandLevel) -> float:
    """band → 派生展示 score. 真值表不读, 仅显示用."""
    return {"strong": 1.0, "medium": 0.7, "weak": 0.4, "none": 0.1}[band]


# ─── Step A1 · PCA 基础 band 网格 (docs/16 §三) ──────────────


def _step_a1_pca_grid(
    L: float, W: float, R: float, k_inner: int, cfg: dict
) -> tuple[BandLevel, LocationShape, str]:
    """9 行网格按顺序匹配, 第一条命中即为基础值."""
    a1 = cfg["a1_grid"]

    # A1.1: L > 5 → none oversized
    if L > a1["l_oversized_km"]:
        return "none", LocationShape.OVERSIZED, "A1.1"

    # A1.2: W > 1.5 且 L > W → none oversized
    if W > a1["w_oversized_km"] and L > W:
        return "none", LocationShape.OVERSIZED, "A1.2"

    # A1.3: R > 5 且 W ≥ 1.5 → none oversized
    if R > a1["r_oversized"] and W >= a1["w_oversized_km"]:
        return "none", LocationShape.OVERSIZED, "A1.3"

    # A1.4: L ≤ 0.5 → strong compact
    if L <= a1["l_compact_km"]:
        return "strong", LocationShape.COMPACT, "A1.4"

    # A1.5: linear (W < 0.5 + R > 5 + L ≤ 5 + K_inner=1) → strong linear
    if (
        W < a1["w_linear_max_km"]
        and R > a1["r_linear_min"]
        and L <= a1["l_linear_max_km"]
        and k_inner == 1
    ):
        return "strong", LocationShape.LINEAR, "A1.5"

    # A1.6: L ≤ 1.5 + R ≤ 5 → strong compact
    if L <= a1["l_compact_max_km"] and R <= a1["r_compact_max"]:
        return "strong", LocationShape.COMPACT, "A1.6"

    # A1.7: L ≤ 3 + W ≤ 1.5 → medium stretched
    if L <= a1["l_stretched_max_km"] and W <= a1["w_stretched_max_km"]:
        return "medium", LocationShape.STRETCHED, "A1.7"

    # A1.8: 3 < L ≤ 5 + W ≤ 1.5 → medium extended
    if L <= a1["l_extended_max_km"] and W <= a1["w_stretched_max_km"]:
        return "medium", LocationShape.EXTENDED, "A1.8"

    # A1.9: 其他 → weak irregular
    return "weak", LocationShape.IRREGULAR, "A1.9"


# ─── Step A2 · 形状校正 (docs/16 §四) ────────────────────────


def _step_a2_shape_correction(
    band: BandLevel,
    shape: LocationShape,
    rule_fired: str,
    tortuosity: float | None,
    L: float,
    W: float,
    cfg: dict,
) -> tuple[BandLevel, LocationShape, str]:
    """A2.1 环形/U 形平反; A2.2 弯曲线性降档. tortuosity=None 时不动."""
    if tortuosity is None:
        return band, shape, rule_fired

    a2 = cfg["a2_correction"]

    # A2.1: A1.1 / A1.2 命中 none, 但 τ > 2 + L ≤ 8 + W ≤ 3 → medium loop
    if (
        rule_fired in ("A1.1", "A1.2")
        and tortuosity > a2["tortuosity_loop_threshold"]
        and L <= a2["l_loop_max_km"]
        and W <= a2["w_loop_max_km"]
    ):
        return "medium", LocationShape.LOOP, "A2.1"

    # A2.2: A1.5 linear strong, 但 τ > 1.5 → medium linear_curved
    if rule_fired == "A1.5" and tortuosity > a2["tortuosity_curved_threshold"]:
        return "medium", LocationShape.LINEAR_CURVED, "A2.2"

    return band, shape, rule_fired


# ─── Step A3 · transit 降档 (docs/16 §五) ────────────────────


def _step_a3_transit_demote(
    band: BandLevel, rule_fired: str, transit_kmh: float | None, cfg: dict
) -> tuple[BandLevel, str]:
    """transit ≥ 30 kmh + 当前 band ∈ {strong, medium} → 降一档."""
    if transit_kmh is None:
        return band, rule_fired
    threshold = cfg["a3_transit"]["transit_demote_kmh"]
    if transit_kmh < threshold:
        return band, rule_fired
    if band == "strong":
        return "medium", f"{rule_fired}+A3_transit_demote"
    if band == "medium":
        return "weak", f"{rule_fired}+A3_transit_demote"
    return band, rule_fired


# ─── 路径 B · K_outer = 2 单步判定 (docs/16 §六) ─────────────


def _step_b_dual_cluster(
    gap_km: float, transit_kmh: float | None, cfg: dict
) -> tuple[BandLevel, LocationShape, str]:
    """双簇 4 行判定."""
    b = cfg["path_b_dual"]

    if gap_km <= b["gap_close_km"]:
        return "strong", LocationShape.MULTI_CLOSE, "B.1"

    if gap_km > b["gap_walk_max_km"]:
        return "none", LocationShape.MULTI_FAR, "B.4"

    # gap ≤ 2km
    if transit_kmh is None or transit_kmh < b["transit_walk_kmh"]:
        return "medium", LocationShape.MULTI_WALK, "B.2"
    return "weak", LocationShape.MULTI_DRIVE, "B.3"


# ─── 高层入口 ────────────────────────────────────────────────


@dataclass
class _Phase1Result:
    cluster_count_outer: int
    labels: list[int]
    outlier_count: int
    points_xy: list[tuple[float, float]]
    valid_photos: list[L1Output]   # 有 GPS 的子集
    valid_indices: list[int]        # valid_photos 在原 photos 中的下标


def _phase1_outer(photos: list[L1Output], cfg: dict) -> _Phase1Result:
    """Phase 1 几何预处理 + 外层 DBSCAN."""
    valid_photos = [p for p in photos if p.exif_location is not None]
    valid_indices = [i for i, p in enumerate(photos) if p.exif_location is not None]
    if len(valid_photos) < 2:
        return _Phase1Result(0, [], len(valid_photos), [], valid_photos, valid_indices)

    gps = [p.exif_location for p in valid_photos]
    points_xy, _ = to_local_meters(gps)
    labels = dbscan(
        points_xy,
        eps_m=cfg["dbscan"]["eps_outer_m"],
        min_samples=cfg["dbscan"]["min_samples"],
    )
    cluster_ids = set(label for label in labels if label >= 0)
    outlier_count = sum(1 for label in labels if label == -1)
    return _Phase1Result(
        cluster_count_outer=len(cluster_ids),
        labels=labels,
        outlier_count=outlier_count,
        points_xy=points_xy,
        valid_photos=valid_photos,
        valid_indices=valid_indices,
    )


def build_location_feature(photos: list[L1Output]) -> LocationFeature:
    """路径 B Location 维度入口. 参考 docs/16 §二 整体流水线."""
    cfg = load_config("path_b_location.yaml")["path_b_location"]
    is_hfp = any(p.is_high_frequency_place for p in photos)

    phase1 = _phase1_outer(photos, cfg)
    k_outer = phase1.cluster_count_outer

    # ─── K_outer = 0 或 ≥ 3 → scattered none ────────────────
    if k_outer == 0:
        rule_fired = "K_outer_0" if phase1.valid_photos else "K_outer_no_gps"
        return LocationFeature(
            band="none",
            rule_fired=rule_fired,
            score=_derived_score("none"),
            cluster_count_outer=0,
            cluster_count_inner=None,
            outlier_count=phase1.outlier_count,
            shape=LocationShape.SCATTERED,
            is_high_frequency_place=is_hfp,
        )

    if k_outer >= 3:
        return LocationFeature(
            band="none",
            rule_fired="K_outer_3_plus",
            score=_derived_score("none"),
            cluster_count_outer=k_outer,
            cluster_count_inner=None,
            outlier_count=phase1.outlier_count,
            shape=LocationShape.SCATTERED,
            is_high_frequency_place=is_hfp,
        )

    # ─── K_outer = 2 → 路径 B 双簇 ─────────────────────────
    if k_outer == 2:
        cluster_groups: list[list[tuple[float, float]]] = [[], []]
        for label, xy in zip(phase1.labels, phase1.points_xy, strict=True):
            if label >= 0:
                cluster_groups[label].append(xy)
        gap_km = cluster_gap_km(cluster_groups[0], cluster_groups[1])
        # transit 用全部有时间戳的相邻照片对 (跨簇也算, 这是双簇场景的关键信号)
        sorted_photos = sorted(
            (p for p in phase1.valid_photos if p.captured_at is not None),
            key=lambda p: p.captured_at,
        )
        transit = max_transit_kmh(sorted_photos, cfg["a3_transit"]["min_interval_minutes"])

        band, shape, rule_fired = _step_b_dual_cluster(gap_km, transit, cfg)
        if is_hfp:
            band = _downgrade_one(band)
            rule_fired = f"{rule_fired}+HFP_demote"

        return LocationFeature(
            band=band,
            rule_fired=rule_fired,
            score=_derived_score(band),
            cluster_count_outer=2,
            cluster_count_inner=None,
            outlier_count=phase1.outlier_count,
            inter_outer_gap_km=gap_km,
            max_transit_kmh=transit,
            shape=shape,
            is_high_frequency_place=is_hfp,
        )

    # ─── K_outer = 1 → 三层判定 (A1 → A2 → A3) ─────────────
    cluster_xy = [
        xy for label, xy in zip(phase1.labels, phase1.points_xy, strict=True) if label == 0
    ]
    cluster_photos = [
        p for p, label in zip(phase1.valid_photos, phase1.labels, strict=True) if label == 0
    ]

    # 内层 DBSCAN (eps=500m), 仅对 outer cluster 内的点
    inner_labels = dbscan(
        cluster_xy,
        eps_m=cfg["dbscan"]["eps_inner_m"],
        min_samples=cfg["dbscan"]["min_samples"],
    )
    inner_cluster_ids = set(label for label in inner_labels if label >= 0)
    # 退化情况: 内层 DBSCAN 全是 outlier (例如内簇点 < min_samples), 视为 1 个隐式簇
    k_inner = len(inner_cluster_ids) if inner_cluster_ids else 1

    # 几何特征
    L, W, R = pca_obb(cluster_xy)
    D = convex_hull_diameter_km(cluster_xy)
    sorted_cluster_photos = sorted(
        (p for p in cluster_photos if p.captured_at is not None),
        key=lambda p: p.captured_at,
    )
    T = trace_length_km(sorted_cluster_photos)
    tortuosity = (T / D) if D > 1e-6 else None
    transit = max_transit_kmh(sorted_cluster_photos, cfg["a3_transit"]["min_interval_minutes"])

    # Step A1
    band, shape, rule_fired = _step_a1_pca_grid(L, W, R, k_inner, cfg)
    # Step A2
    band, shape, rule_fired = _step_a2_shape_correction(band, shape, rule_fired, tortuosity, L, W, cfg)
    # Step A3
    band, rule_fired = _step_a3_transit_demote(band, rule_fired, transit, cfg)
    # 高频地点降一档 (ADR-0006)
    if is_hfp:
        band = _downgrade_one(band)
        rule_fired = f"{rule_fired}+HFP_demote"

    return LocationFeature(
        band=band,
        rule_fired=rule_fired,
        score=_derived_score(band),
        cluster_count_outer=1,
        cluster_count_inner=k_inner,
        outlier_count=phase1.outlier_count,
        outer_length_km=L,
        outer_width_km=W,
        outer_ratio=R if R != float("inf") else None,
        convex_hull_diameter_km=D,
        trace_length_km=T,
        tortuosity=tortuosity,
        inter_outer_gap_km=None,
        max_transit_kmh=transit,
        shape=shape,
        is_high_frequency_place=is_hfp,
    )


def _downgrade_one(band: BandLevel) -> BandLevel:
    return {"strong": "medium", "medium": "weak", "weak": "none", "none": "none"}[band]


# ─── v0.1 兼容入口 (assemble.py 仍调) ───────────────────────


def compute_location_score(photos: list[L1Output]) -> float:
    """v0.1 兼容入口: 返回 LocationFeature.score (派生展示值).

    新代码应直接调 build_location_feature 拿完整结构.
    """
    return build_location_feature(photos).score
