# 02 · 数据契约

> 所有契约用 Pydantic v2 定义在 `src/contracts/`。**禁止用 dict 凑合,禁止临时加字段**。
> SCHEMA_REFERENCE.md 是字段全集,本文件聚焦"代码用到的子集 + 边界 + 易混点"。

## 模块对应

| 路径/层 | 契约文件 | 主要类型 |
|---|---|---|
| L1 单图理解 | `src/contracts/l1_output.py` | `L1Output` / `SemanticFacts` / `SafetyFlags` / `ImageFacts` / `PlaceSignals` |
| Feature Assembler | `src/contracts/features.py` | `FeaturePackage` / `Bands` / `BandLevel` / `LocationFeature + LocationShape` (ADR-0010) / `TimeFeature + TimeShape` (ADR-0011) / `EventFeature + EventShape` (ADR-0012) / `ThemeFeature + ThemeShape` (ADR-0013) / `AnchorFeature + AnchorShape` (ADR-0014) / `EmotionalFeature + EmotionalShape` (ADR-0015) |
| 路径 B 决策 | `src/contracts/decision.py` | `TruthTableMatch` / `LLMJudgement` / `Association` / `AssociationDecision` / `DecisionLog` |
| 路径 A 决策 | `src/contracts/growth.py` | `MiniAlbumFingerprint` / `PlaceAnchor` / `GrowthFeatures` / `GrowthBands` / `GrowthTruthTableMatch` / `GrowthDecision` / `GrowthDecisionLog` |
| 路径 C 决策 | `src/contracts/backfill.py` | `BackfillCap` / `BackfillDecision` / `BackfillDecisionLog` / `PriorityRankingEntry` (ADR-0017) |
| 仲裁器 | `src/contracts/arbitration.py` | `ArbitrationResult` / `GrowthMergeRecord` (ADR-0017) |
| Feature Assembler 双版本 | `src/contracts/features.py` + `src/contracts/decision.py` | `FeaturePackage.plan` + `DecisionLog.feature_assembler_plan` (ADR-0018) |
| Place Anchor (ADR-0005) | `src/contracts/place_anchor.py` | `Cluster` / `OutlierPoint` / `MatchResult` / `HomeCityRegion` / `Context` |
| Low Quality Place (ADR-0006) | `src/contracts/low_quality_place.py` | `UserDensityBaseline` / `LowQualityResult` |
| Theme Clusters (ADR-0008) | `src/contracts/theme.py` | `SemanticCluster` / `ThemeMatchResult` |
| Event Aggregation (ADR-0009) | `src/contracts/event.py` | `EventAggregation` / `EventMatchResult` |

---

## L1Output (路径 B/A/C 共同输入)

```python
class L1Output(BaseModel):
    photo_id: str
    user_id: str
    captured_at: datetime | None
    captured_at_source: Literal["exif", "upload_time_fallback"]

    # 文学化输出 (LLM 生成, 语义边界见下方)
    individual_title: str           # 2-10 字
    individual_understanding: str   # 60-120 字
    meaning_anchors: list[str]
    meaning_density: float          # 0.0-1.0
    aesthetic_density: float        # 0.0-1.0
    theme_tags: list[str]
    emotional_tone: str

    # 结构化输出
    semantic_facts: SemanticFacts

    # 位置 / 安全 / 高频
    image_facts: ImageFacts
    place_signals: PlaceSignals
    safety_flags: SafetyFlags
```

### L1 文学化字段语义边界 (防漂移)

这些字段由 L1 LLM 生成,**极易随模型/prompt 版本漂移**。契约层 + LLM prompt 必须双向钉死以下边界:

| 字段 | 长度 | 容许语义 | **禁止内容** | 正例 | 反例 |
|---|---|---|---|---|---|
| `individual_title` | 2-10 字 | 具体物象 / 场景细节 / 中文优先 | 机器词("AI 识别为"、"分析图")/ 美学打分("绝美") / 缺席的人 | "湖边的午后" / "夕阳留白" | "AI 识别风景" / "高质量户外照" |
| `individual_understanding` | 60-120 字 | 第一人称视角 / 物象细节 / 时间感 | 情绪推断("用户当时心情焦虑") / 缺席人提及("妈妈不在") / 机器词 / 宏大词("壮丽") | "走到亭子边,柳枝从头顶垂下来…" | "用户拍下了一张人物照片,展示了…" |
| `meaning_anchors` | 1-5 个,每个 ≤4 字 | 具体物象 / 抽象意象 | 评价词("美丽") / 情绪词("开心") | `["天光","树影","慢下来"]` | `["美","好看","赞"]` |
| `meaning_density` | float 0.0-1.0 | 意义密度自评 (越高越值得记) | (数值字段,无语义禁词) | 0.78 | — |
| `aesthetic_density` | float 0.0-1.0 | 视觉密度自评 | — | 0.64 | — |
| `theme_tags` | 1-6 个,每个英文 snake_case | 主题/场景/情境的英文短标签 | 中文 / 美学评价 / 长句 / 情绪 | `["lakeside","slow_life","spring"]` | `["美丽湖景","relaxed_user"]` |
| `emotional_tone` | 单字符串 | 中性情绪基调 | 推断性情绪("焦虑"/"沮丧"/"幸福") | "relaxed" / "calm" / "neutral" | "depressed" / "anxious" |

### 不可逾越的产品红线 (体现在字段里)

