"""growth_features 单测."""
from __future__ import annotations

from datetime import datetime, timezone

from src.contracts import (
    Cluster,
    L1Output,
    MiniAlbumFingerprint,
    OutlierPoint,
    PlaceAnchor,
)
from src.contracts.l1_output import ImageFacts, SemanticFacts
from src.features.growth_features import compute_growth_features
from src.mini_album.theme_aggregation import (
    aggregate_theme_clusters,
    get_embedder,
    truncate_by_relative_threshold,
)
from src.policy.config_loader import load_config

# 用 yaml 配置的 embedder, 保持与生产 compute_growth_features 一致 (dim 一致)
_TEST_CFG = load_config("theme_aggregation.yaml")["theme_aggregation"]
_TEST_EMBEDDER = get_embedder(_TEST_CFG)


def _build_test_clusters(tags: list[str]):
    """从 tag 列表构造测试用 theme_clusters (mock embedder, 与生产同 dim)."""
    raw = aggregate_theme_clusters(
        tags, _TEST_EMBEDDER,
        merge_similarity=float(_TEST_CFG["merge_similarity"]),
    )
    return truncate_by_relative_threshold(
        raw,
        max_keep=int(_TEST_CFG["max_clusters"]),
        relative_threshold=float(_TEST_CFG["relative_threshold"]),
    )


def mk_album(
    cluster_hull: list[tuple[float, float]] | None = None,
    cluster_member_ids: list[str] | None = None,
    outliers: list[tuple[str, tuple[float, float]]] | None = None,
    is_hfp: bool = False,
    theme_tags: list[str] | None = None,
    dominant_event: str = "outing",
    anchors: list[str] | None = None,
) -> MiniAlbumFingerprint:
    """构造测试用 album fingerprint (DBCH + theme clusters + event_agg).

    默认: 一个西湖区域 cluster + 无 outlier.
    dominant_event 参数: 作为 event_agg.primary (默认 outing); 传 "unknown" → 空 agg.
    """
    if cluster_hull is None:
        cluster_hull = [
            (30.2585, 120.1320),
            (30.2588, 120.1322),
            (30.2586, 120.1325),
        ]
    if cluster_member_ids is None:
        cluster_member_ids = ["p1", "p2", "p3"]
    clusters: list[Cluster] = []
    if cluster_hull:
        clusters.append(Cluster(
            cluster_id="c_test",
            member_photo_ids=cluster_member_ids,
            convex_hull=cluster_hull,
            centroid=(
                sum(p[0] for p in cluster_hull) / len(cluster_hull),
                sum(p[1] for p in cluster_hull) / len(cluster_hull),
            ),
            is_low_quality=is_hfp,
        ))
    outlier_objs = [OutlierPoint(photo_id=pid, gps=gps) for pid, gps in (outliers or [])]

    # event_agg: 占位 — dominant_event 参数 → primary, 空 unknown → empty agg
    from src.contracts import EventAggregation
    if dominant_event == "unknown":
        event_agg = EventAggregation(
            primary=None, secondary=[], tertiary=[], distribution={}, total_events=0,
        )
    else:
        event_agg = EventAggregation(
            primary=dominant_event,
            secondary=[],
            tertiary=[],
            distribution={dominant_event: 3},
            total_events=3,
        )

    return MiniAlbumFingerprint(
        mini_album_id="ma_test",
        user_id="user_demo",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        last_updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        growth_lock_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        place_anchor=PlaceAnchor(
            clusters=clusters,
            outliers=outlier_objs,
            is_high_frequency_anchor=is_hfp,
        ),
        theme_clusters=_build_test_clusters(theme_tags or ["lakeside", "spring"]),
        theme_aggregated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        event_agg=event_agg,
        event_aggregated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        anchors_set=anchors or ["夕阳", "湖面"],
    )


def mk_photo(
    gps: tuple[float, float] | None = (30.2590, 120.1325),
    theme_tags: list[str] | None = None,
    event_hint: str = "outing",
    meaning_anchors: list[str] | None = None,
    is_hfp: bool = False,
) -> L1Output:
    from src.contracts.l1_output import PlaceSignals
    # 区分 None vs 空列表: None → 默认, [] → 空
    final_tags = theme_tags if theme_tags is not None else ["lakeside", "sunset"]
    final_anchors = meaning_anchors if meaning_anchors is not None else ["夕阳", "湖面"]
    return L1Output(
        photo_id="p_test",
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        theme_tags=final_tags,
        meaning_anchors=final_anchors,
        image_facts=ImageFacts(exif_location=gps) if gps else ImageFacts(),
        place_signals=PlaceSignals(is_high_frequency_place=is_hfp),
        semantic_facts=SemanticFacts(event_hint=event_hint),  # type: ignore[arg-type]
    )


