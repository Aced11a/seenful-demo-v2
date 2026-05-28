"""Place Anchor (DBCH) 算法单测 (ADR-0005).

覆盖:
  · haversine 距离
  · DBSCAN 聚类 (核心点 / 直接密度可达 / 噪声)
  · Andrew's convex hull (3-N 点 / 退化情况)
  · point_in_polygon (内 / 外 / 边)
  · 点到凸包距离
  · Buffer 衰减公式
  · match_new_photo 三场景 (有簇 / 仅 outlier / 完全空)
  · strong 早返
  · 高频降档
"""
from __future__ import annotations

import math

import pytest

from src.contracts import (
    Cluster,
    L1Output,
    MatchResult,
    OutlierPoint,
    PlaceAnchor,
)
from src.mini_album.place_anchor import (
    build_place_anchor,
    compute_buffer_m,
    convex_hull,
    dbscan_cluster,
    haversine_m,
    match_new_photo,
    point_in_polygon,
    point_to_hull_distance_m,
)


# ═════════════════════════════════════════════════════════════════
# 距离工具
# ═════════════════════════════════════════════════════════════════

class TestHaversine:
    def test_zero_distance(self):
        assert haversine_m((30.0, 120.0), (30.0, 120.0)) == pytest.approx(0.0)

    def test_short_distance(self):
        # (30.2585, 120.1320) 到 (30.2588, 120.1322) 应该约 38m
        d = haversine_m((30.2585, 120.1320), (30.2588, 120.1322))
        assert 30 < d < 50


# ═════════════════════════════════════════════════════════════════
# DBSCAN
# ═════════════════════════════════════════════════════════════════

class TestDBSCAN:
    def test_empty(self):
        clusters, noise = dbscan_cluster([], eps_m=200, min_samples=2)
        assert clusters == [] and noise == []

    def test_single_point_is_noise(self):
        # 1 个点, min_samples=2 → 不能成簇 → 噪声
        clusters, noise = dbscan_cluster([(30.0, 120.0)], eps_m=200, min_samples=2)
        assert clusters == []
        assert noise == [0]

    def test_two_close_points_form_cluster(self):
        clusters, noise = dbscan_cluster(
            [(30.2585, 120.1320), (30.2588, 120.1322)],  # ~38m apart
            eps_m=200,
            min_samples=2,
        )
        assert len(clusters) == 1 and sorted(clusters[0]) == [0, 1]
        assert noise == []

    def test_two_far_points_are_noise(self):
        clusters, noise = dbscan_cluster(
            [(30.0, 120.0), (31.0, 121.0)],  # ~140km apart
            eps_m=200,
            min_samples=2,
        )
        assert clusters == []
        assert sorted(noise) == [0, 1]

    def test_three_close_one_far(self):
        # 3 张紧密 + 1 张离群
        clusters, noise = dbscan_cluster(
            [
                (30.2585, 120.1320),
                (30.2588, 120.1322),
                (30.2586, 120.1325),
                (31.0, 121.0),       # 离群
            ],
            eps_m=200,
            min_samples=2,
        )
        assert len(clusters) == 1
        assert sorted(clusters[0]) == [0, 1, 2]
        assert noise == [3]


# ═════════════════════════════════════════════════════════════════
# Convex Hull
# ═════════════════════════════════════════════════════════════════

class TestConvexHull:
    def test_single_point(self):
        assert convex_hull([(30.0, 120.0)]) == [(30.0, 120.0)]

    def test_two_points(self):
        h = convex_hull([(30.0, 120.0), (30.1, 120.1)])
        assert sorted(h) == [(30.0, 120.0), (30.1, 120.1)]

    def test_triangle(self):
        pts = [(30.2585, 120.1320), (30.2588, 120.1322), (30.2586, 120.1325)]
        h = convex_hull(pts)
        assert len(h) == 3
        assert set(h) == set(pts)

    def test_collinear_points_degenerate(self):
        # 共线点 hull 退化 (只保留端点或全部, 不严格要求)
        h = convex_hull([(30.0, 120.0), (30.0, 120.1), (30.0, 120.2)])
        assert len(h) >= 2


# ═════════════════════════════════════════════════════════════════
# Point in polygon
# ═════════════════════════════════════════════════════════════════

class TestPointInPolygon:
    triangle = [(30.2585, 120.1320), (30.2588, 120.1322), (30.2586, 120.1325)]

    def test_inside(self):
        # (30.2587, 120.1323) 应该在三角形内
        assert point_in_polygon((30.2587, 120.1323), self.triangle) is True

    def test_outside_above(self):
        assert point_in_polygon((30.2590, 120.1325), self.triangle) is False

    def test_outside_far(self):
        assert point_in_polygon((31.0, 121.0), self.triangle) is False


# ═════════════════════════════════════════════════════════════════
# 点到凸包距离
# ═════════════════════════════════════════════════════════════════