来自 `CLAUDE.md`,以下任一在 L1 输出里出现就是 P0 bug:

1. **不做情绪推断**: `emotional_tone` 只允许中性档(relaxed/calm/neutral/awe),禁推断性情绪
2. **不引用人的缺席**: 三个文学化字段都不能提"…不在"、"…缺席"
3. **不出现机器词**: AI / 分析 / 识别 / 检测 / 评分 / 算法 / 模型 一律禁
4. **不评价用户**: 不出现"用户开心/沮丧/孤独"

LLM prompt 调用 L1 时必须把这张表的约束作为系统指令带入。

---

## SemanticFacts (枚举严格)

```python
class SemanticFacts(BaseModel):
    main_subjects: list[str] = []
    scene_type: Literal["home","park","travel","restaurant",
                        "street","indoor","outdoor","unknown"] = "unknown"
    activity: Literal["walk","meal","gathering","sightseeing",
                      "gardening","resting","unknown"] = "unknown"
    people_presence: Literal["none","single","group",
                             "family_like","unknown"] = "unknown"
    face_count: int = 0
    object_anchors: list[str] = []
    place_category: Literal["home_area","scenic_spot","community",
                            "road","restaurant","unknown"] = "unknown"
    # ADR-0009: 10 枚举 (6→10), 删 family_visit/festival, 新增 gathering/celebration/
    # performance/sports/work/study. 见 docs/15 §一.
    event_hint: Literal[
        "meal", "outing", "gathering", "celebration",
        "performance", "sports", "work", "study",
        "daily_record", "unknown",
    ] = "unknown"
```

所有枚举字段都含 `unknown` 兜底。LLM 拿不准时一律输出 `unknown`,不允许编造。

---

## FeaturePackage / Bands (路径 B)

```python
class FeaturePackage(BaseModel):
    location_score: float        # 派生展示, 真值表读 Bands.location
    time_score: float
    theme_score: float
    event_score: float
    people_score: float          # P0 上限 0.65
    anchor_score: float
    emotional_score: float

    is_high_frequency_place: bool
    time_is_fallback: bool
    photo_count: int

    # 维度子模型 (落痕完整结构)
    location: LocationFeature | None    # ★ ADR-0010 直出 band
    time: TimeFeature | None             # ★ ADR-0011 直出 band
    event: EventFeature | None           # ★ ADR-0012 直出 band
    theme: ThemeFeature | None           # ★ ADR-0013 直出 band
    anchor: AnchorFeature | None         # ★ ADR-0014 直出 band
    emotional: EmotionalFeature | None   # ★ ADR-0015 直出 band

class Bands(BaseModel):
    location: BandLevel   # ★ 直读 LocationFeature.band (ADR-0010)
    time: BandLevel       # ★ 直读 TimeFeature.band (ADR-0011)
    event: BandLevel      # ★ 直读 EventFeature.band (ADR-0012)
    theme: BandLevel      # ★ 直读 ThemeFeature.band (ADR-0013)
    anchor: BandLevel     # ★ 直读 AnchorFeature.band (ADR-0014)
    emotional: BandLevel  # ★ 直读 EmotionalFeature.band (ADR-0015)
    people: BandLevel     # v0.1 score → 阈值 (仅剩此 1 维待升级)
```

---

## LocationFeature (ADR-0010 升级版)

> 完整算法见 [docs/16_path_b_location.md](./16_path_b_location.md). 本节聚焦字段定义.

```python
class LocationFeature(BaseModel):
    """路径 B location 维度产出 (ADR-0010 直出 band).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断 (LLM / 监控可读, 真值表不读).
    """

    # ★ 真值表直消费
    band: BandLevel                                       # strong | medium | weak | none
    rule_fired: str                                       # "A1.7" / "A2.1" / "A3_transit_demote" / "B.2" ...

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── DBSCAN 拓扑诊断 ──────────────────────────────────────
    cluster_count_outer: int                              # K_outer
    cluster_count_inner: int | None                       # K_inner, 仅 K_outer=1 时填
    outlier_count: int

    # ─── K_outer=1 几何特征 ──────────────────────────────────
    outer_length_km: float | None                         # L (PCA 主轴投影跨度)
    outer_width_km: float | None                          # W (PCA 次轴投影跨度)
    outer_ratio: float | None                             # R = L / W
    convex_hull_diameter_km: float | None                 # D (凸包直径)
    trace_length_km: float | None                         # T (时序折线总长)
    tortuosity: float | None                              # τ = T / D

    # ─── K_outer≥2 几何特征 ──────────────────────────────────
    inter_outer_gap_km: float | null                      # gap (双簇凸包间最小距离)

    # ─── 共用 ────────────────────────────────────────────────
    max_transit_kmh: float | None                         # transit (Δt≥20min 过滤后最大速率)
    shape: LocationShape                                  # 形状大类枚举
    is_high_frequency_place: bool = False                 # ADR-0006 高频降档
    primary_signal: str = "exif_location"


class LocationShape(str, Enum):
    """LocationFeature.shape 枚举 (ADR-0010, 仅诊断/落痕用)."""
    COMPACT = "compact"                # A1.4 / A1.6
    LINEAR = "linear"                  # A1.5
    LINEAR_CURVED = "linear_curved"    # A2.2 校正后
    STRETCHED = "stretched"            # A1.7
    EXTENDED = "extended"              # A1.8
    IRREGULAR = "irregular"            # A1.9
    OVERSIZED = "oversized"            # A1.1 / A1.2 / A1.3
    LOOP = "loop"                      # A2.1 (环形)
    U_SHAPE = "u_shape"                # A2.1 (U 形)
    MULTI_CLOSE = "multi_close"        # B.1
    MULTI_WALK = "multi_walk"          # B.2
    MULTI_DRIVE = "multi_drive"        # B.3
    MULTI_FAR = "multi_far"            # B.4
    SCATTERED = "scattered"            # K_outer=0 或 K_outer≥3
```

