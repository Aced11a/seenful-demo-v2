"""Place Anchor (DBCH) 算法 · 纯 Python 实现.

参考:
  docs/10_mini_album_schema.md
  docs/22_location_geocoder.md (ADR-0016 4 档)
  decisions/0005-place-anchor-dbch.md (DBCH 核心)
  decisions/0016-location-geocoder-4tier.md (4 档 supersede ADR-0007)
  archive/specs/Place_Anchor_Spec_Final.md (原始 spec, 已归档)

ADR-0016 (supersede ADR-0007):
  · distance_to_band 下钻 4 档 context (市内/省内/国内/国外)
  · 读 cfg["band_thresholds_4tier"][context]
  · buffer base 读 cfg["buffer_4tier"]["base_m"][context]

提供:
  · dbscan_cluster        — O(n²) DBSCAN (适用 n ≤ 30)
  · convex_hull           — Andrew's monotone chain
  · point_in_polygon      — Ray casting
  · point_to_hull_distance_m
  · compute_buffer_m
  · match_new_photo / match_against_cluster / match_against_outliers
  · build_place_anchor    — 从照片列表生成 PlaceAnchor

依赖: 仅 stdlib (math). 不引 numpy/shapely/sklearn.
"""
from __future__ import annotations

import math
import uuid

from src.contracts import (
    Cluster,
    Context,
    HomeCityRegion,
    L1Output,
    MatchResult,
    OutlierPoint,
    PlaceAnchor,
)
from src.policy.config_loader import load_config

BAND_PRIORITY = {"none": 0, "weak": 1, "medium": 2, "strong": 3}


# ═════════════════════════════════════════════════════════════════
# 距离工具
# ═════════════════════════════════════════════════════════════════

def haversine_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """两点 (lat, lng) 球面距离, 单位米."""
    lat1, lng1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lng2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    earth_radius_m = 6_371_000.0
    return earth_radius_m * c


def haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return haversine_m(p1, p2) / 1000.0


# ═════════════════════════════════════════════════════════════════
# DBSCAN (O(n²) 纯 Python, 适用 n ≤ 30)
# ═════════════════════════════════════════════════════════════════

def dbscan_cluster(
    points: list[tuple[float, float]],
    eps_m: float,
    min_samples: int = 2,
) -> tuple[list[list[int]], list[int]]:
    """对点集做 DBSCAN, 返回 (clusters_indices, noise_indices).

    clusters_indices: [[idx, ...], [idx, ...]] 每簇的点索引
    noise_indices: [idx, ...] 未成簇的 outlier 点索引
    """
    n = len(points)
    if n == 0:
        return [], []

    # 邻接表 (距离 <= eps_m)
    neighbors: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if haversine_m(points[i], points[j]) <= eps_m:
                neighbors[i].append(j)
                neighbors[j].append(i)

    labels: list[int] = [-1] * n   # -1 = 未访问; -2 = noise; ≥0 = cluster id
    cluster_id = 0

    for i in range(n):
        if labels[i] != -1:
            continue
        # 核心点条件: 邻居数 >= min_samples - 1 (不含自己)
        if len(neighbors[i]) + 1 < min_samples:
            labels[i] = -2
            continue
        # 启动新簇, 广度优先扩展
        labels[i] = cluster_id
        queue = list(neighbors[i])
        while queue:
            j = queue.pop(0)
            if labels[j] == -2:
                labels[j] = cluster_id   # noise 转簇成员
            if labels[j] != -1:
                continue
            labels[j] = cluster_id
            if len(neighbors[j]) + 1 >= min_samples:
                queue.extend(neighbors[j])
        cluster_id += 1

    clusters: list[list[int]] = [[] for _ in range(cluster_id)]
    noise: list[int] = []
    for idx, lab in enumerate(labels):
        if lab >= 0:
            clusters[lab].append(idx)
        else:
            noise.append(idx)
    return clusters, noise


# ═════════════════════════════════════════════════════════════════
# 凸包 (Andrew's monotone chain)
# ═════════════════════════════════════════════════════════════════

def convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """返回凸包顶点 (lat, lng) 列表, 顺时针环, 不闭合 (首尾不重复).

    < 3 个不同点时, 返回原点列表去重 (不构成多边形).
    """
    unique = list({(round(p[0], 8), round(p[1], 8)) for p in points})
    unique.sort()
    if len(unique) < 3:
        return unique

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # 下半凸包
    lower: list[tuple[float, float]] = []
    for p in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    # 上半凸包
    upper: list[tuple[float, float]] = []
    for p in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    # 合并 (去掉重复的首尾)
    return lower[:-1] + upper[:-1]


# ═════════════════════════════════════════════════════════════════
# 点几何
# ═════════════════════════════════════════════════════════════════

def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Ray casting. polygon 是闭合环 (首尾相同或自动闭合)."""
    if len(polygon) < 3:
        return False
    x, y = point[1], point[0]   # lng, lat (x=lng/y=lat 视角)
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i][1], polygon[i][0]
        xj, yj = polygon[j][1], polygon[j][0]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def point_to_segment_distance_m(
    point: tuple[float, float],
    seg_a: tuple[float, float],
    seg_b: tuple[float, float],
) -> float:
    """点到线段最短距离, 米.

    使用 haversine 近似 (适用本应用规模, 单段距离 < 数 km).
    投影到线段上, 再算 haversine 到投影点.
    """
    # 投影系数 t ∈ [0, 1] 表示投影在 ab 上的位置
    ax, ay = seg_a[1], seg_a[0]   # lng, lat
    bx, by = seg_b[1], seg_b[0]
    px, py = point[1], point[0]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return haversine_m(point, seg_a)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj = (ay + t * dy, ax + t * dx)   # (lat, lng)
    return haversine_m(point, proj)


def point_to_hull_distance_m(
    point: tuple[float, float],
    hull: list[tuple[float, float]],
) -> float:
    """点到凸包距离, 米.

    点在 hull 内 → 0
    点在 hull 外 → 到所有 hull 边的最短距离
    hull 只有 1 点 → haversine 到该点
    hull 只有 2 点 (退化线段) → 点到线段
    """
    if not hull:
        return float("inf")
    if len(hull) == 1:
        return haversine_m(point, hull[0])
    if len(hull) == 2:
        return point_to_segment_distance_m(point, hull[0], hull[1])
    if point_in_polygon(point, hull):
        return 0.0
    min_d = float("inf")
    for i in range(len(hull)):
        a = hull[i]
        b = hull[(i + 1) % len(hull)]
        d = point_to_segment_distance_m(point, a, b)
        if d < min_d:
            min_d = d
    return min_d


# ═════════════════════════════════════════════════════════════════
# Buffer 公式
# ═════════════════════════════════════════════════════════════════

def compute_buffer_m(n: int, base_m: float, alpha: float) -> float:
    """buffer = base / (1 + alpha × ln(n)). n=1 时 buffer=base."""
    if n <= 1:
        return base_m
    return base_m / (1.0 + alpha * math.log(n))


# ═════════════════════════════════════════════════════════════════
# 几何中心 (簇 centroid)
# ═════════════════════════════════════════════════════════════════

def geometric_median(points: list[tuple[float, float]]) -> tuple[float, float]:
    """几何中位数 (简化为算术平均, 小样本足够)."""
    if not points:
        return (0.0, 0.0)
    lat = sum(p[0] for p in points) / len(points)
    lng = sum(p[1] for p in points) / len(points)
    return (lat, lng)


# ═════════════════════════════════════════════════════════════════
# 档位映射 + 高频降档
# ═════════════════════════════════════════════════════════════════

def distance_to_band(d_m: float, context: Context, band_cfg: dict) -> str:
    """距离 → band (ADR-0016 4 档: 市内/省内/国内/国外).

    band_cfg 是 cfg["band_thresholds_4tier"], 按 context 下钻读 strong_m/medium_m/weak_m.

    Supersede ADR-0007 临时单一表; OQ-017 回切完成.
    """
    tier_cfg = band_cfg[context]
    if d_m <= tier_cfg["strong_m"]:
        return "strong"
    if d_m <= tier_cfg["medium_m"]:
        return "medium"
    if d_m <= tier_cfg["weak_m"]:
        return "weak"
    return "none"


def downgrade_one_level(band: str) -> str:
    return {"strong": "medium", "medium": "weak", "weak": "none", "none": "none"}[band]


# ═════════════════════════════════════════════════════════════════
# 匹配函数 (核心)
# ═════════════════════════════════════════════════════════════════

def match_against_cluster(
    new_photo_gps: tuple[float, float],
    cluster: Cluster,
    context: Context,
    cfg: dict,
    user_context=None,             # UserContext | None, 详见 ADR-0006
    l1_data: dict | None = None,   # dict[photo_id, L1Output], Plan A 需用
) -> tuple[str, dict]:
    """对单簇做 hull + buffer 匹配, 返回 (band, diagnostics).

    距离档位 + buffer base (ADR-0016 4 档):
      · buffer base 读 cfg["buffer_4tier"]["base_m"][context]
      · distance_to_band 读 cfg["band_thresholds_4tier"][context]
      · context 下钻 (supersede ADR-0007 单一表)

    高频低质量降档 (ADR-0006):
      · user_context 为 None → 跳过判定, 不降档 (v0.1 demo 默认行为)
      · 否则调 is_low_quality_place 实时判定; 命中则 band 降一档
    """
    n = len(cluster.member_photo_ids)
    base = float(cfg["buffer_4tier"]["base_m"][context])
    alpha = float(cfg["buffer_4tier"]["alpha"])
    buffer_m = compute_buffer_m(n, base, alpha)

    if point_in_polygon(new_photo_gps, cluster.convex_hull):
        raw_d = 0.0
        d_m = 0.0
    else:
        raw_d = point_to_hull_distance_m(new_photo_gps, cluster.convex_hull)
        d_m = max(0.0, raw_d - buffer_m)

    band = distance_to_band(d_m, context, cfg["band_thresholds_4tier"])

    # ADR-0006: 实时低质量判定 + 降档
    from src.mini_album.low_quality_place import is_low_quality_place
    low_q_result = is_low_quality_place(cluster, user_context, l1_data)
    if low_q_result.is_low_quality:
        band = downgrade_one_level(band)

    diag = {
        "cluster_id": cluster.cluster_id,
        "cluster_size": n,
        "raw_distance_m": raw_d,
        "buffer_m": buffer_m,
        "effective_distance_m": d_m,
        "context": context,
        "band_table_used": context,        # ADR-0016: 直接用 context 名
        "is_low_quality": low_q_result.is_low_quality,
        "low_quality_reason": low_q_result.signal_source,
    }
    return band, diag


def match_against_outliers(
    new_photo_gps: tuple[float, float],
    outliers: list[OutlierPoint],
    context: Context,
    cfg: dict,
) -> MatchResult:
    """无簇仅 outlier 时, 取最近的 outlier 算点点距离, 不用 buffer.

    ADR-0016: distance_to_band 4 档下钻 context.
    """
    distances = [(o, haversine_m(new_photo_gps, o.gps)) for o in outliers]
    nearest, d_m = min(distances, key=lambda x: x[1])
    band = distance_to_band(d_m, context, cfg["band_thresholds_4tier"])
    return MatchResult(
        band=band,
        matched_target_type="outlier",
        matched_target_id=nearest.photo_id,
        diagnostics={
            "outlier_id": nearest.photo_id,
            "raw_distance_m": d_m,
            "buffer_m": 0.0,
            "effective_distance_m": d_m,
            "context": context,
            "band_table_used": "unified",    # ADR-0007
            "is_first_match_in_album": True,
        },
    )


def match_new_photo(
    new_photo_gps: tuple[float, float] | None,
    anchor: PlaceAnchor,
    context: Context,
    cfg: dict | None = None,
    user_context=None,             # UserContext | None, 见 ADR-0006
    l1_data: dict | None = None,   # dict[photo_id, L1Output]
) -> MatchResult:
    """主匹配函数 · 见 docs/10 §2.6.

    返回 MatchResult, band 字段是真值表唯一消费的输出.
    user_context + l1_data 用于 ADR-0006 高频低质量地点降档 (实时判定).
    user_context=None → 跳过低质量判定 (v0.1 demo 默认).
    """
    if new_photo_gps is None:
        return MatchResult(band="none", reason="no_gps")

    cfg = cfg or load_config("place_anchor.yaml")

    # 场景 A: 有簇 → 对每个簇算, 取最强, strong 早返
    if anchor.clusters:
        best_band = "none"
        best_target_id: str | None = None
        best_diag: dict = {}
        for cluster in anchor.clusters:
            band, diag = match_against_cluster(
                new_photo_gps, cluster, context, cfg,
                user_context=user_context, l1_data=l1_data,
            )
            if BAND_PRIORITY[band] > BAND_PRIORITY[best_band]:
                best_band = band
                best_target_id = cluster.cluster_id
                best_diag = diag
            if band == "strong":
                break   # ★ 早返
        return MatchResult(
            band=best_band,
            matched_target_type="cluster",
            matched_target_id=best_target_id,
            diagnostics=best_diag,
        )

    # 场景 B: 无簇仅 outlier
    if anchor.outliers:
        return match_against_outliers(new_photo_gps, anchor.outliers, context, cfg)

    # 场景 C: 完全空
    return MatchResult(band="none", reason="empty_anchor")


# ═════════════════════════════════════════════════════════════════
# 构造 PlaceAnchor (DBSCAN 把点集分成簇 + outlier)
# ═════════════════════════════════════════════════════════════════

def build_place_anchor(
    photos: list[L1Output],
    context: Context,
    cfg: dict | None = None,
) -> PlaceAnchor:
    """从照片列表构造 PlaceAnchor.

    流程:
      1. 提取每张照片的 GPS (无 GPS 的跳过)
      2. DBSCAN 分簇 (eps 用对应 context, min_samples=2)
      3. 簇 → Cluster 对象 (含 convex_hull / centroid, is_low_quality=False 默认)
      4. 噪声点 → OutlierPoint

    ⚠ ADR-0006: cluster.is_low_quality **不在 build 时计算**, 而由
    match_against_cluster 调 is_low_quality_place 实时填充 (依赖 user_context).
    本函数构造时一律设 is_low_quality=False 占位.

    相册级 is_high_frequency_anchor 保留为兼容字段, 默认 False.
    """
    cfg = cfg or load_config("place_anchor.yaml")
    eps_m = float(cfg["dbscan"]["eps_m"][context])
    min_samples = int(cfg["dbscan"]["min_samples"])

    photos_with_gps = [p for p in photos if p.exif_location is not None]
    if not photos_with_gps:
        return PlaceAnchor(clusters=[], outliers=[], is_high_frequency_anchor=False)

    points = [p.exif_location for p in photos_with_gps]
    cluster_indices, noise_indices = dbscan_cluster(points, eps_m, min_samples)

    clusters: list[Cluster] = []
    for cluster_idx_list in cluster_indices:
        cluster_points = [points[i] for i in cluster_idx_list]
        cluster_photo_ids = [photos_with_gps[i].photo_id for i in cluster_idx_list]
        hull = convex_hull(cluster_points)
        centroid = geometric_median(cluster_points)
        clusters.append(Cluster(
            cluster_id=f"c_{uuid.uuid4().hex[:8]}",
            member_photo_ids=cluster_photo_ids,
            convex_hull=hull,
            centroid=centroid,
            is_low_quality=False,   # ADR-0006: 实时填充, build 时默认 False
        ))

    outliers: list[OutlierPoint] = []
    for idx in noise_indices:
        outliers.append(OutlierPoint(
            photo_id=photos_with_gps[idx].photo_id,
            gps=points[idx],
        ))

    # 相册级 is_high_frequency_anchor (保留为兼容字段, ADR-0006 后实际不用)
    return PlaceAnchor(
        clusters=clusters,
        outliers=outliers,
        is_high_frequency_anchor=False,
    )