class TestLocation:
    def test_near_album_inside_hull_strong(self):
        # 默认 p_test gps=(30.2590, 120.1325) 在 hull 外但 raw_d ≈ 35m, buffer ≈ 30m
        # effective_d ≈ 5m ≤ 100m (home_city strong)
        gf = compute_growth_features(mk_photo(), mk_album())
        assert gf.location_match is not None
        assert gf.location_match.band == "strong"
        assert gf.location_score == 1.0

    def test_no_gps_band_none(self):
        gf = compute_growth_features(mk_photo(gps=None), mk_album())
        assert gf.location_match is not None
        assert gf.location_match.band == "none"
        assert gf.location_match.reason == "no_gps"

    def test_high_frequency_flag(self):
        gf = compute_growth_features(mk_photo(is_hfp=True), mk_album())
        assert gf.is_high_frequency_place is True


class TestThemeOverlap:
    """ADR-0008: theme_match.band 直接消费, theme_overlap_score 仅作派生展示值."""

    def test_strong_match(self):
        # album 全是 lakeside 同义簇; 新照片同样命中 → strong
        gf = compute_growth_features(
            mk_photo(theme_tags=["lakeside", "湖面"]),
            mk_album(theme_tags=["lakeside", "湖边", "湖水"]),
        )
        assert gf.theme_match is not None
        assert gf.theme_match.band == "strong"
        assert gf.theme_overlap_score == 1.0   # band=strong → 派生 1.0

    def test_unrelated_tags_none(self):
        # 新 tag 与 album 簇语义无关 (走 hash, cosine 大概率低)
        gf = compute_growth_features(
            mk_photo(theme_tags=["zzz_unknown1", "zzz_unknown2"]),
            mk_album(theme_tags=["lakeside", "湖边", "湖水"]),
        )
        assert gf.theme_match is not None
        assert gf.theme_match.band == "none"

    def test_empty_new_tags_returns_none(self):
        gf = compute_growth_features(
            mk_photo(theme_tags=[]),
            mk_album(theme_tags=["lakeside"]),
        )
        assert gf.theme_match is not None
        assert gf.theme_match.band == "none"
        assert gf.theme_match.reason == "no_tags"

    def test_empty_clusters_returns_none(self):
        # 老相册 theme_clusters 为空 (理论上聚合后至少有 1 个, 但兜底)
        album = mk_album(theme_tags=["lakeside"])
        album.theme_clusters = []   # 手动清空模拟边界
        gf = compute_growth_features(
            mk_photo(theme_tags=["lakeside"]),
            album,
        )
        assert gf.theme_match is not None
        assert gf.theme_match.band == "none"
        assert gf.theme_match.reason == "empty_clusters"


class TestEventMatch:
    """ADR-0009: event_match.band 直接消费, event_similarity_score 仅作派生展示值."""

    def test_primary_hit_strong(self):
        # 新 event 命中 primary → strong
        gf = compute_growth_features(
            mk_photo(event_hint="outing"),
            mk_album(dominant_event="outing"),
        )
        assert gf.event_match is not None
        assert gf.event_match.band == "strong"
        assert gf.event_match.matched_tier == "primary"
        assert gf.event_similarity_score == 1.0   # 派生

    def test_unrelated_event_none(self):
        # 新 event 完全不在 agg → none
        gf = compute_growth_features(
            mk_photo(event_hint="meal"),
            mk_album(dominant_event="outing"),
        )
        assert gf.event_match is not None
        assert gf.event_match.band == "none"
        assert gf.event_match.matched_tier == "none"

    def test_unknown_event_returns_none(self):
        # 新 event=unknown → none + reason
        gf = compute_growth_features(
            mk_photo(event_hint="unknown"),
            mk_album(dominant_event="outing"),
        )
        assert gf.event_match is not None
        assert gf.event_match.band == "none"
        assert gf.event_match.reason == "unknown_event"

    def test_empty_aggregation_returns_none(self):
        # 老相册 event_agg 空 (全 unknown) → none + reason
        gf = compute_growth_features(
            mk_photo(event_hint="outing"),
            mk_album(dominant_event="unknown"),   # → 空 agg
        )
        assert gf.event_match is not None
        assert gf.event_match.band == "none"
        assert gf.event_match.reason == "empty_aggregation"


class TestAnchorOverlap:
    def test_full_overlap(self):
        gf = compute_growth_features(
            mk_photo(meaning_anchors=["夕阳", "湖面"]),
            mk_album(anchors=["夕阳", "湖面"]),
        )
        assert gf.anchor_overlap_score == 1.0