### ⚠ ADR-0010 字段变更

| 变更 | 字段 | 原因 |
|---|---|---|
| **新增** | `band` | 4 档终值直出, 真值表直读 (ADR-0010 §2.1) |
| **新增** | `rule_fired` / `shape` | 落痕命中规则与形状大类, 便于事后归因 |
| **新增** | `cluster_count_outer/inner` / `outlier_count` | 分级 DBSCAN 拓扑诊断 |
| **新增** | `outer_length_km` / `outer_width_km` / `outer_ratio` | PCA OBB 长 / 宽 / 长宽比 (L/W/R) |
| **新增** | `convex_hull_diameter_km` / `trace_length_km` / `tortuosity` | 凸包直径 D / 轨迹长度 T / 曲折度 τ |
| **新增** | `inter_outer_gap_km` / `max_transit_kmh` | 双簇 gap / 速率 (过滤 Δt < 20min) |
| **删除** | `context: LocationContext` | LocationContext 在 ADR-0007 期已不参与判定, ADR-0010 进一步删除 (Ace 偏好: 老方案直接删) |
| **删除** | `threshold_table_used: str` | 同上, 不再走 score → 阈值表 |
| **删除** | `max_distance_m: float` | max 距离不再是核心信号, 已被几何特征矩阵替代 |
| **保留** | `score: float` | 派生展示值, 维持 v0.1 FeaturePackage.location_score 字段兼容 |
| **保留** | `is_high_frequency_place` / `primary_signal` | ADR-0006 高频降档信号 / 主信号标识 |

---

## TimeFeature (ADR-0011 升级版)

> 完整算法见 [docs/17_path_b_time.md](./17_path_b_time.md). 本节聚焦字段定义.

```python
class TimeFeature(BaseModel):
    """路径 B time 维度产出 (ADR-0011 直出 band).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断 (LLM / 监控可读, 真值表不读).
    """

    # ★ 真值表直消费
    band: BandLevel                                       # strong | medium | weak | none
    rule_fired: str                                       # "T1.5" / "T2.1+k_days_uncertain" / "T1.3+near_eps_boundary"

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── 自然日 + 事件诊断 ────────────────────────────────────
    unique_days_count: int                                # K_days, 应用自然日归属后
    span_days: int                                        # 含空日的最早最晚跨自然日数
    has_empty_days: bool                                  # span_days > K_days
    events_per_day: dict[str, int]                        # {"2026-05-15": 2, ...}
    max_events_in_any_day: int

    # ─── 时间几何 (v0.2 拆字段, 修问题⑦) ──────────────────
    total_span_hours: float                               # max - min 跨度
    max_inter_cluster_gap_h: float | None                 # 同日 cluster 间最大 gap (跨日 None)
    max_intra_cluster_span_h: float | None                # 单 cluster 内最大 span (≤ eps/60)
    has_overnight_chain: bool                             # K_days=2 + day1 末 → day2 首 gap < 12h
    has_dawn_photos: bool                                 # 是否有 0-6 点照片
    near_eps_boundary_count: int                          # 切分时 gap ∈ [eps-δ, eps+δ] 次数

    # ─── fallback ────────────────────────────────────────────
    fallback_count: int                                   # captured_at_source = upload_time_fallback 数
    fallback_ratio: float                                 # fallback_count / total
    confidence: float                                     # 1.0 - ratio × 0.3 (ratio=1 → 0.5)

    # ─── 落痕 ────────────────────────────────────────────────
    shape: TimeShape                                      # 形状大类枚举
    primary_signal: str = "captured_at"


class TimeShape(str, Enum):
    """TimeFeature.shape 枚举 (ADR-0011, 仅诊断/落痕用)."""
    SINGLE_EVENT_DENSE = "single_event_dense"             # T1.1
    SINGLE_EVENT_EXTENDED = "single_event_extended"       # T1.2
    ADJACENT_EVENTS = "adjacent_events"                   # T1.3
    DISTANT_EVENTS = "distant_events"                     # T1.4
    EXTENDED_CHAIN = "extended_chain"                     # T1.5 (v0.2 升 strong)
    DENSE_CHAIN = "dense_chain"                           # T1.6 (v0.2 新增)
    MULTI_EVENTS_BREAK = "multi_events_break"             # T1.7 (v0.2 重命名)
    OVERSTRETCHED_CHAIN = "overstretched_chain"           # T1.8 (v0.2 新增)
    OVERNIGHT = "overnight"                               # T2.1
    WEEKEND_TRIP = "weekend_trip"                         # T2.2
    SPARSE_TWO_DAYS = "sparse_two_days"                   # T2.3 / T2.4
    SHORT_TRIP = "short_trip"                             # T3.1
    SPARSE_SHORT_TRIP = "sparse_short_trip"               # T3.2
    LONG_TRIP = "long_trip"                               # T3.3
    SCATTERED_LONG = "scattered_long"                     # T3.4
    NO_TIMESTAMP = "no_timestamp"                         # K_days=0
```

