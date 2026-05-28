# 10 · Mini Album 数据 Schema + 指纹合成规范

> 完整 Mini Album 字段见 `SCHEMA_REFERENCE.md` §3。本文档聚焦**指纹合成与匹配**算法。
> Place Anchor 部分基于 [ADR-0005 · DBCH 算法](../decisions/0005-place-anchor-dbch.md), v0.1 测试期距离档位部分被 [ADR-0007](../decisions/0007-unified-location-bands.md) 临时塌缩 (单一表 500/1000/2000m, OQ-017 触发回切).
> Theme 指纹部分基于 [ADR-0008 · 语义簇聚合](../decisions/0008-theme-semantic-clustering.md), 完整算法见 [docs/14](./14_theme_aggregation.md).
> Event 指纹部分基于 [ADR-0009 · event 三级分层](../decisions/0009-event-aggregation.md), 完整算法见 [docs/15](./15_event_aggregation.md).
> 其他指纹字段(anchors_set / 更新策略)仍待 [OQ-008](./12_open_questions.md#oq-008-小集指纹合成-mini-album-fingerprint-synthesis) §8e/8h/8i 决策。

---

## 一、指纹字段总览

```python
class MiniAlbumFingerprint(BaseModel):
    # 已规范
    place_anchor: PlaceAnchor                # DBCH 结构, 见 §二 (ADR-0005/0007)
    theme_clusters: list[SemanticCluster]    # 语义簇, 见 §三 (ADR-0008, docs/14)
    theme_aggregated_at: datetime | None     # 上次 theme 聚合时间
    event_agg: EventAggregation              # event 三级分层, 见 §四 (ADR-0009, docs/15)
    event_aggregated_at: datetime | None     # 上次 event 聚合时间

    # 待 OQ-008 §8e/8h/8i 规范
    anchors_set: list[str]                   # 占位
```

⚠ 字段变更历史:
- ADR-0008: 删 `theme_tags_set` + `dominant_theme`, 升级为 `theme_clusters`
- ADR-0009: 删 `dominant_event_hint`, 升级为 `event_agg` (三级分层)

---

## 二、Place Anchor (DBCH 算法)

### 2.1 · 数据结构

```python
class PlaceAnchor(BaseModel):
    clusters: list[Cluster]            # DBSCAN 成簇的聚集区
    outliers: list[OutlierPoint]       # 未成簇的孤立照片
    is_high_frequency_anchor: bool     # 相册级标志, 来自 cluster.is_low_quality 投票 (deprecated, ADR-0006 之后改为实时计算)
    place_cluster_id: str | None       # 与用户级 high-freq place 关联 (与 DBCH 无关)


class Cluster(BaseModel):
    cluster_id: str
    member_photo_ids: list[str]
    convex_hull: list[tuple[float, float]]   # 凸包顶点 [(lat, lng), ...]
    centroid: tuple[float, float]            # 几何中位数
    is_low_quality: bool = False             # 高频低质量地点标志 (ADR-0006)
                                              # ⚠ 实时计算, 不持久化; build_place_anchor 默认 False
                                              # match_against_cluster 调用时由 is_low_quality_place 实时填充


class OutlierPoint(BaseModel):
    photo_id: str
    gps: tuple[float, float]                  # (lat, lng)


class MatchResult(BaseModel):
    band: Literal["strong", "medium", "weak", "none"]
    matched_target_type: Literal["cluster", "outlier"] | None
    matched_target_id: str | None
    diagnostics: dict[str, Any]               # raw_distance / buffer / effective_distance / context 等
    reason: str = ""                          # 早返时填: "no_gps" / "empty_anchor"
```

**核心不变性**(代码必须保证):

1. 一张照片**要么属于某个簇,要么是 outlier**, 二者必居其一
2. outlier 不进任何凸包, 不参与基于 hull 的匹配
3. outlier 在全量重跑时有机会"转正"为簇成员
4. `band` 输出严格 ∈ {strong, medium, weak, none}, schema 永远统一
5. 同一相册多簇时, 最终 band = 最强簇的 band
6. 命中 strong 即早返, 不再算其他簇
7. 无簇但有 outlier 时, 退化为点点距离匹配, **不用 buffer**
8. Buffer 随 n 单调不增 (越用越严), 永不为 0

### 2.2 · Context 判定 (用户层级)

```python
def get_context_for_photo(photo, user_home_city) -> Literal["home_city", "cross_province", "cross_country"]:
    d_km = haversine_km(photo.gps, user_home_city.center)
    if d_km < user_home_city.radius_km:
        return "home_city"
    if same_province(photo.gps, user_home_city.center):
        return "cross_province"
    return "cross_country"
```

⚠ context 是**判定时算出来**的, 不预存 (用户搬家后, 同一张照片可能从 home_city 变 cross_province)。

⚠ `user_home_city` 推断模块是**前置依赖**, 见 [OQ-010](./12_open_questions.md)。v0.1 demo 用硬编码 stub: `user_demo → (30.26, 120.13, radius_km=30)` (杭州中心)。

### 2.3 · 距离档位表

> ⚠ **v0.1 测试期 (ADR-0007)**: 三 context 表塌缩为**单一档** (POI 城市判定 OQ-010 未实现, 三档归因复杂). 原三档保留为下方注释, OQ-017 完成后回切.

#### 当前生效 (unified, ADR-0007)

```yaml
unified_band_thresholds:
  strong_m: 500
  medium_m: 1000
  weak_m: 2000
```

距离 → 档位:
- `d ≤ 500m` → strong
- `d ≤ 1000m` → medium
- `d ≤ 2000m` → weak
- `d >  2000m` → none

档位**不再下钻 context**, `infer_context` 仍调用但只写进 diag (备 v0.2 回切验证).

<!--
#### 待回切 (per-context, ADR-0005 原方案, OQ-017 触发)

band_thresholds:
  home_city:        { strong_m: 100,  medium_m: 300,   weak_m: 800 }
  cross_province:   { strong_m: 500,  medium_m: 1500,  weak_m: 5000 }
  cross_country:    { strong_m: 2000, medium_m: 5000,  weak_m: 15000 }

距离 → 档位:
- `d ≤ strong_m[context]` → strong
- `d ≤ medium_m[context]` → medium
- `d ≤ weak_m[context]`   → weak
- `d >  weak_m[context]`  → none
-->


### 2.4 · Buffer 公式 (簇置信宽容度)

```
buffer = base / (1 + 0.6 × ln(n))
```

> ⚠ **v0.1 测试期 (ADR-0007)**: `base` 塌缩为**统一 250m** (= unified strong_m / 2).

#### 当前生效 (unified, ADR-0007)

- `base = 250m` (与 context 无关)
- `n` = 簇内点数
- `alpha = 0.6`

**衰减表**:

| n | buffer |
|---|---|
| 1 | 250m |
| 3 | 151m |
| 5 | 127m |
| 10 | 105m |
| 20 | 91m |
| 30 | 82m |

n=5 时衰到一半, n=30 时降到约 1/3, 永不归零.

<!--
#### 待回切 (per-context, ADR-0005 原方案)

- base = strong_m / 2 (各 context: home=50m / province=250m / country=1000m)
- 衰减表:
  | n | home buffer | province buffer | country buffer |
  |---|---|---|---|
  | 1 | 50m | 250m | 1000m |
  | 3 | 30m | 151m | 602m |
  | 5 | 25m | 127m | 509m |
  | 10 | 21m | 105m | 420m |
  | 20 | 18m | 91m | 363m |
  | 30 | 16m | 82m | 329m |
-->


### 2.5 · DBSCAN 参数

```yaml
dbscan:
  eps_m:
    home_city: 200       # P0.5 调优
    cross_province: 400
    cross_country: 800
  min_samples: 2
```

eps 取簇内**主流照片 context** 对应值; 跨 context 罕见, 取最严的。

⚠ eps 取值是经验值, 待 P0.5 真实数据调优 — 见 [OQ-012](./12_open_questions.md)(从 ADR-0005 spec §六 OQ-001 转入)。

### 2.6 · 匹配函数 (核心)

```python
def match_new_photo(new_photo, anchor, context, config) -> MatchResult:
    """返回 band + 诊断信息, 直接消费"""
    if not new_photo.has_gps:
        return MatchResult(band="none", reason="no_gps")

    # 场景 A: 有簇 → 对每簇算 hull+buffer 距离, 取最强档, strong 早返
    if anchor.clusters:
        best = ("none", None, None)
        for cluster in anchor.clusters:
            band, diag = match_against_cluster(new_photo, cluster, context, config)
            if band_priority[band] > band_priority[best[0]]:
                best = (band, cluster.cluster_id, diag)
            if band == "strong":
                break                          # ★ 早返优化
        return MatchResult(band=best[0], matched_target_type="cluster", ...)

    # 场景 B: 无簇仅 outlier → 点点距离取最近, 不用 buffer
    if anchor.outliers:
        return match_against_outliers(new_photo, anchor.outliers, context, config)

    # 场景 C: 完全空
    return MatchResult(band="none", reason="empty_anchor")
```

#### 子函数 1: match_against_cluster (hull + buffer)

```python
def match_against_cluster(new_photo, cluster, context, config) -> tuple[str, dict]:
    # ─── 算 buffer (ADR-0007: 统一 base, 不下钻 context) ───
    n = len(cluster.member_photo_ids)
    base = config.unified_buffer.base_m     # = 250m (unified)
    alpha = config.unified_buffer.alpha     # = 0.6
    decay = 1 + alpha * log(n) if n > 1 else 1.0
    buffer_m = base / decay

    # ─── 算 d ───
    if hull_contains(cluster.convex_hull, new_photo.gps):
        raw_d_m = 0.0
        d_m = 0.0
    else:
        raw_d_m = point_to_hull_distance_m(new_photo.gps, cluster.convex_hull)
        d_m = max(0.0, raw_d_m - buffer_m)

    # ─── 查档位 (ADR-0007: 统一表, 不下钻 context) ───
    band = distance_to_band(d_m)            # 读 cfg.unified_band_thresholds

    # ─── 高频低质量降档 (ADR-0006) ───
    low_q = is_low_quality_place(cluster, user_context, l1_data)
    if low_q.is_low_quality:
        band = downgrade_one_level(band)

    return band, {
        "cluster_id": cluster.cluster_id,
        "cluster_size": n,
        "raw_distance_m": raw_d_m,
        "buffer_m": buffer_m,
        "effective_distance_m": d_m,
        "context": context,                  # 仍写进 diag, 备 OQ-017 回切
        "band_table_used": "unified",        # 回切后变 "home_city"/"cross_province"/...
        "is_low_quality": low_q.is_low_quality,
        "low_quality_reason": low_q.signal_source,
    }
```

#### 子函数 2: match_against_outliers (点点距离)

```python
def match_against_outliers(new_photo, outliers, context, config) -> MatchResult:
    distances = [(o, haversine_m(new_photo.gps, o.gps)) for o in outliers]
    nearest, d_m = min(distances, key=lambda x: x[1])
    band = distance_to_band(d_m)            # ADR-0007: 统一表, 不下钻 context
    # outlier 模式不考虑高频降档 (没有 cluster 维度可降)
    return MatchResult(
        band=band,
        matched_target_type="outlier",
        matched_target_id=nearest.photo_id,
        diagnostics={
            "raw_distance_m": d_m,
            "buffer_m": 0,
            "effective_distance_m": d_m,
            "context": context,
        },
    )
```

### 2.7 · 增量更新 vs 全量重跑

新照片入相册后:

- **增量路径**: 算所属簇 (若距离簇成员 < eps), 更新该簇 hull + member_photo_ids + n。否则加入 outliers
- **每 10 张全量重跑**: 配置 `rerun.full_rerun_interval`, 给 outlier 转正机会

### 2.8 · 完整匹配场景

> ⚠ 以下示例**均按 v0.1 unified 档位 (ADR-0007)** 走 — strong/medium/weak = 500m/1000m/2000m, buffer base=250m. 原 per-context 示例见下方注释.

#### 场景 1: 3 张簇, 新照片到 hull 300m

```
n=3, buffer = 250 / (1 + 0.6·ln(3)) ≈ 151m
raw_d_m = 300m
d_m = max(0, 300 - 151) = 149m
查表: 149 ≤ 500 → strong ✓
```

#### 场景 2: 10 张簇, 新照片到 hull 800m

```
n=10, buffer = 250 / (1 + 0.6·ln(10)) ≈ 105m
d_m = max(0, 800 - 105) = 695m
查表: 695 ≤ 1000 → medium
```

#### 场景 3: 相册无簇, 只有 2 个 outlier

```
new_photo → outlier_1: 600m
new_photo → outlier_2: 1800m
取最近 outlier_1, d=600m
查表: 600 ≤ 1000 → medium
```

#### 场景 4: 多簇取最强 (strong 早返)

```
cluster_0: band=medium (continue)
cluster_1: band=strong (★ break)
不再算 cluster_2
最终: strong, matched_target=cluster_1
```

<!--
#### v0.2 回切后场景 (per-context, ADR-0005 原方案, OQ-017 触发)

场景 1: home_city, 3 张簇, 新照片到 hull 80m
  n=3, buffer = 50 / (1 + 0.6·ln(3)) ≈ 30m
  d_m = max(0, 80 - 30) = 50m
  查表: 50 ≤ 100 → strong ✓

场景 2: cross_country, 10 张簇, 新照片到 hull 800m
  n=10, buffer = 1000 / (1 + 0.6·ln(10)) ≈ 420m
  d_m = max(0, 800 - 420) = 380m
  查表: 380 ≤ 2000 → strong ✓

场景 3: home_city 相册无簇, 2 outlier
  new_photo → outlier_1: 150m → medium (150 ≤ 300)
-->


---

## 三、Theme Clusters (语义簇指纹, ADR-0008)

完整算法规范见 [docs/14_theme_aggregation.md](./14_theme_aggregation.md). 本节只放总览.

```python
class SemanticCluster(BaseModel):
    representative: str              # 簇代表 (簇内字面频次最高)
    members: dict[str, int]          # {字面: 频次}
    frequency: int                   # 簇总频次
    centroid: list[float]            # 加权平均归一化向量

# 指纹字段
theme_clusters: list[SemanticCluster]   # max 5, frequency 降序
theme_aggregated_at: datetime | None
```

**核心流程**: 全部 tag → 频次统计 → 批量 embed (Qwen3 / Mock) → 层次聚类 (cosine, merge_similarity=0.75) → 每簇加权聚合 → 按频次降序 → 截断 (≥ max×0.4, ≤ 5).

**匹配** (1 张新照片 vs 老相册 theme_clusters):

```
per_cluster_max_sim[j] = max_i cos(new_tag_i, cluster_j.centroid)
weight[j] = cluster_j.frequency / sum(all_freq)
score = sum_j (per_cluster_max_sim[j] × weight[j])
band ← {strong ≥ 0.75, medium ≥ 0.55, weak ≥ 0.35, else none}
```

**核心不变性**: 不对新 tag 取平均, 簇权重必用, 截断保留主流. 详见 [docs/14](./14_theme_aggregation.md) §四.

## 四、Event Aggregation (三级分层, ADR-0009)

完整算法规范见 [docs/15_event_aggregation.md](./15_event_aggregation.md). 本节只放总览.

```python
class EventAggregation(BaseModel):
    primary: str | None              # 主导 event (占比 ≥ 0.6)
    secondary: list[str]              # 次主导 (占比 ≥ 0.2)
    tertiary: list[str]               # 历史稀少 (count ≥ 1)
    distribution: dict[str, int]      # 完整分布
    total_events: int                 # 剔除 unknown 后总计

event_agg: EventAggregation
event_aggregated_at: datetime | None
```

**L1 枚举**: `event_hint` 从 6 扩到 10 — `meal/outing/gathering/celebration/performance/sports/work/study/daily_record/unknown` (ADR-0009 删 `family_visit/festival`, 新增 6 个).

**核心流程**: 过滤 unknown → Counter → 三级分层 (primary ≥ 60% / secondary ≥ 20% / tertiary count ≥ 1).

**匹配** (1 张新照片 vs 老相册 event_agg, 四档):

```
unknown          → none
== primary       → strong
in secondary     → medium
in tertiary      → weak
其他              → none
```

**核心不变性**: 单值枚举 / 10 枚举固定 / 三级分层把二元判断扩为四档 / 实时重算. 详见 [docs/15](./15_event_aggregation.md) §九.

## 五、其他指纹字段 (待 OQ-008 决策)

| 字段 | 当前 | 待规范 |
|---|---|---|
| `anchors_set` | meaning + object 并集 | OQ-008 §8e |
| 更新策略 (anchor) | 增量(部分)+ 30 天冻结 | OQ-008 §8h |

⚠ 在 OQ-008 §8d/8e/8h/8i 完成前, `tests/fixtures/albums/*.json` 这些字段是**手填**, 用作算法验证占位。
⚠ `theme_clusters` 已由 ADR-0008 解决, fixture 中需手填 mock embedding 表对应的 centroid 值 (见 [docs/14](./14_theme_aggregation.md) §七).

---

## 六、配置全集

- Place Anchor 配置: [config/place_anchor.yaml](../config/place_anchor.yaml)
- Theme Aggregation 配置: [config/theme_aggregation.yaml](../config/theme_aggregation.yaml)
- Event Aggregation 配置: [config/event_aggregation.yaml](../config/event_aggregation.yaml)

本文档不重复 yaml 内容, 修改阈值改 yaml, 算法逻辑改本文档 + docs/14 / docs/15.

---

## 七、关联

- Place Anchor 算法依据: [ADR-0005](../decisions/0005-place-anchor-dbch.md)
- v0.1 测试期距离档位修订: [ADR-0007](../decisions/0007-unified-location-bands.md) (临时塌缩, OQ-017 触发回切)
- Theme Clusters 算法依据: [ADR-0008](../decisions/0008-theme-semantic-clustering.md) + 完整规范 [docs/14_theme_aggregation.md](./14_theme_aggregation.md)
- Event Aggregation 算法依据: [ADR-0009](../decisions/0009-event-aggregation.md) + 完整规范 [docs/15_event_aggregation.md](./15_event_aggregation.md)
- 上层使用方: `src/features/growth_features.py::_compute_location` + `_compute_theme_match` + `_compute_event_match` (路径 A)
- 阈值同步: [ADR-0004](../decisions/0004-feature-assembler-revision.md) §3.2.1-new (location_score) — 本 ADR 用同一档位表, 但加 DBCH 结构化匹配 (v0.1 期同被 ADR-0007 塌缩); §3.2.3 (theme 路径 B 算法, 与 ADR-0008 路径 A 算法互补)
- 待补 OQ:
  - [OQ-008](./12_open_questions.md#oq-008-小集指纹合成-mini-album-fingerprint-synthesis) — 其他指纹字段 §8e/8h/8i (§8b/8c 已被 ADR-0008 关闭, §8d 已被 ADR-0009 关闭)
  - [OQ-020](./12_open_questions.md#oq-020-event-枚举与聚合调优) — event 枚举与聚合调优
  - [OQ-010](./12_open_questions.md) — user_home_city 推断
  - [OQ-011](./12_open_questions.md) — 空 anchor 情况
  - [OQ-012](./12_open_questions.md) — DBSCAN eps 调优
  - [OQ-017](./12_open_questions.md#oq-017-poi-城市判定接入后-location-档位回切计划) — POI 城市判定接入后回切三档
  - [OQ-018](./12_open_questions.md#oq-018-qwen-真实-embedding-接入与基准测试) — Qwen 真实 embedding 接入
  - [OQ-019](./12_open_questions.md#oq-019-语义聚类参数调优) — 语义聚类参数调优