class TestPointToHullDistance:
    triangle = [(30.2585, 120.1320), (30.2588, 120.1322), (30.2586, 120.1325)]

    def test_inside_is_zero(self):
        d = point_to_hull_distance_m((30.2587, 120.1323), self.triangle)
        assert d == pytest.approx(0.0)

    def test_outside_near(self):
        # 三角形上方 ~35m
        d = point_to_hull_distance_m((30.2590, 120.1325), self.triangle)
        assert 20 < d < 60

    def test_outside_far(self):
        d = point_to_hull_distance_m((31.0, 121.0), self.triangle)
        assert d > 100_000  # 100+ km


# ═════════════════════════════════════════════════════════════════
# Buffer 公式
# ═════════════════════════════════════════════════════════════════

class TestBufferFormula:
    def test_n_1_returns_base(self):
        assert compute_buffer_m(1, base_m=50, alpha=0.6) == pytest.approx(50.0)

    def test_n_3_halves_roughly(self):
        # n=3: 50 / (1 + 0.6 × ln 3) ≈ 50 / 1.659 ≈ 30.1m
        assert compute_buffer_m(3, base_m=50, alpha=0.6) == pytest.approx(30.14, abs=0.5)

    def test_n_10_about_quarter(self):
        # n=10: 50 / (1 + 0.6 × ln 10) ≈ 50 / 2.381 ≈ 21m
        assert compute_buffer_m(10, base_m=50, alpha=0.6) == pytest.approx(21.0, abs=1.0)

    def test_monotone_decreasing(self):
        prev = compute_buffer_m(1, 50, 0.6)
        for n in [2, 3, 5, 10, 30]:
            cur = compute_buffer_m(n, 50, 0.6)
            assert cur < prev
            prev = cur

    def test_never_zero(self):
        # 即使 n=1000, buffer 仍 > 0
        b = compute_buffer_m(1000, 50, 0.6)
        assert b > 0


# ═════════════════════════════════════════════════════════════════
# match_new_photo 三场景
# ═════════════════════════════════════════════════════════════════

def _stub_config() -> dict:
    """匹配函数测试用配置 (避免读 yaml 加快测试).

    ADR-0016 4 档 (市内/省内/国内/国外), supersede ADR-0007.
    """
    return {
        "band_thresholds_4tier": {
            "市内": {"strong_m": 500, "medium_m": 1000, "weak_m": 2000},
            "省内": {"strong_m": 1000, "medium_m": 2000, "weak_m": 4000},
            "国内": {"strong_m": 1500, "medium_m": 3000, "weak_m": 6000},
            "国外": {"strong_m": 2000, "medium_m": 4000, "weak_m": 8000},
        },
        "buffer_4tier": {
            "alpha": 0.6,
            "base_m": {"市内": 250, "省内": 500, "国内": 750, "国外": 1000},
        },
    }


def _stub_cluster(member_n: int = 3, is_low_quality: bool = False) -> Cluster:
    return Cluster(
        cluster_id="c1",
        member_photo_ids=[f"p{i}" for i in range(member_n)],
        convex_hull=[
            (30.2585, 120.1320),
            (30.2588, 120.1322),
            (30.2586, 120.1325),
        ],
        centroid=(30.25863, 120.13223),
        is_low_quality=is_low_quality,
    )


class TestMatchNewPhoto:
    cfg = _stub_config()

    def test_no_gps_returns_none(self):
        anchor = PlaceAnchor(clusters=[_stub_cluster()])
        r = match_new_photo(None, anchor, "市内", self.cfg)
        assert r.band == "none"
        assert r.reason == "no_gps"

    def test_empty_anchor_returns_none(self):
        anchor = PlaceAnchor(clusters=[], outliers=[])
        r = match_new_photo((30.2587, 120.1323), anchor, "市内", self.cfg)
        assert r.band == "none"
        assert r.reason == "empty_anchor"

    def test_inside_hull_strong(self):
        # 点在 hull 内 → effective_d = 0 → strong
        anchor = PlaceAnchor(clusters=[_stub_cluster()])
        r = match_new_photo((30.2587, 120.1323), anchor, "市内", self.cfg)
        assert r.band == "strong"
        assert r.matched_target_type == "cluster"
        assert r.diagnostics["effective_distance_m"] == 0

    def test_outside_hull_with_buffer_still_strong(self):
        # ADR-0007: buffer base=250, n=3 buffer≈151m. 点 hull 外 35m,
        # effective_d = max(0, 35-151) = 0 → strong (unified strong_m=500)
        anchor = PlaceAnchor(clusters=[_stub_cluster(member_n=3)])
        r = match_new_photo((30.2590, 120.1325), anchor, "市内", self.cfg)
        assert r.band == "strong"
        assert r.diagnostics["effective_distance_m"] == 0   # buffer 完全吸收

    def test_far_outside_returns_none(self):
        anchor = PlaceAnchor(clusters=[_stub_cluster()])
        r = match_new_photo((31.0, 121.0), anchor, "市内", self.cfg)
        assert r.band == "none"   # 100+ km, 跨过 unified weak_m=2000m

    def test_outlier_only_uses_point_distance(self):
        # 无簇仅 outlier, 点点距离
        anchor = PlaceAnchor(
            clusters=[],
            outliers=[OutlierPoint(photo_id="o1", gps=(30.2585, 120.1320))],
        )
        r = match_new_photo((30.2587, 120.1323), anchor, "市内", self.cfg)
        assert r.band in ("strong", "medium")  # 距离 ~ 40m, 落 strong
        assert r.matched_target_type == "outlier"
        assert r.matched_target_id == "o1"
        assert r.diagnostics["buffer_m"] == 0   # outlier 不用 buffer

    def test_no_user_context_no_downgrade(self):
        # ADR-0006: user_context=None 时, 跳过低质量判定, 不降档
        # 即使 cluster.is_low_quality 字段为 True 也无效 (字段是占位, 实时判定才生效)
        anchor = PlaceAnchor(clusters=[_stub_cluster(is_low_quality=True)])
        r = match_new_photo((30.2587, 120.1323), anchor, "市内", self.cfg)
        # user_context=None → is_low_quality_place 返回 False → 不降档
        assert r.band == "strong"
        assert r.diagnostics["is_low_quality"] is False
        assert r.diagnostics["low_quality_reason"] == "no_user_context"