### ⚠ ADR-0011 字段变更

| 变更 | 字段 | 原因 |
|---|---|---|
| **新增** | `band` | 4 档终值直出, 真值表直读 (ADR-0011 §2.1) |
| **新增** | `rule_fired` / `shape` | 落痕命中规则与形状大类 |
| **新增** | `unique_days_count` / `span_days` / `has_empty_days` / `events_per_day` / `max_events_in_any_day` | 自然日 + 事件诊断 |
| **新增** | `total_span_hours` / `max_inter_cluster_gap_h` / `max_intra_cluster_span_h` | 时间几何, v0.2 拆字段修问题⑦ |
| **新增** | `has_overnight_chain` / `has_dawn_photos` / `near_eps_boundary_count` | 跨夜判定 / 凌晨标记 / 边界保护带计数 |
| **新增** | `fallback_count` / `fallback_ratio` | 比旧 `all_fallback: bool` 更细 |
| **删除** | `is_bimodal: bool` | 双峰检测整段废弃 (新算法 1D 链式切分覆盖) |
| **删除** | `is_travel_relaxed: bool` | ADR-0010 删 LocationContext 后字段已死 |
| **删除** | `median_gap_hours: float` | 不再用 median 统计, 改用 cluster 间 gap |
| **删除** | `all_fallback: bool` | 用 `fallback_ratio == 1.0` 表达更细 |
| **重命名** | `time_span_hours` → `total_span_hours` | 与 ADR-0010 命名风格对齐 |
| **保留** | `score: float` | 派生展示值, 维持 v0.1 FeaturePackage.time_score 兼容 |
| **保留** | `confidence: float` | 仍存在, 但语义升级 (fallback 不动 band 走 confidence) |

---

## ThemeFeature (ADR-0013 升级版) + AnchorFeature (ADR-0014 新增)

> 完整算法见 [docs/19_path_b_theme.md](./19_path_b_theme.md) + [docs/20_path_b_anchor.md](./20_path_b_anchor.md).
> 两者算法骨架共享 (`src/features/_two_tier_cluster.py`), 字段抽取器不同.

```python
class ThemeShape(str, Enum):
    """ThemeFeature.shape (ADR-0013 v0.3 + ADR-0022 v0.10, 6 个主路径)."""
    MULTI_PARALLEL_CLUSTERS = "multi_parallel_clusters"  # TH.0 medium (ADR-0022)
    FULL_COVERAGE_THEMED = "full_coverage_themed"        # TH.1 strong
    DOMINANT_THEMED = "dominant_themed"                  # TH.2 medium-high
    PARTIAL_THEMED = "partial_themed"                    # TH.3 medium-low
    NO_DOMINANT_THEME = "no_dominant_theme"              # TH.4 weak
    NO_THEME_SIGNAL = "no_theme_signal"                  # TH.5 none


class ThemeFeature(BaseModel):
    band: BandLevel
    rule_fired: str                                       # "TH.1" / "TH.2+secondary_boost" 等
    score: float

    # 主字段诊断 (theme_tags)
    total_photos: int
    valid_photo_count: int
    primary_tag_pool_size: int
    primary_cluster_count: int
    primary_theme_clusters: list[list[str]]
    primary_hit_rates: list[float]
    primary_coverage: float
    primary_outlier_ids: list[str]

    # 次字段诊断 (main_subjects, 仅 TH.2/TH.3 触发 Phase 3 升降档)
    secondary_tag_pool_size: int | None
    secondary_cluster_count: int | None
    secondary_theme_clusters: list[list[str]]
    secondary_hit_rates: list[float]
    secondary_coverage: float | None
    secondary_action: str                                 # "none" | "boost" | "demote"

    # ADR-0023: subject single-layer 诊断 + MAX-OR 输出
    theme_band: BandLevel | None = None                   # Phase 3 完成时的 theme_band (MAX 输入)
    subject_band: BandLevel | None = None                 # subject single-layer band (TH.1~TH.5)
    subject_coverage: float | None = None
    subject_cluster_count: int | None = None
    subject_theme_clusters: list[list[str]] = []
    subject_hit_rates: list[float] = []
    subject_stoplist_capped: bool = False
    subject_stoplist_hits: list[str] = []                 # 命中的泛词列表
    dominant_field: Literal["theme", "subject"] = "theme" # MAX 赢家 (信息字段, 跟 rule_fired 后缀 .subject 双重落痕)

    shape: ThemeShape
    primary_signal: str = "theme_tags"
    secondary_signal: str = "main_subjects"


class AnchorShape(str, Enum):
    """AnchorFeature.shape (ADR-0014 v0.3, 5 个)."""
    FULL_COVERAGE_ANCHORED = "full_coverage_anchored"    # AN.1
    DOMINANT_ANCHORED = "dominant_anchored"              # AN.2
    PARTIAL_ANCHORED = "partial_anchored"                # AN.3
    NO_DOMINANT_ANCHOR = "no_dominant_anchor"            # AN.4
    NO_ANCHOR_SIGNAL = "no_anchor_signal"                # AN.5


class AnchorFeature(BaseModel):
    """跟 ThemeFeature 结构对称, 字段名 anchor_clusters 替代 theme_clusters."""
    band: BandLevel
    rule_fired: str
    score: float
    # 主 (meaning_anchors) + 次 (object_anchors), 结构同 ThemeFeature
    primary_anchor_clusters: list[list[str]]
    secondary_anchor_clusters: list[list[str]]
    # ... 其他字段同 ThemeFeature
    shape: AnchorShape
    primary_signal: str = "meaning_anchors"
    secondary_signal: str = "object_anchors"
```

