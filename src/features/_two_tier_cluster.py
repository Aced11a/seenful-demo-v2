"""路径 B 双层字段判定通用工具 (ADR-0013 / ADR-0014).

参考:
  docs/19_path_b_theme.md (theme 应用)
  docs/20_path_b_anchor.md (anchor 应用)
  decisions/0013-path-b-theme-two-tier-cluster.md
  decisions/0014-path-b-anchor-two-tier-cluster.md

提供:
  · TwoTierResult           — 中性数据结构 (theme/anchor 各自映射成 Feature)
  · build_two_tier_feature  — 通用入口, primary/secondary extractor 注入

依赖:
  · ADR-0008 MockEmbedder + agglomerative_cluster_cosine (路径 A 已实现, 复用)
  · 配置 cluster.merge_similarity 来自 config/theme_aggregation.yaml
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from src.contracts import BandLevel, L1Output
from src.mini_album.theme_aggregation import (
    agglomerative_cluster_cosine,
    get_embedder,
)
from src.policy.config_loader import load_config


# ─── 中性结果数据结构 ────────────────────────────────────────


@dataclass
class TwoTierResult:
    """双层判定通用输出.

    上层 (theme / anchor) 各自映射成 ThemeFeature / AnchorFeature.
    """

    band: BandLevel
    rule_fired: str                                  # "TH.1" / "AN.2+secondary_boost" 等

    # ─── 主字段诊断 ───────────────────────────────────────
    total_photos: int
    valid_photo_count: int
    primary_tag_pool_size: int
    primary_cluster_count: int
    primary_theme_clusters: list[list[str]] = field(default_factory=list)  # 过阈值主题簇 tags
    primary_hit_rates: list[float] = field(default_factory=list)
    primary_coverage: float = 0.0
    primary_outlier_ids: list[str] = field(default_factory=list)

    # ─── 次字段诊断 (仅 medium 段计算) ─────────────────────
    secondary_tag_pool_size: int | None = None
    secondary_cluster_count: int | None = None
    secondary_theme_clusters: list[list[str]] = field(default_factory=list)
    secondary_hit_rates: list[float] = field(default_factory=list)
    secondary_coverage: float | None = None
    secondary_action: str = "none"                  # "none" | "boost" | "demote"

    # ─── 落痕标识 ───────────────────────────────────────────
    shape_code: str = ""                            # "TH.1" / "AN.2" etc, 主路径码 (无后缀)


# ─── 核心算法 ────────────────────────────────────────────────


def _cluster_tags(
    tags: list[str],
    embed_fn: Callable[[list[str]], list[list[float]]],
    merge_similarity: float,
) -> list[list[str]]:
    """对 tag 列表做层次聚类, 返回 list of clusters (每个 cluster 是 tag list).

    去重 + embed + cluster.
    """
    unique_tags = list(dict.fromkeys(tags))  # 保序去重
    if not unique_tags:
        return []
    embeddings = embed_fn(unique_tags)
    labels = agglomerative_cluster_cosine(
        embeddings,
        distance_threshold=1.0 - merge_similarity,
    )
    buckets: dict[int, list[str]] = {}
    for idx, lab in enumerate(labels):
        buckets.setdefault(lab, []).append(unique_tags[idx])
    return list(buckets.values())


def _compute_hit_rates(
    clusters: list[list[str]],
    photos: list[L1Output],
    extractor: Callable[[L1Output], list[str]],
    n: int,
) -> tuple[list[float], list[set[str]]]:
    """对每个 cluster 算 hit_rate + 关联 photo_id set.

    photo 命中 cluster = photo 的 tags 至少有一个在 cluster 内.
    """
    hit_rates: list[float] = []
    member_photos: list[set[str]] = []
    for cluster_tags in clusters:
        cluster_set = set(cluster_tags)
        hits = set()
        for p in photos:
            if any(t in cluster_set for t in extractor(p)):
                hits.add(p.photo_id)
        hit_rates.append(len(hits) / n if n > 0 else 0.0)
        member_photos.append(hits)
    return hit_rates, member_photos


def _filter_theme_clusters(
    clusters: list[list[str]],
    hit_rates: list[float],
    member_photos: list[set[str]],
    hit_rate_threshold: float,
    min_hit_count: int,
    n: int,
    top_k: int | None = None,
) -> tuple[list[list[str]], list[float], list[set[str]]]:
    """过滤出主题簇.

    两种模式:
    - top_k=None (anchor/emotional 现行): hit_rate ≥ threshold AND hit_count ≥ min_hit_count
    - top_k=int (theme ADR-0024): hit_count ≥ min_hit_count → 候选, 取 Top-K by hit_count
    """
    if top_k is None:
        # 老逻辑 (anchor/emotional): hit_rate + min_hit_count 双重过滤
        out_clusters: list[list[str]] = []
        out_rates: list[float] = []
        out_members: list[set[str]] = []
        for c, r, m in zip(clusters, hit_rates, member_photos):
            if r >= hit_rate_threshold and len(m) >= min_hit_count:
                out_clusters.append(c)
                out_rates.append(r)
                out_members.append(m)
        return out_clusters, out_rates, out_members

    # ADR-0024 Top-K (theme): hit_count ≥ min_hit_count → 候选, 取 Top-K by hit_count
    candidates = [
        (c, r, m)
        for c, r, m in zip(clusters, hit_rates, member_photos)
        if len(m) >= min_hit_count
    ]
    candidates.sort(key=lambda x: (-len(x[2]), -x[1]))
    top = candidates[:top_k]
    return (
        [c for c, _, _ in top],
        [r for _, r, _ in top],
        [m for _, _, m in top],
    )


def _compute_coverage(
    theme_member_photos: list[set[str]],
    n: int,
) -> tuple[float, set[str]]:
    """coverage = |⋃ theme_member_photos| / n."""
    covered: set[str] = set()
    for m in theme_member_photos:
        covered |= m
    return (len(covered) / n if n > 0 else 0.0, covered)


def _band_to_score(band: BandLevel) -> float:
    """跟 ADR-0010/0011/0012 派生 score 规则一致."""
    return {"strong": 0.9, "medium": 0.7, "weak": 0.4, "none": 0.1}[band]


# ─── 主流程 ─────────────────────────────────────────────────


def build_two_tier_feature(
    photos: list[L1Output],
    primary_extractor: Callable[[L1Output], list[str]],
    secondary_extractor: Callable[[L1Output], list[str]],
    cfg: dict,
    rule_prefix: str,
    enable_secondary: bool = True,
    enable_th0_multi_parallel: bool = False,
) -> TwoTierResult:
    """双层字段判定通用入口.

    Args:
      photos: 输入照片列表
      primary_extractor: 抽主字段 tags (例 lambda p: list(p.theme_tags))
      secondary_extractor: 抽次字段 tags (theme/anchor 用; emotional 传空 lambda)
      cfg: path_b_theme.yaml / path_b_anchor.yaml / path_b_emotional.yaml 下钻段
      rule_prefix: "TH" / "AN" / "EM" (主路径码前缀)
      enable_secondary: True (theme/anchor 默认双层); False (emotional 单层, 跳过 Phase 3)

    Returns:
      TwoTierResult (中性结构, 上层映射成 Feature)

    ADR-0015 加 enable_secondary 参数: emotional 单层 (无次字段), 仅跑 Phase 1-2.
    """
    n = len(photos)

    # ─── 边界: N < 2 → none ─────────────────────────────
    if n < 2:
        return TwoTierResult(
            band="none",
            rule_fired=f"{rule_prefix}.5",
            total_photos=n,
            valid_photo_count=0,
            primary_tag_pool_size=0,
            primary_cluster_count=0,
            shape_code=f"{rule_prefix}.5",
        )

    # 读 config 阈值
    primary_threshold = float(cfg["primary_hit_rate_threshold"])
    min_hit_count = int(cfg["min_hit_count"])
    bt = cfg["primary_band_thresholds"]
    strong_cov = float(bt["strong_coverage"])
    medium_high = float(bt["medium_high"])
    medium_low = float(bt["medium_low"])
    # secondary 配置仅 enable_secondary=True 时读 (emotional 单层不需要)
    if enable_secondary:
        adj = cfg["secondary_band_adjust"]
        boost_threshold = float(adj["boost_threshold"])
        demote_threshold = float(adj["demote_threshold"])
    else:
        boost_threshold = 1.0  # 占位, 不会用到
        demote_threshold = 0.0
    n_valid_min = int(cfg["fallback"]["n_valid_min"])

    # 复用 ADR-0008 MockEmbedder + merge_similarity
    theme_cfg = load_config("theme_aggregation.yaml")["theme_aggregation"]
    embedder = get_embedder(theme_cfg)
    merge_similarity = float(theme_cfg["merge_similarity"])

    # ─── Phase 1 · 主字段聚类 ──────────────────────────
    primary_tags_per_photo = [primary_extractor(p) for p in photos]
    valid_photo_count = sum(1 for ts in primary_tags_per_photo if ts)

    # 边界: N_valid ≤ 阈值 → none
    if valid_photo_count <= n_valid_min - 1:  # n_valid_min=1 → N_valid ≤ 0 → none
        # 严格按 spec: N_valid ≤ 1 → none (即 N_valid ≤ n_valid_min)
        pass
    if valid_photo_count <= n_valid_min:
        return TwoTierResult(
            band="none",
            rule_fired=f"{rule_prefix}.5",
            total_photos=n,
            valid_photo_count=valid_photo_count,
            primary_tag_pool_size=0,
            primary_cluster_count=0,
            shape_code=f"{rule_prefix}.5",
        )

    primary_tag_pool = []
    for ts in primary_tags_per_photo:
        primary_tag_pool.extend(ts)
    primary_clusters = _cluster_tags(primary_tag_pool, embedder, merge_similarity)
    primary_hit_rates, primary_members = _compute_hit_rates(
        primary_clusters, photos, primary_extractor, n
    )
    # ADR-0024: theme 启 Top-K (cfg.top_k_clusters=3), anchor/emotional 不传 → 走老 hit_rate 过滤
    top_k_cfg = cfg.get("top_k_clusters")
    top_k = int(top_k_cfg) if top_k_cfg is not None else None
    primary_theme_clusters, primary_theme_rates, primary_theme_members = _filter_theme_clusters(
        primary_clusters, primary_hit_rates, primary_members,
        primary_threshold, min_hit_count, n, top_k=top_k,
    )
    primary_coverage, primary_covered = _compute_coverage(primary_theme_members, n)
    primary_outliers = sorted(
        p.photo_id for p in photos if p.photo_id not in primary_covered
    )

    # ─── Phase 2 · 主 band 判定 (ADR-0022 加 TH.0 仅 theme 用, 6 行 grid) ───
    # TH.0 (多簇各覆盖不同子集) 优先 → TH.1 (单簇 OR 多簇同覆盖全集) → TH.2 → TH.3 → TH.4
    th0_min_clusters = int(cfg.get("th0_min_cluster_count", 2))
    primary_cluster_count = len(primary_theme_clusters)
    # 关键: TH.0 要求多个簇**各覆盖不同子集** (即每簇 hit_rate < 1.0).
    # ADR-0022: 仅 theme 启用 (enable_th0_multi_parallel=True); anchor/emotional 不区分
    multi_parallel = (
        enable_th0_multi_parallel
        and primary_cluster_count >= th0_min_clusters
        and any(rate < 1.0 for rate in primary_theme_rates)
    )
    triggers_secondary = False
    if primary_coverage >= strong_cov and multi_parallel:
        # TH.0: 多并列主簇覆盖 100% (各占不同子集) → medium (mixed type)
        band: BandLevel = "medium"
        shape_code = f"{rule_prefix}.0"
    elif primary_coverage >= strong_cov:
        # TH.1: 单簇 OR 多簇都全覆盖 (同主题不同 tag) → strong
        band = "strong"
        shape_code = f"{rule_prefix}.1"
    elif primary_coverage >= medium_high:
        band = "medium"
        shape_code = f"{rule_prefix}.2"
        triggers_secondary = True
    elif primary_coverage >= medium_low:
        band = "medium"
        shape_code = f"{rule_prefix}.3"
        triggers_secondary = True
    else:
        # < medium_low OR 无 theme_clusters
        band = "weak"
        shape_code = f"{rule_prefix}.4"

    rule_fired = shape_code

    result = TwoTierResult(
        band=band,
        rule_fired=rule_fired,
        total_photos=n,
        valid_photo_count=valid_photo_count,
        primary_tag_pool_size=len(set(primary_tag_pool)),
        primary_cluster_count=len(primary_clusters),
        primary_theme_clusters=primary_theme_clusters,
        primary_hit_rates=primary_theme_rates,
        primary_coverage=primary_coverage,
        primary_outlier_ids=primary_outliers,
        shape_code=shape_code,
    )

    # ─── Phase 3 · 次字段升降档 (仅 TH.2/TH.3 AND enable_secondary) ──
    if triggers_secondary and enable_secondary:
        secondary_tags_per_photo = [secondary_extractor(p) for p in photos]
        secondary_tag_pool = []
        for ts in secondary_tags_per_photo:
            secondary_tag_pool.extend(ts)
        secondary_clusters = _cluster_tags(secondary_tag_pool, embedder, merge_similarity)
        secondary_hit_rates, secondary_members = _compute_hit_rates(
            secondary_clusters, photos, secondary_extractor, n
        )
        secondary_theme_clusters, secondary_theme_rates, secondary_theme_members = _filter_theme_clusters(
            secondary_clusters, secondary_hit_rates, secondary_members,
            primary_threshold, min_hit_count, n, top_k=top_k,  # ADR-0024 Top-K
        )
        secondary_coverage, _ = _compute_coverage(secondary_theme_members, n)

        result.secondary_tag_pool_size = len(set(secondary_tag_pool))
        result.secondary_cluster_count = len(secondary_clusters)
        result.secondary_theme_clusters = secondary_theme_clusters
        result.secondary_hit_rates = secondary_theme_rates
        result.secondary_coverage = secondary_coverage

        # 升降档
        if secondary_coverage >= boost_threshold:
            result.band = "strong"
            result.rule_fired = f"{shape_code}+secondary_boost"
            result.secondary_action = "boost"
        elif secondary_coverage < demote_threshold:
            result.band = "weak"
            result.rule_fired = f"{shape_code}+secondary_demote"
            result.secondary_action = "demote"
        # else 不动 (rule_fired = shape_code, action = "none")

    return result
