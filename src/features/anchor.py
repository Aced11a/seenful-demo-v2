"""路径 B Anchor 维度 (ADR-0014): 双层字段判定 (主 meaning + 次 object).

参考:
  docs/20_path_b_anchor.md
  decisions/0014-path-b-anchor-two-tier-cluster.md
  config/path_b_anchor.yaml

输出: AnchorFeature (含 band 终值 + 完整诊断字段)

⚠ 复用 ADR-0013 _two_tier_cluster 通用工具.
⚠ v0.3 修订 OQ-008 §8e: 不再合并 meaning + object set, 改主次分层.
"""
from __future__ import annotations

from src.contracts import AnchorFeature, AnchorShape, L1Output
from src.policy.config_loader import load_config

from ._two_tier_cluster import TwoTierResult, build_two_tier_feature


# ─── shape_code → AnchorShape 映射 ───────────────────────────


_SHAPE_MAP: dict[str, AnchorShape] = {
    "AN.1": AnchorShape.FULL_COVERAGE_ANCHORED,
    "AN.2": AnchorShape.DOMINANT_ANCHORED,
    "AN.3": AnchorShape.PARTIAL_ANCHORED,
    "AN.4": AnchorShape.NO_DOMINANT_ANCHOR,
    "AN.5": AnchorShape.NO_ANCHOR_SIGNAL,
}


def _band_to_score(band: str) -> float:
    return {"strong": 0.9, "medium": 0.7, "weak": 0.4, "none": 0.1}[band]


# ─── 字段抽取器 ──────────────────────────────────────────────


def _anchor_primary_extractor(p: L1Output) -> list[str]:
    """主字段: meaning_anchors."""
    return list(p.meaning_anchors)


def _anchor_secondary_extractor(p: L1Output) -> list[str]:
    """次字段: semantic_facts.object_anchors."""
    return list(p.semantic_facts.object_anchors)


# ─── 高层入口 ────────────────────────────────────────────────


def build_anchor_feature(photos: list[L1Output]) -> AnchorFeature:
    """从 photos 构造 AnchorFeature (ADR-0014 直出 band).

    流水线 (docs/20 §2.1):
      Phase 1: 主字段 (meaning_anchors) 聚类 → primary_coverage
      Phase 2: 主 band 判定 (5 行 grid AN.1~AN.5)
      Phase 3: 仅 AN.2/AN.3 → 次字段 (object_anchors) 升降档
    """
    cfg = load_config("path_b_anchor.yaml")["path_b_anchor"]

    result: TwoTierResult = build_two_tier_feature(
        photos=photos,
        primary_extractor=_anchor_primary_extractor,
        secondary_extractor=_anchor_secondary_extractor,
        cfg=cfg,
        rule_prefix="AN",
    )

    shape = _SHAPE_MAP[result.shape_code]

    return AnchorFeature(
        band=result.band,
        rule_fired=result.rule_fired,
        score=_band_to_score(result.band),
        total_photos=result.total_photos,
        valid_photo_count=result.valid_photo_count,
        primary_tag_pool_size=result.primary_tag_pool_size,
        primary_cluster_count=result.primary_cluster_count,
        primary_anchor_clusters=result.primary_theme_clusters,  # 通用结构, 命名映射
        primary_hit_rates=result.primary_hit_rates,
        primary_coverage=result.primary_coverage,
        primary_outlier_ids=result.primary_outlier_ids,
        secondary_tag_pool_size=result.secondary_tag_pool_size,
        secondary_cluster_count=result.secondary_cluster_count,
        secondary_anchor_clusters=result.secondary_theme_clusters,
        secondary_hit_rates=result.secondary_hit_rates,
        secondary_coverage=result.secondary_coverage,
        secondary_action=result.secondary_action,
        shape=shape,
    )
