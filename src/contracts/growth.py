"""动态生长 (路径 A · L2.5) 契约.

参考: docs/04_truth_table_growth.md, SCHEMA_REFERENCE.md §3 (Mini Album)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .features import BandLevel
from .place_anchor import Cluster, MatchResult, OutlierPoint
from .theme import SemanticCluster, ThemeMatchResult
from .event import EventAggregation, EventMatchResult

DecisionTier = Literal["auto_merge", "ask_user", "no_merge", "not_applicable"]
GrowthType = Literal["location", "thematic", "event", "anchor", "mixed", "weak"]


class PlaceAnchor(BaseModel):
    """老相册的位置指纹 (DBCH 结构, ADR-0005).

    替代 v0.1 的 gps_center + gps_radius_m 简单结构:
    - clusters: DBSCAN 成簇的聚集区 (可多个)
    - outliers: 未成簇的孤立照片
    - 一张照片要么属于某簇, 要么是 outlier, 二者必居其一
    """
    clusters: list[Cluster] = Field(default_factory=list)
    outliers: list[OutlierPoint] = Field(default_factory=list)
    is_high_frequency_anchor: bool = Field(
        default=False,
        description="相册级兼容字段 (ADR-0005 老语义); ADR-0006 后实际不用, cluster.is_low_quality 由实时判定填充",
    )
    place_cluster_id: str | None = Field(
        default=None,
        description="用户级高频地点聚类 id (与本算法无关, 留作 v0.2 接入用户画像)",
    )


class MiniAlbumFingerprint(BaseModel):
    """老相册指纹 (动态生长候选用).

    完整 MiniAlbum 字段见 SCHEMA_REFERENCE.md §3,
    本结构只保留生长匹配需要的部分.
    """
    mini_album_id: str
    user_id: str
    title: str = ""
    created_at: datetime
    last_updated_at: datetime

    # 指纹三件套
    place_anchor: PlaceAnchor
    theme_clusters: list[SemanticCluster] = Field(
        default_factory=list,
        description="语义簇指纹 (ADR-0008); max 5 个, 按 frequency 降序. 见 docs/14",
    )
    theme_aggregated_at: datetime | None = Field(
        default=None,
        description="上次 theme 聚合时间; 新照片加入后全量重算 (ADR-0008 §2.6)",
    )
    event_agg: EventAggregation = Field(
        default_factory=EventAggregation,
        description="event 三级分层指纹 (ADR-0009); primary/secondary/tertiary. 见 docs/15",
    )
    event_aggregated_at: datetime | None = Field(
        default=None,
        description="上次 event 聚合时间; 新照片加入后全量重算 (ADR-0009 §2.6)",
    )
    anchors_set: list[str] = Field(default_factory=list)

    # 生长状态
    is_growing: bool = True
    growth_lock_at: datetime
    photo_count: int = 0
    max_photo_capacity: int = 30
    excluded_photo_ids: list[str] = Field(default_factory=list)


class GrowthFeatures(BaseModel):
    """新照片 vs 老相册的 4 维分数 + DBCH/Theme 诊断 (ADR-0005 / ADR-0008).

    location_score / theme_overlap_score 仅作派生展示值,
    实际分档由 location_match.band / theme_match.band 直接决定.
    """
    location_score: float = Field(ge=0.0, le=1.0)
    theme_overlap_score: float = Field(ge=0.0, le=1.0)
    event_similarity_score: float = Field(ge=0.0, le=1.0)
    anchor_overlap_score: float = Field(ge=0.0, le=1.0)
    is_high_frequency_place: bool = False

    # DBCH 算法输出 (ADR-0005), 设置时 compute_growth_bands 直接使用 band
    location_match: MatchResult | None = None
    # 语义簇匹配输出 (ADR-0008), 设置时 compute_growth_bands 直接使用 band
    theme_match: ThemeMatchResult | None = None
    # event 三级分层匹配输出 (ADR-0009), 设置时 compute_growth_bands 直接使用 band
    event_match: EventMatchResult | None = None

    def as_dict(self) -> dict:
        return self.model_dump()


class GrowthBands(BaseModel):
    """生长分档 (4 维)."""
    location: BandLevel
    theme: BandLevel
    event: BandLevel
    anchor: BandLevel


class GrowthTruthTableMatch(BaseModel):
    """路径 A 真值表命中.

    与 path B 区别:
      · 无 bounds_min/max (decision_tier 直接由表给)
      · bands_snapshot 只有 4 维 (location/theme/event/anchor)
    """
    matched_pattern: str  # "G-A1" | "G-A2" | ... | "G-F1"
    type: GrowthType
    decision_tier: DecisionTier
    bands_snapshot: GrowthBands | None = None    # ★ 输入快照


class GrowthLLMJudgement(BaseModel):
    """LLM Step 5 输出."""
    accept: bool
    semantic_reason: str = ""
    counter_evidence: str = ""
    confidence_adjustment: float = Field(default=0.0, ge=-0.1, le=0.1)
    is_mock: bool = False


class GrowthCandidateEvaluation(BaseModel):
    """对单本相册的完整评估结果."""
    album_id: str
    features: GrowthFeatures
    bands: GrowthBands
    truth_table_match: GrowthTruthTableMatch
    llm: GrowthLLMJudgement | None = None
    decision_tier: DecisionTier
    primary_signal: str


class GrowthDecision(BaseModel):
    """单张新照片的最终生长决策."""
    growth_decision_id: str
    new_photo_id: str
    decision_tier: DecisionTier
    merge_target_album_id: str | None = None
    primary_signal: str = ""
    reason: str = ""


class GrowthDecisionLog(BaseModel):
    """完整生长决策日志."""
    decision_id: str
    scenario: str | None = None
    path_taken: Literal["path_A"] = "path_A"
    new_photo_id: str
    candidate_album_ids: list[str] = Field(default_factory=list)
    per_album_evaluations: list[GrowthCandidateEvaluation] = Field(default_factory=list)
    policy_overrides: list[dict[str, Any]] = Field(default_factory=list)
    final_decision: GrowthDecision
