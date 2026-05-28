"""Feature Assembler 输出 + 维度分档契约.

参考:
  docs/02_data_contracts.md
  docs/07_dimension_thresholds.md
  docs/16_path_b_location.md (LocationFeature, ADR-0010)
  docs/17_path_b_time.md (TimeFeature, ADR-0011)
  docs/18_path_b_event.md (EventFeature, ADR-0012)
  docs/19_path_b_theme.md (ThemeFeature, ADR-0013)
  docs/20_path_b_anchor.md (AnchorFeature, ADR-0014)
  decisions/0010-path-b-location-dbch-pca-shape.md (LocationFeature 升级)
  decisions/0011-time-natural-day-event-clustering.md (TimeFeature 升级)
  decisions/0012-path-b-event-aggregation.md (EventFeature 升级)
  decisions/0013-path-b-theme-two-tier-cluster.md (ThemeFeature 升级)
  decisions/0014-path-b-anchor-two-tier-cluster.md (AnchorFeature 新增)
  decisions/0015-path-b-emotional-single-tier-cluster.md (EmotionalFeature 新增)
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

BandLevel = Literal["strong", "medium", "weak", "none"]


# ─── ADR-0010 · LocationFeature shape 枚举 ────────────────────
class LocationShape(str, Enum):
    """LocationFeature.shape 落痕枚举 (ADR-0010, docs/16 §五).

    仅作诊断用, 真值表不读. 命中规则与 rule_fired 一一对应:
    - A1.4 / A1.6 → COMPACT
    - A1.5 → LINEAR
    - A2.2 → LINEAR_CURVED
    - A1.7 → STRETCHED
    - A1.8 → EXTENDED
    - A1.9 → IRREGULAR
    - A1.1 / A1.2 / A1.3 → OVERSIZED
    - A2.1 → LOOP 或 U_SHAPE
    - B.1 → MULTI_CLOSE
    - B.2 → MULTI_WALK
    - B.3 → MULTI_DRIVE
    - B.4 → MULTI_FAR
    - K_outer=0 或 K_outer≥3 → SCATTERED
    """
    COMPACT = "compact"
    LINEAR = "linear"
    LINEAR_CURVED = "linear_curved"
    STRETCHED = "stretched"
    EXTENDED = "extended"
    IRREGULAR = "irregular"
    OVERSIZED = "oversized"
    LOOP = "loop"
    U_SHAPE = "u_shape"
    MULTI_CLOSE = "multi_close"
    MULTI_WALK = "multi_walk"
    MULTI_DRIVE = "multi_drive"
    MULTI_FAR = "multi_far"
    SCATTERED = "scattered"


# ─── ADR-0010 · LocationFeature ───────────────────────────────
class LocationFeature(BaseModel):
    """路径 B location 维度产出 (ADR-0010 直出 band).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断 (LLM / 监控可读, 真值表不读).
    参考: docs/16_path_b_location.md §一~§六 + §八 不变性.
    """

    # ★ 真值表直消费
    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "A1.7" / "A2.1" / "A3_transit_demote" / "B.2" ...

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── DBSCAN 拓扑诊断 ──────────────────────────────────────
    cluster_count_outer: int = Field(ge=0)
    cluster_count_inner: int | None = Field(default=None, ge=0)
    outlier_count: int = Field(ge=0)

    # ─── K_outer = 1 几何特征 (仅 K_outer=1 时填) ─────────────
    outer_length_km: float | None = Field(default=None, ge=0.0)
    outer_width_km: float | None = Field(default=None, ge=0.0)
    outer_ratio: float | None = Field(default=None, ge=0.0)
    convex_hull_diameter_km: float | None = Field(default=None, ge=0.0)
    trace_length_km: float | None = Field(default=None, ge=0.0)
    tortuosity: float | None = Field(default=None, ge=0.0)

    # ─── K_outer ≥ 2 几何特征 ─────────────────────────────────
    inter_outer_gap_km: float | None = Field(default=None, ge=0.0)

    # ─── 共用 ────────────────────────────────────────────────
    max_transit_kmh: float | None = Field(default=None, ge=0.0)
    shape: LocationShape
    is_high_frequency_place: bool = False
    primary_signal: str = "exif_location"


# ─── ADR-0011 · TimeFeature shape 枚举 ─────────────────────────
class TimeShape(str, Enum):
    """TimeFeature.shape 落痕枚举 (ADR-0011, docs/17 §三).

    仅作诊断用, 真值表不读. 命中规则与 rule_fired 一一对应:
    - T1.1 → SINGLE_EVENT_DENSE
    - T1.2 → SINGLE_EVENT_EXTENDED
    - T1.3 → ADJACENT_EVENTS
    - T1.4 → DISTANT_EVENTS
    - T1.5 → EXTENDED_CHAIN (v0.2 升 strong)
    - T1.6 → DENSE_CHAIN
    - T1.7 → MULTI_EVENTS_BREAK
    - T1.8 → OVERSTRETCHED_CHAIN
    - T2.1 → OVERNIGHT
    - T2.2 → WEEKEND_TRIP
    - T2.3 / T2.4 → SPARSE_TWO_DAYS
    - T3.1 → SHORT_TRIP
    - T3.2 → SPARSE_SHORT_TRIP
    - T3.3 → LONG_TRIP
    - T3.4 → SCATTERED_LONG
    - T0 (K_days=0) → NO_TIMESTAMP
    """
    SINGLE_EVENT_DENSE = "single_event_dense"
    SINGLE_EVENT_EXTENDED = "single_event_extended"
    ADJACENT_EVENTS = "adjacent_events"
    DISTANT_EVENTS = "distant_events"
    EXTENDED_CHAIN = "extended_chain"
    DENSE_CHAIN = "dense_chain"
    MULTI_EVENTS_BREAK = "multi_events_break"
    OVERSTRETCHED_CHAIN = "overstretched_chain"
    OVERNIGHT = "overnight"
    WEEKEND_TRIP = "weekend_trip"
    SPARSE_TWO_DAYS = "sparse_two_days"
    SHORT_TRIP = "short_trip"
    SPARSE_SHORT_TRIP = "sparse_short_trip"
    LONG_TRIP = "long_trip"
    SCATTERED_LONG = "scattered_long"
    NO_TIMESTAMP = "no_timestamp"


class TimeFeature(BaseModel):
    """路径 B time 维度产出 (ADR-0011 直出 band).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断 (LLM / 监控可读, 真值表不读).
    参考: docs/17_path_b_time.md §一~§五 不变性.
    """

    # ★ 真值表直消费
    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "T1.5" / "T2.1+k_days_uncertain" / "T1.3+near_eps_boundary"

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── 自然日 + 事件诊断 (ADR-0011 §2.5) ────────────────
    unique_days_count: int = Field(ge=0)                # K_days
    span_days: int = Field(ge=0)
    has_empty_days: bool = False
    events_per_day: dict[str, int] = Field(default_factory=dict)
    max_events_in_any_day: int = Field(default=0, ge=0)

    # ─── 时间几何 (v0.2 拆字段, 修问题⑦) ──────────────────
    total_span_hours: float = Field(ge=0.0)
    max_inter_cluster_gap_h: float | None = Field(default=None, ge=0.0)
    max_intra_cluster_span_h: float | None = Field(default=None, ge=0.0)
    has_overnight_chain: bool = False
    has_dawn_photos: bool = False
    near_eps_boundary_count: int = Field(default=0, ge=0)

    # ─── fallback (ADR-0011 §2.7) ─────────────────────────
    fallback_count: int = Field(default=0, ge=0)
    fallback_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # ─── 落痕 ────────────────────────────────────────────
    shape: TimeShape
    primary_signal: str = "captured_at"


# ─── ADR-0013 · ThemeFeature shape 枚举 ────────────────────
class ThemeShape(str, Enum):
    """ThemeFeature.shape 落痕枚举 (ADR-0013 v0.3, ADR-0022 加 TH.0)."""
    MULTI_PARALLEL_CLUSTERS = "multi_parallel_clusters"  # TH.0 medium (ADR-0022)
    FULL_COVERAGE_THEMED = "full_coverage_themed"        # TH.1 strong (单簇 100%)
    DOMINANT_THEMED = "dominant_themed"                  # TH.2 medium-high
    PARTIAL_THEMED = "partial_themed"                    # TH.3 medium-low
    NO_DOMINANT_THEME = "no_dominant_theme"              # TH.4 weak
    NO_THEME_SIGNAL = "no_theme_signal"                  # TH.5 none


class ThemeFeature(BaseModel):
    """路径 B theme 维度产出 (ADR-0013 v0.3 直出 band, 双层判定).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断.
    """

    # ★ 真值表直消费
    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "TH.1" / "TH.2+secondary_boost" 等

    # 派生展示
    score: float = Field(ge=0.0, le=1.0)

    # ─── 主字段诊断 (theme_tags) ─────────────────────────────
    total_photos: int = Field(ge=0)
    valid_photo_count: int = Field(ge=0)
    primary_tag_pool_size: int = Field(default=0, ge=0)
    primary_cluster_count: int = Field(default=0, ge=0)
    primary_theme_clusters: list[list[str]] = Field(default_factory=list)
    primary_hit_rates: list[float] = Field(default_factory=list)
    primary_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    primary_outlier_ids: list[str] = Field(default_factory=list)

    # ─── 次字段诊断 (main_subjects, 仅 TH.2/TH.3 触发 Phase 3 升降档) ────
    secondary_tag_pool_size: int | None = None
    secondary_cluster_count: int | None = None
    secondary_theme_clusters: list[list[str]] = Field(default_factory=list)
    secondary_hit_rates: list[float] = Field(default_factory=list)
    secondary_coverage: float | None = None
    secondary_action: str = "none"               # "none" | "boost" | "demote"

    # ─── ADR-0023 · subject single-layer (Phase 4) + MAX-OR (Phase 6) ────
    theme_band: BandLevel | None = None          # Phase 3 完成时的 theme_band (MAX 输入)
    subject_band: BandLevel | None = None        # subject single-layer band (TH.1~TH.5, 无 TH.0)
    subject_coverage: float | None = None
    subject_cluster_count: int | None = None
    subject_theme_clusters: list[list[str]] = Field(default_factory=list)
    subject_hit_rates: list[float] = Field(default_factory=list)
    subject_stoplist_capped: bool = False        # 是否被泛词 cap medium
    subject_stoplist_hits: list[str] = Field(default_factory=list)  # 命中的泛词列表
    dominant_field: Literal["theme", "subject"] = "theme"  # MAX 赢家 (跟 rule_fired 后缀 .subject 双重落痕)

    # ─── 落痕 ────────────────────────────────────────────────
    shape: ThemeShape
    primary_signal: str = "theme_tags"
    secondary_signal: str = "main_subjects"


# ─── ADR-0014 · AnchorFeature shape 枚举 ───────────────────
class AnchorShape(str, Enum):
    """AnchorFeature.shape 落痕枚举 (ADR-0014 v0.3, 5 个主路径)."""
    FULL_COVERAGE_ANCHORED = "full_coverage_anchored"    # AN.1
    DOMINANT_ANCHORED = "dominant_anchored"              # AN.2
    PARTIAL_ANCHORED = "partial_anchored"                # AN.3
    NO_DOMINANT_ANCHOR = "no_dominant_anchor"            # AN.4
    NO_ANCHOR_SIGNAL = "no_anchor_signal"                # AN.5


class AnchorFeature(BaseModel):
    """路径 B anchor 维度产出 (ADR-0014 v0.3 直出 band, 双层判定).

    band 是真值表消费的 4 档终值.
    主字段: meaning_anchors / 次字段: semantic_facts.object_anchors.
    跟 ThemeFeature 结构对称, 共享 _two_tier_cluster 工具.
    """

    # ★ 真值表直消费
    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "AN.1" / "AN.2+secondary_boost" 等

    score: float = Field(ge=0.0, le=1.0)

    # ─── 主字段诊断 (meaning_anchors) ─────────────────────
    total_photos: int = Field(ge=0)
    valid_photo_count: int = Field(ge=0)
    primary_tag_pool_size: int = Field(default=0, ge=0)
    primary_cluster_count: int = Field(default=0, ge=0)
    primary_anchor_clusters: list[list[str]] = Field(default_factory=list)
    primary_hit_rates: list[float] = Field(default_factory=list)
    primary_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    primary_outlier_ids: list[str] = Field(default_factory=list)

    # ─── 次字段诊断 (object_anchors, 仅 AN.2/AN.3 计算) ────
    secondary_tag_pool_size: int | None = None
    secondary_cluster_count: int | None = None
    secondary_anchor_clusters: list[list[str]] = Field(default_factory=list)
    secondary_hit_rates: list[float] = Field(default_factory=list)
    secondary_coverage: float | None = None
    secondary_action: str = "none"               # "none" | "boost" | "demote"

    shape: AnchorShape
    primary_signal: str = "meaning_anchors"
    secondary_signal: str = "object_anchors"


# ─── ADR-0015 · EmotionalFeature shape 枚举 ────────────────
class EmotionalShape(str, Enum):
    """EmotionalFeature.shape 落痕枚举 (ADR-0015 v0.2, 6 个).

    EM.0 preempt: 主簇代表词=neutral 强制 cap weak (优先级最高).
    """
    UNANIMOUS_EMOTION = "unanimous_emotion"          # EM.1 strong
    DOMINANT_EMOTION = "dominant_emotion"            # EM.2 medium
    MIXED_EMOTION = "mixed_emotion"                  # EM.3 medium
    NEUTRAL_BASELINE = "neutral_baseline"            # EM.0 preempt weak
    SCATTERED_EMOTION = "scattered_emotion"          # EM.4 weak
    NO_EMOTION_SIGNAL = "no_emotion_signal"          # EM.5 none


class EmotionalFeature(BaseModel):
    """路径 B emotional 维度产出 (ADR-0015 v0.2 直出 band, 单层语义聚类).

    band 是真值表消费的 4 档终值.
    复用 _two_tier_cluster.build_two_tier_feature(enable_secondary=False) 通用工具.
    跟 ThemeFeature/AnchorFeature 结构相似, 字段不同 + 加 neutral baseline + 红线诊断.
    """

    # ★ 真值表直消费
    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "EM.0" / "EM.1" / "EM.3" 等
    score: float = Field(ge=0.0, le=1.0)

    # ─── 聚类诊断 (跟 ThemeFeature/AnchorFeature 同结构) ──
    total_photos: int = Field(ge=0)
    valid_photo_count: int = Field(ge=0)
    tag_pool_size: int = Field(default=0, ge=0)
    cluster_count: int = Field(default=0, ge=0)
    emotion_clusters: list[list[str]] = Field(default_factory=list)
    hit_rates: list[float] = Field(default_factory=list)
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    outlier_photo_ids: list[str] = Field(default_factory=list)

    # ─── neutral baseline 检测 (emotional 独有) ────────────
    primary_dominant_tone: str | None = None     # 主簇代表词
    is_neutral_baseline: bool = False            # primary_dominant_tone == "neutral"

    # ─── 红线诊断 (推断情绪词违规落痕) ────────────────────
    detected_inferred_emotion_count: int = Field(default=0, ge=0)
    detected_inferred_emotions: list[str] = Field(default_factory=list)

    shape: EmotionalShape
    primary_signal: str = "emotional_tone"


# ─── ADR-0012 · EventFeature shape 枚举 ──────────────────────
class EventShape(str, Enum):
    """EventFeature.shape 落痕枚举 (ADR-0012, docs/18 §三).

    8 个 shape 对应 8 行 E.1~E.8 grid:
    - E.1 → UNANIMOUS_EVENT_ACTIVITY (strong)
    - E.2 → UNANIMOUS_EVENT_MIXED_ACTIVITY (medium)
    - E.3 → DOMINANT_EVENT (medium)
    - E.4 → MIXED_EVENT (medium)
    - E.5 → SCATTERED_EVENT (weak)
    - E.6 → FRAGMENTED_EVENT (weak)
    - E.7 → ACTIVITY_FALLBACK (weak)
    - E.8 → NO_EVENT_SIGNAL (none)
    """
    UNANIMOUS_EVENT_ACTIVITY = "unanimous_event_activity"           # E.1
    UNANIMOUS_EVENT_MIXED_ACTIVITY = "unanimous_event_mixed_activity"  # E.2
    DOMINANT_EVENT = "dominant_event"                               # E.3
    MIXED_EVENT = "mixed_event"                                     # E.4
    SCATTERED_EVENT = "scattered_event"                             # E.5
    FRAGMENTED_EVENT = "fragmented_event"                           # E.6
    ACTIVITY_FALLBACK = "activity_fallback"                         # E.7
    NO_EVENT_SIGNAL = "no_event_signal"                             # E.8


class EventFeature(BaseModel):
    """路径 B event 维度产出 (ADR-0012 直出 band).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断.
    参考: docs/18_path_b_event.md §一~§五.
    """

    # ★ 真值表直消费
    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "E.1" / "E.2" / "E.7" 等

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── event 分布诊断 ──────────────────────────────────────
    total_photos: int = Field(ge=0)
    valid_event_count: int = Field(ge=0)
    unknown_share: float = Field(ge=0.0, le=1.0)
    primary_event: str | None = None
    primary_count: int = Field(default=0, ge=0)
    event_primary_share: float = Field(ge=0.0, le=1.0)
    secondary_events: list[str] = Field(default_factory=list)
    tertiary_events: list[str] = Field(default_factory=list)
    distinct_events: int = Field(default=0, ge=0)

    # ─── activity 二次门槛诊断 (ADR-0012 v0.2 新) ────────────
    activity_primary: str | None = None
    activity_primary_count: int = Field(default=0, ge=0)
    activity_primary_share: float = Field(default=0.0, ge=0.0, le=1.0)
    used_activity_gate: bool = False                 # E.1 双重门槛
    used_activity_fallback: bool = False             # E.7 兜底

    # ─── 落痕 ────────────────────────────────────────────────
    shape: EventShape
    primary_signal: str = "event_hint"


# ─── FeaturePackage ───────────────────────────────────────────
class FeaturePackage(BaseModel):
    """Step 2 输出: 7 维客观分数 + 维度子模型."""

    # ─── ADR-0018: 版本标记 ──────────────────────────────────
    # L2_2.0 (默认): 走 ADR-0010~0015 直出 band, 子 Feature 字段填充
    # L2_1.0: 走 v1.3 §3.2 score-based, 子 Feature 字段全 None, 仅 *_score 填充
    plan: Literal["L2_2.0", "L2_1.0"] = "L2_2.0"

    # ─── v0.1 scalar 字段 (派生展示, 真值表通过 Bands 间接消费) ─
    location_score: float = Field(ge=0.0, le=1.0)
    time_score: float = Field(ge=0.0, le=1.0)
    theme_score: float = Field(ge=0.0, le=1.0)
    event_score: float = Field(ge=0.0, le=1.0)
    people_score: float = Field(ge=0.0, le=0.65)  # P0 上限
    anchor_score: float = Field(ge=0.0, le=1.0)
    emotional_score: float = Field(ge=0.0, le=1.0)

    # 上下文标志
    is_high_frequency_place: bool = False
    time_is_fallback: bool = False
    photo_count: int = 0

    # ─── 维度子模型 (落痕完整结构) ──────────────────────────
    location: LocationFeature | None = None      # ★ ADR-0010 直出 band
    time: TimeFeature | None = None              # ★ ADR-0011 直出 band
    event: EventFeature | None = None            # ★ ADR-0012 直出 band
    theme: ThemeFeature | None = None            # ★ ADR-0013 直出 band
    anchor: AnchorFeature | None = None          # ★ ADR-0014 直出 band
    emotional: EmotionalFeature | None = None    # ★ ADR-0015 直出 band

    def as_dict(self) -> dict:
        return {
            "location_score": self.location_score,
            "time_score": self.time_score,
            "theme_score": self.theme_score,
            "event_score": self.event_score,
            "people_score": self.people_score,
            "anchor_score": self.anchor_score,
            "emotional_score": self.emotional_score,
            "is_high_frequency_place": self.is_high_frequency_place,
            "time_is_fallback": self.time_is_fallback,
        }


class Bands(BaseModel):
    """Step 3 Stage 2 输出: 每个维度的强/中/弱/无.

    location 直读 LocationFeature.band (ADR-0010).
    time 直读 TimeFeature.band (ADR-0011).
    event 直读 EventFeature.band (ADR-0012).
    theme 直读 ThemeFeature.band (ADR-0013).
    anchor 直读 AnchorFeature.band (ADR-0014).
    emotional 直读 EmotionalFeature.band (ADR-0015).
    """

    location: BandLevel
    time: BandLevel
    theme: BandLevel
    event: BandLevel
    people: BandLevel
    anchor: BandLevel
    emotional: BandLevel

    def main_signals(self) -> dict[str, BandLevel]:
        return {
            "location": self.location,
            "theme": self.theme,
            "event": self.event,
            "people": self.people,
        }

    def auxiliary_signals(self) -> dict[str, BandLevel]:
        return {"anchor": self.anchor, "emotional": self.emotional}
