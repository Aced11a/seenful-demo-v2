"""动态生长 4 维特征 (路径 A · Step 2).

参考:
  docs/04_truth_table_growth.md §维度计算
  docs/10_mini_album_schema.md (place_anchor DBCH 算法)
  docs/14_theme_aggregation.md (theme 语义簇算法, ADR-0008)
  decisions/0005-place-anchor-dbch.md
  decisions/0008-theme-semantic-clustering.md
"""
from __future__ import annotations

from src.contracts import (
    EventMatchResult,
    GrowthFeatures,
    L1Output,
    MatchResult,
    MiniAlbumFingerprint,
    ThemeMatchResult,
)
from src.features.theme import jaccard_multi
from src.mini_album.event_aggregation import match_event
from src.mini_album.place_anchor import match_new_photo
from src.mini_album.theme_aggregation import get_embedder, match_theme
from src.mini_album.user_home_city import (
    get_context_for_photo,
    infer_user_home_city,
)
from src.policy.config_loader import load_config

# location_score / theme_overlap_score 派生值 (band → 分数, 仅作展示, 不参与分档)
_BAND_TO_SCORE = {"strong": 1.0, "medium": 0.75, "weak": 0.45, "none": 0.15}


def compute_growth_features(
    new_photo: L1Output,
    album: MiniAlbumFingerprint,
) -> GrowthFeatures:
    """计算新照片 vs 老相册 的 4 维分数 + DBCH / Theme / Event 诊断."""
    location_match = _compute_location_match(new_photo, album)
    theme_match = _compute_theme_match(new_photo, album)
    event_match = _compute_event_match(new_photo, album)
    return GrowthFeatures(
        location_score=_BAND_TO_SCORE[location_match.band],
        theme_overlap_score=_BAND_TO_SCORE[theme_match.band],
        event_similarity_score=_BAND_TO_SCORE[event_match.band],
        anchor_overlap_score=_compute_anchor_overlap(new_photo, album),
        is_high_frequency_place=(
            new_photo.is_high_frequency_place
            or album.place_anchor.is_high_frequency_anchor
        ),
        location_match=location_match,
        theme_match=theme_match,
        event_match=event_match,
    )


def _compute_location_match(
    p: L1Output,
    album: MiniAlbumFingerprint,
) -> MatchResult:
    """DBCH 匹配 (ADR-0005): 新照片 vs 老相册的 PlaceAnchor (簇 + outlier).

    返回 MatchResult 含 band + 诊断. band 直接被 compute_growth_bands 消费.
    """
    user_home = infer_user_home_city(p.user_id)
    context = get_context_for_photo(p.exif_location, user_home)
    cfg = load_config("place_anchor.yaml")
    return match_new_photo(p.exif_location, album.place_anchor, context, cfg)


def _compute_theme_match(
    p: L1Output,
    album: MiniAlbumFingerprint,
) -> ThemeMatchResult:
    """语义簇匹配 (ADR-0008): 新照片 theme_tags vs 老相册 theme_clusters.

    返回 ThemeMatchResult 含 band + score + per_cluster 诊断.
    band 直接被 compute_growth_bands 消费.

    参考: docs/14_theme_aggregation.md §四.
    """
    cfg = load_config("theme_aggregation.yaml")["theme_aggregation"]
    embedder = get_embedder(cfg)
    return match_theme(
        new_tags=p.theme_tags,
        clusters=album.theme_clusters,
        embed_fn=embedder,
        band_thresholds=cfg["band_thresholds"],
    )


def _compute_event_match(
    p: L1Output,
    album: MiniAlbumFingerprint,
) -> EventMatchResult:
    """Event 三级分层匹配 (ADR-0009): 新照片 event_hint vs 老相册 event_agg.

    返回 EventMatchResult 含 band + matched_tier + diagnostics.
    band 直接被 compute_growth_bands 消费.

    参考: docs/15_event_aggregation.md §四.
    """
    return match_event(p.semantic_facts.event_hint, album.event_agg)


def _compute_anchor_overlap(p: L1Output, album: MiniAlbumFingerprint) -> float:
    """新照片 meaning/object anchors 与 album.anchors_set Jaccard 取 max.

    ⚠ 见 OQ-009 §9d: 严格 Jaccard, v0.1 几乎死规则.
    """
    if not album.anchors_set:
        return 0.0
    meaning = jaccard_multi(
        [set(p.meaning_anchors), set(album.anchors_set)]
    ) if p.meaning_anchors else 0.0
    obj = jaccard_multi(
        [set(p.semantic_facts.object_anchors), set(album.anchors_set)]
    ) if p.semantic_facts.object_anchors else 0.0
    return max(meaning, obj)