class TestStrongEarlyReturn:
    cfg = _stub_config()

    def test_multi_clusters_strong_first_returns_immediately(self):
        cluster_a = _stub_cluster()  # 包含 (30.2587, 120.1323)
        # 第二个簇放远点
        cluster_b = Cluster(
            cluster_id="c2",
            member_photo_ids=["far1", "far2"],
            convex_hull=[(31.0, 121.0), (31.001, 121.001), (31.001, 121.002)],
            centroid=(31.0005, 121.001),
            is_low_quality=False,
        )
        anchor = PlaceAnchor(clusters=[cluster_a, cluster_b])
        r = match_new_photo((30.2587, 120.1323), anchor, "市内", self.cfg)
        assert r.band == "strong"
        assert r.matched_target_id == "c1"   # 命中第一个就早返


# ═════════════════════════════════════════════════════════════════
# build_place_anchor
# ═════════════════════════════════════════════════════════════════

def _mk_l1(pid: str, gps: tuple[float, float] | None, is_hfp: bool = False) -> L1Output:
    from src.contracts.l1_output import ImageFacts, PlaceSignals
    return L1Output(
        photo_id=pid,
        user_id="user_demo",
        individual_title="t",
        individual_understanding="x" * 70,
        image_facts=ImageFacts(exif_location=gps) if gps else ImageFacts(),
        place_signals=PlaceSignals(is_high_frequency_place=is_hfp),
    )


class TestBuildPlaceAnchor:
    def test_three_close_photos_form_one_cluster(self):
        photos = [
            _mk_l1("p1", (30.2585, 120.1320)),
            _mk_l1("p2", (30.2588, 120.1322)),
            _mk_l1("p3", (30.2586, 120.1325)),
        ]
        anchor = build_place_anchor(photos, "市内")
        assert len(anchor.clusters) == 1
        assert len(anchor.outliers) == 0
        assert set(anchor.clusters[0].member_photo_ids) == {"p1", "p2", "p3"}

    def test_outlier_kept_separate(self):
        photos = [
            _mk_l1("p1", (30.2585, 120.1320)),
            _mk_l1("p2", (30.2588, 120.1322)),
            _mk_l1("p_far", (31.0, 121.0)),  # 离群
        ]
        anchor = build_place_anchor(photos, "市内")
        assert len(anchor.clusters) == 1
        assert len(anchor.outliers) == 1
        assert anchor.outliers[0].photo_id == "p_far"

    def test_no_gps_photo_skipped(self):
        photos = [
            _mk_l1("p1", (30.2585, 120.1320)),
            _mk_l1("p2", (30.2588, 120.1322)),
            _mk_l1("p_nogps", None),
        ]
        anchor = build_place_anchor(photos, "市内")
        # p_nogps 完全不进, 只有 p1+p2 成簇
        all_ids = (
            [pid for c in anchor.clusters for pid in c.member_photo_ids]
            + [o.photo_id for o in anchor.outliers]
        )
        assert "p_nogps" not in all_ids

    def test_build_does_not_vote_is_low_quality(self):
        # ADR-0006: build_place_anchor 不再 vote is_low_quality,
        # 一律设 False; 实际降档由 match 时 is_low_quality_place 实时判定
        photos = [
            _mk_l1("p1", (30.2585, 120.1320), is_hfp=True),
            _mk_l1("p2", (30.2588, 120.1322), is_hfp=True),
            _mk_l1("p3", (30.2586, 120.1325), is_hfp=False),
        ]
        anchor = build_place_anchor(photos, "市内")
        assert anchor.clusters[0].is_low_quality is False    # 占位, 不是预存
        assert anchor.is_high_frequency_anchor is False       # 兼容字段
