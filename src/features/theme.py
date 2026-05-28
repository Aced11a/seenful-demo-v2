"""路径 B Theme 维度 (ADR-0013 + ADR-0023): 双层字段 + MAX-OR + 泛词 stoplist.

参考:
  docs/19_path_b_theme.md
  decisions/0013-path-b-theme-two-tier-cluster.md  (Phase 1-3)
  decisions/0022-th0-multi-parallel-clusters-medium.md  (TH.0)
  decisions/0023-theme-subject-max-or.md  (Phase 4-6: subject single-layer + stoplist cap + MAX)
  config/path_b_theme.yaml

输出: ThemeFeature (含 band 终值 + 完整诊断字段 + dominant_field + subject_*)

⚠ A2 真值表让 theme=强 单独成集, strong 门槛严. MAX-OR 后多 1 个 strong 入口:
   theme_band=strong  (Phase 3 完成)
   subject_band=strong (Phase 4 完成, 无 stoplist 命中)

⚠ 复用 _two_tier_cluster 通用工具 (anchor/emotional 共享同工具, 各自 rule_prefix).
"""
from __future__ import annotations

from src.contracts import L1Output, ThemeFeature, ThemeShape
from src.contracts.features import BandLevel
from src.policy.config_loader import load_config

from ._two_tier_cluster import TwoTierResult, build_two_tier_feature


# ─── 向后兼容: jaccard_multi 工具 ───────────────────────────
# 被 src/candidate_builder/backfill_scan.py + src/features/growth_features.py 引用


def jaccard_multi(sets: list[set]) -> float:
    """多集合 Jaccard = |交集| / |并集|. 空输入 → 0.0.

    保留为公共工具 (path A growth_features + path C backfill_scan 仍依赖).
    Path B theme/anchor 已升级到 ADR-0013/0014 语义簇, 不用此函数.
    """
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0
    intersection = set.intersection(*sets)
    union = set.union(*sets)
    if not union:
        return 0.0
    return len(intersection) / len(union)


# ─── shape_code → ThemeShape 映射 ────────────────────────────


_SHAPE_MAP: dict[str, ThemeShape] = {
    "TH.0": ThemeShape.MULTI_PARALLEL_CLUSTERS,         # ADR-0022 v0.10
    "TH.1": ThemeShape.FULL_COVERAGE_THEMED,
    "TH.2": ThemeShape.DOMINANT_THEMED,
    "TH.3": ThemeShape.PARTIAL_THEMED,
    "TH.4": ThemeShape.NO_DOMINANT_THEME,
    "TH.5": ThemeShape.NO_THEME_SIGNAL,
}


_BAND_ORDER: dict[BandLevel, int] = {"none": 0, "weak": 1, "medium": 2, "strong": 3}


def _band_to_score(band: str) -> float:
    return {"strong": 0.9, "medium": 0.7, "weak": 0.4, "none": 0.1}[band]


# ─── 字段抽取器 ──────────────────────────────────────────────


def _theme_primary_extractor(p: L1Output) -> list[str]:
    """主字段: theme_tags."""
    return list(p.theme_tags)


def _theme_secondary_extractor(p: L1Output) -> list[str]:
    """次字段: semantic_facts.main_subjects."""
    return list(p.semantic_facts.main_subjects)


# ─── ADR-0023 helpers ──────────────────────────────────────


def _detect_stoplist_hits(
    clusters: list[list[str]],
    stoplist: set[str],
) -> list[str]:
    """返回主簇中命中 stoplist 的所有词 (去重保序)."""
    hits: list[str] = []
    seen: set[str] = set()
    for cluster in clusters:
        for tag in cluster:
            if tag in stoplist and tag not in seen:
                hits.append(tag)
                seen.add(tag)
    return hits


def _cap_band(band: BandLevel, ceiling: BandLevel) -> BandLevel:
    """band 不能超过 ceiling (序数比较)."""
    if _BAND_ORDER[band] > _BAND_ORDER[ceiling]:
        return ceiling
    return band


# ─── 高层入口 ────────────────────────────────────────────────