### ⚠ ADR-0013/0014 字段变更

| 变更 | 字段 | 原因 |
|---|---|---|
| **新增** (theme) | `band` / `rule_fired` / `shape` / 主+次 cluster 诊断字段 | v0.3 双层判定直出 band |
| **删除** (theme) | `tag_embedding_similarity` / `main_subjects_jaccard` / `scene_type_consistency` / `embedding_model_used` / `degraded` | ADR-0004 v1.3.2 设计 supersede; v0.3 算法不需要 |
| **新增** (anchor) | 整个 AnchorFeature + AnchorShape (老 v0.1 仅 anchor_score 字段) | ADR-0014 直出 band |
| **新增** | FeaturePackage.anchor 字段 | 容纳 AnchorFeature |

---

## EventFeature (ADR-0012 升级版)

> 完整算法见 [docs/18_path_b_event.md](./18_path_b_event.md). 本节聚焦字段定义.

```python
class EventFeature(BaseModel):
    """路径 B event 维度产出 (ADR-0012 直出 band).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断 (LLM / 监控可读, 真值表不读).
    """

    # ★ 真值表直消费
    band: BandLevel                                       # strong | medium | weak | none
    rule_fired: str                                       # "E.1" / "E.2" / "E.7" 等

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── event 分布诊断 ──────────────────────────────────────
    total_photos: int                                     # N
    valid_event_count: int                                # N_valid
    unknown_share: float                                  # (N - N_valid) / N
    primary_event: str | None                             # agg.primary (ADR-0009)
    primary_count: int
    event_primary_share: float                            # primary_count / N (基于总数, 不是 N_valid)
    secondary_events: list[str]
    tertiary_events: list[str]
    distinct_events: int

    # ─── activity 二次门槛诊断 (v0.2 新) ────────────────────
    activity_primary: str | None                          # activity Counter.most_common, 排除 unknown
    activity_primary_count: int
    activity_primary_share: float                         # activity_primary_count / N
    used_activity_gate: bool                              # E.1 双重门槛触发标记
    used_activity_fallback: bool                          # E.7 兜底触发标记

    # ─── 落痕 ────────────────────────────────────────────────
    shape: EventShape
    primary_signal: str = "event_hint"


class EventShape(str, Enum):
    """EventFeature.shape 枚举 (ADR-0012, 仅诊断/落痕用)."""
    UNANIMOUS_EVENT_ACTIVITY = "unanimous_event_activity"           # E.1 strong
    UNANIMOUS_EVENT_MIXED_ACTIVITY = "unanimous_event_mixed_activity"  # E.2 medium
    DOMINANT_EVENT = "dominant_event"                               # E.3 medium
    MIXED_EVENT = "mixed_event"                                     # E.4 medium
    SCATTERED_EVENT = "scattered_event"                             # E.5 weak
    FRAGMENTED_EVENT = "fragmented_event"                           # E.6 weak
    ACTIVITY_FALLBACK = "activity_fallback"                         # E.7 weak
    NO_EVENT_SIGNAL = "no_event_signal"                             # E.8 none
```

### ⚠ ADR-0012 字段变更

| 变更 | 字段 | 原因 |
|---|---|---|
| **新增** | `band` / `rule_fired` / `shape` | 4 档终值 + 命中规则 + 形状大类直出 (ADR-0012 §2.1) |
| **新增** | `total_photos` / `valid_event_count` / `unknown_share` | event 分布基础诊断 |
| **新增** | `primary_event` / `primary_count` / `event_primary_share` | 主导事件 (来自 ADR-0009 aggregate_event) |
| **新增** | `secondary_events` / `tertiary_events` / `distinct_events` | 三级分层落痕 |
| **新增** | `activity_primary` / `activity_primary_count` / `activity_primary_share` | activity 二次门槛诊断 |
| **新增** | `used_activity_gate` / `used_activity_fallback` | 区分 E.1 双重门槛 vs E.7 兜底 |
| **删除** | (老 v0.1 只有 event_score, 没有 EventFeature 子模型, 无需删除) | — |
| **保留** | `score: float` | 派生展示值, 维持 v0.1 FeaturePackage.event_score 兼容 |

---

## EmotionalFeature (ADR-0015 新增)

> 完整算法见 [docs/21_path_b_emotional.md](./21_path_b_emotional.md).
> 字段开放 (`emotional_tone: str`), 单层语义聚类, 复用 ADR-0013 `_two_tier_cluster(enable_secondary=False)`.