def build_theme_feature(photos: list[L1Output]) -> ThemeFeature:
    """从 photos 构造 ThemeFeature (ADR-0013 + ADR-0023).

    流水线 (docs/19 §2.1):
      Phase 1-2: 主字段 (theme_tags) 聚类 + 主 band 6 行 grid (TH.0~TH.5)
      Phase 3: TH.2/TH.3 触发次字段升降档 → theme_band (老逻辑保留)
      Phase 4: subject single-layer 跑 main_subjects (5 行 TH.1~TH.5, 无 TH.0)
      Phase 5: stoplist cap medium (主簇任一成员命中泛词)
      Phase 6: MAX(theme_band, subject_band), 同档取 theme
    """
    cfg = load_config("path_b_theme.yaml")["path_b_theme"]

    stoplist = set(cfg.get("subject_stopword_blocklist", []))

    # ─── Phase 1-3: 老逻辑 (theme 主 + secondary 升降) ─────────
    theme_result: TwoTierResult = build_two_tier_feature(
        photos=photos,
        primary_extractor=_theme_primary_extractor,
        secondary_extractor=_theme_secondary_extractor,
        cfg=cfg,
        rule_prefix="TH",
        enable_th0_multi_parallel=True,
    )
    # ADR-0023 Phase 3 stoplist 兜底: 老 secondary_boost 不能被泛词触发
    # (eg. theme=[lake×4,urban×1] TH.2 + secondary=[person×5] 老会 boost strong)
    if theme_result.secondary_action == "boost":
        sec_hits = _detect_stoplist_hits(theme_result.secondary_theme_clusters, stoplist)
        if sec_hits:
            # 撤销 boost, 退回 shape_code 对应的 band
            theme_result.band = "medium"
            theme_result.rule_fired = f"{theme_result.shape_code}+stopword_phase3_cap"
            theme_result.secondary_action = "none"
    theme_band: BandLevel = theme_result.band
    theme_rule = theme_result.rule_fired

    # ─── Phase 4: subject single-layer (不启 TH.0, 不查次) ─────
    subject_result: TwoTierResult = build_two_tier_feature(
        photos=photos,
        primary_extractor=_theme_secondary_extractor,  # main_subjects 当主跑
        secondary_extractor=lambda p: [],
        cfg=cfg,
        rule_prefix="TH",
        enable_secondary=False,
        enable_th0_multi_parallel=False,
    )
    subject_band: BandLevel = subject_result.band
    subject_rule = subject_result.rule_fired

    # ─── Phase 5: stoplist cap ──────────────────────────────────
    stoplist = set(cfg.get("subject_stopword_blocklist", []))
    stoplist_hits = _detect_stoplist_hits(subject_result.primary_theme_clusters, stoplist)
    subject_stoplist_capped = bool(stoplist_hits)
    if subject_stoplist_capped:
        subject_band = _cap_band(subject_band, "medium")
        if "+stopword_cap" not in subject_rule:
            subject_rule = f"{subject_rule}+stopword_cap"

    # ─── Phase 6: MAX-OR ────────────────────────────────────────
    if _BAND_ORDER[subject_band] > _BAND_ORDER[theme_band]:
        final_band: BandLevel = subject_band
        dominant_field = "subject"
        final_rule_fired = f"{subject_rule}.subject"
        # subject 赢: shape 用 subject 的 (FULL_COVERAGE_THEMED / DOMINANT_THEMED 等)
        final_shape = _SHAPE_MAP[_strip_suffix(subject_rule)]
    else:
        final_band = theme_band
        dominant_field = "theme"
        final_rule_fired = theme_rule
        final_shape = _SHAPE_MAP[theme_result.shape_code]

    return ThemeFeature(
        band=final_band,
        rule_fired=final_rule_fired,
        score=_band_to_score(final_band),
        total_photos=theme_result.total_photos,
        valid_photo_count=theme_result.valid_photo_count,
        primary_tag_pool_size=theme_result.primary_tag_pool_size,
        primary_cluster_count=theme_result.primary_cluster_count,
        primary_theme_clusters=theme_result.primary_theme_clusters,
        primary_hit_rates=theme_result.primary_hit_rates,
        primary_coverage=theme_result.primary_coverage,
        primary_outlier_ids=theme_result.primary_outlier_ids,
        secondary_tag_pool_size=theme_result.secondary_tag_pool_size,
        secondary_cluster_count=theme_result.secondary_cluster_count,
        secondary_theme_clusters=theme_result.secondary_theme_clusters,
        secondary_hit_rates=theme_result.secondary_hit_rates,
        secondary_coverage=theme_result.secondary_coverage,
        secondary_action=theme_result.secondary_action,
        # ADR-0023 新字段
        theme_band=theme_band,
        subject_band=subject_band,
        subject_coverage=subject_result.primary_coverage,
        subject_cluster_count=subject_result.primary_cluster_count,
        subject_theme_clusters=subject_result.primary_theme_clusters,
        subject_hit_rates=subject_result.primary_hit_rates,
        subject_stoplist_capped=subject_stoplist_capped,
        subject_stoplist_hits=stoplist_hits,
        dominant_field=dominant_field,
        shape=final_shape,
    )


def _strip_suffix(rule: str) -> str:
    """从 'TH.1+stopword_cap' / 'TH.2+secondary_boost' 抠出主码 'TH.1' / 'TH.2'."""
    return rule.split("+", 1)[0]