```python
class EmotionalShape(str, Enum):
    UNANIMOUS_EMOTION = "unanimous_emotion"          # EM.1 strong
    DOMINANT_EMOTION = "dominant_emotion"            # EM.2 medium
    MIXED_EMOTION = "mixed_emotion"                  # EM.3 medium
    NEUTRAL_BASELINE = "neutral_baseline"            # EM.0 preempt weak
    SCATTERED_EMOTION = "scattered_emotion"          # EM.4 weak
    NO_EMOTION_SIGNAL = "no_emotion_signal"          # EM.5 none


class EmotionalFeature(BaseModel):
    band: BandLevel
    rule_fired: str                                   # "EM.0" / "EM.1" 等
    score: float

    # 聚类诊断 (跟 ThemeFeature/AnchorFeature 同结构)
    total_photos / valid_photo_count / tag_pool_size / cluster_count
    emotion_clusters: list[list[str]]
    hit_rates / coverage / outlier_photo_ids

    # neutral baseline 检测
    primary_dominant_tone: str | None                # 主簇代表词
    is_neutral_baseline: bool                        # primary_dominant_tone == "neutral"

    # 红线诊断 (推断情绪词违规落痕, 不阻断)
    detected_inferred_emotion_count: int
    detected_inferred_emotions: list[str]

    shape: EmotionalShape
    primary_signal: str = "emotional_tone"
```

### ⚠ ADR-0015 关键设计

- **字段 `emotional_tone: str` 类型不变**, 不引入 Literal
- **L1 prompt 改一行** (`l1_output.py` 描述): 7 白名单 → 开放画面氛围词 + 红线推断情绪阻拦
- **EM.0 preempt 优先**: 主簇代表词=neutral 强制 cap weak (即使 coverage=1.0)
- **红线落痕不阻断**: LLM 违反"不做情绪推断" 仍进 distribution, 仅 `detected_inferred_*` 落痕给上游 LLM/监控

---

## TruthTableMatch (Step 3 Stage 3 输出)

```python
class TruthTableMatch(BaseModel):
    matched_pattern: str           # "A1" | "B7" | "F1" ...
    type: AssociationType          # location / thematic / event / ...
    bounds_min: BoundsLevel        # 输出约束 (见下)
    bounds_max: BoundsLevel        # 输出约束 (见下)
    bands_snapshot: Bands          # ★ 输入快照 (见下)
```

### ⚠ `bounds_min/max` 与 `bands_snapshot` 是两种不同语义

| 字段 | 角色 | 含义 |
|---|---|---|
| `bounds_min` / `bounds_max` | **输出约束** | LLM `proposed_strength` 的允许区间 |
| `bands_snapshot` | **输入快照** | 命中那一刻的 7 维 Bands(谁触发了这条规则) |

**举例**:A1 命中 (`location=strong`) 后:
- `bounds_min=medium, bounds_max=strong` → "LLM 可以提议 medium 或 strong, 不能提议 weak"
- `bands_snapshot={location: strong, theme: medium, event: none, ...}` → "命中时全 7 维 band 的快照"

**为什么需要 bands_snapshot**:
- 一条 match 自洽,后续单独看就能知道哪些 band 触发了
- 多维 pattern 组合分析、bad case 排查无需 join `stages.step3_bands`
- 跨场景统计 (例:所有 location=strong 但 event=none 的 case 占比) 直接可做

---

## LLMJudgement (Step 4 输出)

```python
class LLMJudgement(BaseModel):
    proposed_type: AssociationType
    proposed_strength: BandLevel
    semantic_reason: str          # 30 字内
    evidence: list[EvidenceItem]
    counter_evidence: str         # 必填, 防 yes-bias
    confidence_adjustment: float  # ±0.1
    is_mock: bool
```

**LLM 绝不输出**: `score` / `display_decision` / `bounds_min` / `bounds_max`。这些都是 Policy Engine 的职责。

---

## AssociationDecision / DecisionLog (路径 B 最终输出)

```python
class Association(BaseModel):
    score: float                  # 综合可信度, 仅监控
    type: AssociationType
    strength: BandLevel
    primary_signal: str
    reason: str
    display_decision: DisplayDecision   # show_mini_album / show_inline_hint / suppress

class AssociationDecision(BaseModel):
    association_id: str
    photo_ids: list[str]
    association: Association
    decision_source: Literal[
        "policy_engine_with_llm_support",
        "policy_override",
        "pre_filter_strong",
        "pre_filter_reject",
        "truth_table_f1_suppress",
    ]

class DecisionLog(BaseModel):
    decision_id: str
    scenario: str | None
    path_taken: Literal["path_A","path_B","path_C"]
    stages: dict[str, Any]        # step1_candidates..step6_final
    policy_overrides: list[PolicyOverride]
    decision_source: str
    final_decision: AssociationDecision
```

---

## 路径 A 契约 (动态生长)

```python
class PlaceAnchor(BaseModel):
    """老相册位置指纹 (DBCH 结构, ADR-0005)"""
    clusters: list[Cluster]                # DBSCAN 成簇的聚集区
    outliers: list[OutlierPoint]           # 未成簇的孤立照片
    is_high_frequency_anchor: bool         # 相册级标志, 由 cluster 投票
    place_cluster_id: str | None           # 用户级高频地点 (与 DBCH 无关)

class MiniAlbumFingerprint(BaseModel):
    """老相册指纹 (Mini Album 子集, 仅生长匹配所需)"""
    mini_album_id: str
    user_id: str
    title: str
    created_at: datetime
    last_updated_at: datetime

    place_anchor: PlaceAnchor              # DBCH 结构, 见 docs/10 (ADR-0005/0007)
    theme_clusters: list[SemanticCluster]  # 语义簇, 见 docs/14 (ADR-0008)
    theme_aggregated_at: datetime | None   # 上次 theme 聚合时间
    event_agg: EventAggregation            # event 三级分层, 见 docs/15 (ADR-0009)
    event_aggregated_at: datetime | None   # 上次 event 聚合时间
    anchors_set: list[str]                  # meaning_anchors / object_anchors 并集 (OQ-008 §8e)

    is_growing: bool
    growth_lock_at: datetime
    photo_count: int
    max_photo_capacity: int                 # 默认 30
    excluded_photo_ids: list[str]

# ADR-0008 字段变更:
#   删 theme_tags_set: list[str]   (字面并集 → theme_clusters 语义簇)
#   删 dominant_theme: str | None  (移到 Mini Album 完整 schema, 由 LLM 综述输出)
# ADR-0009 字段变更:
#   删 dominant_event_hint: str    (字面单值 → event_agg 三级分层)

class SemanticCluster(BaseModel):
    """Theme 语义簇 (ADR-0008, docs/14)"""
    representative: str                    # 簇内字面频次最高
    members: dict[str, int]                # {字面: 频次}
    frequency: int                         # 簇总频次
    centroid: list[float]                  # 加权平均归一化向量

class ThemeMatchResult(BaseModel):
    """新照片 vs 老相册 theme_clusters 匹配 (ADR-0008)"""
    band: Literal["strong", "medium", "weak", "none"]
    score: float                           # 加权和原始分
    per_cluster: list[dict]                # 每簇命中诊断
    reason: str = ""                       # "no_tags" / "empty_clusters" / ""

class EventAggregation(BaseModel):
    """小集 event 三级分层 (ADR-0009, docs/15)"""
    primary: str | None                    # 主导 event (占比 ≥ primary_threshold)
    secondary: list[str]                   # 次主导 (占比 ≥ secondary_threshold)
    tertiary: list[str]                    # 历史稀少 (count ≥ tertiary_min_count, 不达 secondary)
    distribution: dict[str, int]           # {event: count} 完整分布
    total_events: int                      # 剔除 unknown 后总计

class EventMatchResult(BaseModel):
    """新照片 event vs 老相册 event_agg 匹配 (ADR-0009)"""
    band: Literal["strong", "medium", "weak", "none"]
    matched_tier: Literal["primary", "secondary", "tertiary", "none"] | None
    diagnostics: dict[str, Any]            # new_event / primary / secondary / tertiary
    reason: str = ""                       # "unknown_event" / "empty_aggregation" / ""

class GrowthFeatures(BaseModel):
    location_score: float                  # 派生展示值, 实际分档看 location_match.band
    theme_overlap_score: float             # 派生展示值, 实际分档看 theme_match.band (ADR-0008)
    event_similarity_score: float          # 派生展示值, 实际分档看 event_match.band (ADR-0009)
    anchor_overlap_score: float
    is_high_frequency_place: bool
    location_match: MatchResult | None     # ★ DBCH 直出 (ADR-0005)
    theme_match: ThemeMatchResult | None   # ★ 语义簇匹配直出 (ADR-0008)
    event_match: EventMatchResult | None   # ★ event 三级分层匹配直出 (ADR-0009)

class GrowthBands(BaseModel):
    location: BandLevel
    theme: BandLevel
    event: BandLevel
    anchor: BandLevel

class GrowthTruthTableMatch(BaseModel):
    matched_pattern: str       # "G-A1" .. "G-F1"
    type: GrowthType
    decision_tier: DecisionTier      # auto_merge | ask_user | no_merge | not_applicable
    bands_snapshot: GrowthBands       # ★ 输入快照

class GrowthDecision(BaseModel):
    growth_decision_id: str
    new_photo_id: str
    decision_tier: DecisionTier
    merge_target_album_id: str | None
    primary_signal: str
    reason: str

class GrowthDecisionLog(BaseModel):
    decision_id: str
    scenario: str | None
    path_taken: Literal["path_A"]
    new_photo_id: str
    candidate_album_ids: list[str]
    per_album_evaluations: list[GrowthCandidateEvaluation]
    policy_overrides: list[dict]
    final_decision: GrowthDecision
```

注意: 路径 A 没有 `bounds_min/max` 概念,`decision_tier` 直接由真值表给出。LLM Judge 只能选 accept/reject + 引发一档浮动(由 `growth_engine.py` HRG-POST 实现)。

### Place Anchor 契约 (ADR-0005)

```python
class Cluster(BaseModel):
    cluster_id: str
    member_photo_ids: list[str]
    convex_hull: list[tuple[float, float]]   # [(lat, lng), ...]
    centroid: tuple[float, float]
    is_low_quality: bool                     # 高频低质量地点 (ADR-0006, 实时填充)

class OutlierPoint(BaseModel):
    photo_id: str
    gps: tuple[float, float]

class MatchResult(BaseModel):
    """match_new_photo 输出, 真值表直接消费 band 字段."""
    band: BandLevel                          # strong / medium / weak / none
    matched_target_type: Literal["cluster", "outlier"] | None
    matched_target_id: str | None
    diagnostics: dict                        # raw_distance / buffer / effective_distance / context
    reason: str = ""                         # 早返原因 "no_gps" / "empty_anchor"

class HomeCityRegion(BaseModel):
    """ADR-0016 升级: admin dict 4 档主信号."""
    user_id: str
    country: str = "中国"
    province: str | None        # "浙江省"
    city: str | None            # "杭州市"
    district: str | None        # "西湖区" (可选)
    center: tuple[float, float] | None    # 兜底用 (lat, lng), Geocoder 失败时回退
    radius_km: float | None
    inferred_source: str = "stub"  # "stub" / "amap_frequency" / "amap_direct"

Context = Literal["市内", "省内", "国内", "国外"]    # ADR-0016 4 档 (中文枚举)
```

完整算法见 `docs/10_mini_album_schema.md` §2。

### Low Quality Place 契约 (ADR-0006)

```python
class UserDensityBaseline(BaseModel):
    """用户个人 L1 双 density 的 25 分位 (Plan A)."""
    user_id: str
    meaning_threshold: float    # user history meaning_density 25 分位
    aesthetic_threshold: float  # 同上 aesthetic_density
    last_computed_at: datetime
    sample_size: int            # ≥ min_samples_for_baseline 才有效

class LowQualityResult(BaseModel):
    """is_low_quality_place 返回结构, 含诊断"""
    is_low_quality: bool
    signal_source: Literal["plan_a", "plan_b", "frequency_failed", "baseline_missing", "disabled"]
    diagnostics: dict           # frequency 通过否 / 双低占比 / baseline 阈值 等
```

完整算法见 `docs/13_low_quality_place_detection.md`。

---

## 路径 C 契约 (兜底回扫)

```python
class BackfillCap(BaseModel):
    rule: str                  # "BACKFILL-CAP-01-bounds_max_strong" 等
    passed: bool
    detail: str

class BackfillDecision(BaseModel):
    backfill_decision_id: str
    new_photo_id: str
    decision_tier: BackfillTier     # create_new_album | no_backfill | insufficient_candidates
    recalled_photo_ids: list[str]
    target_album_strength: str | None
    primary_signal: str
    reason: str

class BackfillDecisionLog(BaseModel):
    decision_id: str
    scenario: str | None
    path_taken: Literal["path_C"]
    new_photo_id: str
    coarse_filter_candidates: list[str]
    priority_ranking: list[PriorityRankingEntry]    # ← ADR-0017 新增
    main_truth_table_match: TruthTableMatch | None  # 复用主表
    llm_judgement: LLMJudgement | None
    backfill_caps_applied: list[BackfillCap]
    policy_overrides: list[dict]
    final_decision: BackfillDecision

class PriorityRankingEntry(BaseModel):
    """ADR-0017: cascade 粗筛后每候选的维度强度总分 (落痕用)."""
    photo_id: str
    gps_within_1km: bool
    theme_jaccard_above_0_5: bool
    event_match: bool
    score: float                                     # gps*1 + theme*1 + event*0.5
    selected: bool                                   # 是否进入 top 4 (PRD §3.10.5)
```

---

## 仲裁器契约

```python
class ArbitrationResult(BaseModel):
    arbitration_id: str
    scenario: str | None

    # 三路原始日志 (None = 未触发)
    growth_log: GrowthDecisionLog | None
    l2_log: DecisionLog | None
    backfill_log: BackfillDecisionLog | None         # 兼容老入口 (单张走 C 时填这个)

    # ─── ADR-0017 新增: 多产物 (多张拆 N 张时填这些) ───
    cascade_albums: list[Association]                # cascade 产出的额外相册 (可 0~N)
    growth_merges: list[GrowthMergeRecord]           # 拆 N 张走 A 加入老相册的记录
    settled_photo_ids: list[str]                     # 拆 N 张后 A C 都失败进沉淀的 photo_ids
    cascade_logs: list[BackfillDecisionLog]          # 各 P_i cascade 单次的完整 log

    # 最终判决
    arbitration_winner: Literal["path_A","path_B","path_C","cascade","none"]
    ending: Literal[
        "add_to_existing_album","ask_user_confirm",
        "create_new_album_path_b","create_new_album_backfill",
        "create_multiple_cascade_albums",            # ← ADR-0017 新增
        "single_photo_sediment","ask_user_pending",
    ]
    target_album_id: str | None
    target_album_strength: str | None
    user_facing_message: str           # 喜宝话术

    # 仲裁过程留痕
    discarded_paths: list[str]         # ["path_B","path_C"] 等
    case_matched: str                  # "Case 1-8" (Case 5-8 = ADR-0017 多张拆 N 张)

class GrowthMergeRecord(BaseModel):
    """ADR-0017: 单张照片加入老相册的记录."""
    photo_id: str
    target_album_id: str
    decision_tier: Literal["auto_merge", "ask_user"]
```

---

## 枚举一览 (快速参考)

| 名称 | 值 |
|---|---|
| `BandLevel` | strong / medium / weak / none |
| `BoundsLevel` | strong / medium / light / none (light 等价 weak,真值表 bounds 专用) |
| `DisplayDecision` | show_mini_album / show_inline_hint / suppress / merge_into_existing / ask_user_merge |
| `AssociationType` | location / temporal / event / thematic / people / emotional / visual / mixed / weak |
| `DecisionTier` (路径 A) | auto_merge / ask_user / no_merge / not_applicable |
| `BackfillTier` (路径 C) | create_new_album / no_backfill / insufficient_candidates |
| `ArbitrationWinner` | path_A / path_B / path_C / none |
| `ArbitrationEnding` | add_to_existing_album / ask_user_confirm / create_new_album_path_b / create_new_album_backfill / single_photo_sediment / ask_user_pending |

⚠ `weak` 和 `light` 同义:代码内部 BandLevel 用 `weak`,真值表 bounds 历史上用 `light`。`99_glossary.md` 注释了这个混用。
