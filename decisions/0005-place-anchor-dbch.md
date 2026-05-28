# ADR-0005 · Place Anchor 算法 — DBSCAN + Bounded Convex Hull (DBCH)

> ⚠ **部分修订**:
> 1. 本 ADR 中的 `Cluster.is_high_freq` 字段已被 [ADR-0006](./0006-high-freq-low-quality-place.md) 重命名为 `is_low_quality` 且改为**实时计算, 不持久化** (原"build 时簇内多数派投票"也已弃用).
> 2. 本 ADR §2.3 距离档位 (三 context 阈值表) + §2.4 buffer base (50/250/1000m 三档) 在 v0.1 测试期已被 [ADR-0007](./0007-unified-location-bands.md) 临时塌缩为**单一表** (strong/medium/weak = 500m/1000m/2000m, buffer base = 250m). 原因: `user_home_city` 仅 stub (OQ-010), 三档归因复杂. POI 接入后回切, 见 [OQ-017](../docs/12_open_questions.md#oq-017-poi-城市判定接入后-location-档位回切计划).
>
> 其余 DBCH 算法核心 (DBSCAN 算法本身 / Hull 构造 / Buffer 公式 / 匹配函数结构 / 增量与重跑策略) **不变**, 仍以本 ADR 为准.

| 字段 | 值 |
|---|---|
| 状态 | accepted (字段 `is_high_freq` 部分被 ADR-0006 修订; 距离档位 + buffer base 部分被 ADR-0007 v0.1 测试期 supersede) |
| 决策日期 | 2026-05-13 |
| 决策人 | Ace (产品/增长) — 来自 `archive/specs/Place_Anchor_Spec_Final.md` v0.5 (2026-05-12, 已归档) |
| 影响范围 | `src/contracts/{place_anchor,growth}.py` + `src/mini_album/place_anchor.py` (新增) + `src/features/growth_features.py::_compute_location` + `config/place_anchor.yaml` + `docs/10_mini_album_schema.md` + `tests/fixtures/albums/*.json` |
| 相关文档 | `docs/10_mini_album_schema.md`, `archive/specs/Place_Anchor_Spec_Final.md` (原始 spec, 已归档) |
| 关联 OQ | 解决 [OQ-008 §8a / §8f](../docs/12_open_questions.md#oq-008-小集指纹合成-mini-album-fingerprint-synthesis); 部分解决 §8g; 引发 OQ-010 / OQ-011 |
| 关联 ADR | 与 [ADR-0004](./0004-feature-assembler-revision.md) §3.2.1-new 互补 (后者 v1.3.2 location_score 用三档阈值; **本 ADR 用同一阈值表但加 DBCH 结构化匹配**) |

---

## 1 · 背景

[ADR-0004](./0004-feature-assembler-revision.md) §3.2.1-new 提出 location_score 引入地理上下文(home_city / cross_province / cross_country)+ 不同距离阈值表。但仍是**单点 GPS 比单点 GPS** 的逻辑,对**多张老照片聚合**(指纹)没给出算法。

实际路径 A 用 1 张新照片 vs 1 个聚合 `gps_center`(几何中心)做匹配,有几个问题:
- 老相册照片可能**多个聚集区**(例如"西湖一日"包含湖边 + 雷峰塔 + 河坊街三处),单一 gps_center 失真
- outlier 照片(误差 GPS / 偶然路过)会**污染** gps_center,把它拉偏
- 简单 haversine 不能描述**形状**(线性沿岸 vs 圆形景区差异巨大)
- 越多老照片应该越精准,当前算法没体现"样本量增加 → 置信度提升"

---

## 2 · 决策 — DBCH 算法

### 2.1 · 数据结构 (替换原 PlaceAnchor)

```
PlaceAnchor
├── clusters: list[Cluster]      # DBSCAN 成簇的聚集区
│   ├── cluster_id
│   ├── member_photo_ids
│   ├── convex_hull              # 凸包顶点 (lat, lng) 列表
│   ├── centroid                 # 几何中位数
│   ├── is_high_freq             # 是否高频地点 (整簇)
│   └── (匹配时算 buffer_m, 不预存)
└── outliers: list[OutlierPoint] # 未成簇的孤立照片
    ├── photo_id
    └── gps
```

**核心不变性**:
- 一张照片**要么属于某个簇,要么是 outlier**, 二者必居其一
- outlier 不进任何凸包, 不参与基于 hull 的匹配
- 每 10 张照片全量重跑 DBSCAN, outlier 有机会"转正"

### 2.2 · Context 判定 (按 ADR-0004)

| context | 触发条件 |
|---|---|
| `home_city` | 照片 GPS 在用户常驻城市半径内 |
| `cross_province` | 不在常驻城市, 但同省 |
| `cross_country` | 跨国 |

判定时算, 不预存(用户搬家后同一张照片的 context 可能从 home_city 变 cross_province)。

⚠ `user_home_city` 推断模块本 ADR **不展开**, 是 P0 前置依赖 — 见 [OQ-010](../docs/12_open_questions.md)。Demo 用硬编码 stub。

### 2.3 · 距离档位表 (绝对值, 与 ADR-0004 §3.2.1-new 一致)

```yaml
band_thresholds:
  home_city:        { strong_m: 100,  medium_m: 300,   weak_m: 800 }
  cross_province:   { strong_m: 500,  medium_m: 1500,  weak_m: 5000 }
  cross_country:    { strong_m: 2000, medium_m: 5000,  weak_m: 15000 }
```

`d ≤ strong_m → strong / d ≤ medium_m → medium / d ≤ weak_m → weak / 其余 → none`

### 2.4 · Buffer 公式 (簇置信宽容度)

```
buffer = base / (1 + 0.6 × ln(n))
```

- `base = strong_m / 2` (各 context: 50m / 250m / 1000m)
- `n` = 簇内点数
- `alpha = 0.6` 三 context 共用

**衰减特征**: n=1 时 buffer = base (最宽容), n=5 时减半, n=30 时降到约 1/3, **永不归零**。

### 2.5 · 匹配函数 (返回 band 直接, 跳过 score → band 转换)

```python
def match_new_photo(new_photo, anchor, context, config) -> MatchResult:
    if not new_photo.has_gps:
        return MatchResult(band="none", reason="no_gps")

    # 场景 A: 有簇 — 对每个簇算 hull + buffer 距离, 取最强档, strong 早返
    if anchor.clusters:
        best = ("none", None, None)
        for cluster in anchor.clusters:
            band, diag = match_against_cluster(new_photo, cluster, context, config)
            if band_priority[band] > band_priority[best[0]]:
                best = (band, cluster.cluster_id, diag)
            if band == "strong":
                break   # ★ 早返
        return MatchResult(band=best[0], matched_target_type="cluster", ...)

    # 场景 B: 无簇仅 outlier — 点点距离, 取最近, 不用 buffer
    if anchor.outliers:
        return match_against_outliers(new_photo, anchor.outliers, context, config)

    # 场景 C: 完全空
    return MatchResult(band="none", reason="empty_anchor")
```

### 2.6 · 增量更新 vs 全量重跑

- **增量**: 新照片入簇 → 该簇 n+1, hull 重算
- **全量**: 每 10 张照片(配置 `rerun.full_rerun_interval`)重跑一次 DBSCAN, 给 outlier 转正机会

---

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| **A. 简单几何中心 + 半径**(原 v0.1) | 多聚集区失真、outlier 污染、不描述形状 |
| **B. K-Means 聚类** | 需要预设 K, 对小样本不稳, 不能产生 outlier |
| **C. 单一凸包覆盖所有点** | outlier 会撑爆 hull, 单一 outlier 把"湖边"和"街区"全圈进去 |
| **D. DBSCAN 但只取最大簇** | 丢失多聚集区信息, 不能解释"两个独立子区域" |
| **E. DBSCAN + Hull + Buffer (采用)** | 自然识别多簇 + outlier 隔离 + 形状感知 + buffer 表达置信度衰减 |

---

## 4 · 影响范围

### 契约变更 (`src/contracts/place_anchor.py` 新建)

新类型:
- `Cluster` (cluster_id / member_photo_ids / convex_hull / centroid / is_high_freq)
- `OutlierPoint` (photo_id / gps)
- `MatchResult` (band / matched_target_type / matched_target_id / diagnostics)
- `AnchorConfig` (加载 yaml 后的 typed 配置)

### 现有契约修改 (`src/contracts/growth.py`)

`PlaceAnchor` 字段**重构**:
- 移除: `gps_center` / `gps_radius_m` (单一中心+半径)
- 新增: `clusters: list[Cluster]` + `outliers: list[OutlierPoint]`
- 保留: `is_high_frequency_anchor` (相册级标志, 来自 cluster 投票)
- 保留: `place_cluster_id` (用户级地点聚类 id, 与本算法无关)

### 新增算法模块 (`src/mini_album/place_anchor.py`)

纯 Python 实现:
- `dbscan_cluster(points, eps_m, min_samples)` — O(n²) DBSCAN
- `convex_hull(points)` — Andrew's monotone chain
- `point_to_hull_distance_m(point, hull)` — 点到凸包距离 (含 contains 判定)
- `compute_buffer_m(n, base_m, alpha)` — buffer 公式
- `match_new_photo(...)` / `match_against_cluster(...)` / `match_against_outliers(...)`
- `build_place_anchor(photos, context, config)` — 从照片构造 PlaceAnchor

### 配置 (`config/place_anchor.yaml` 新建)

完整搬 spec §十一 (band_thresholds / buffer / dbscan / rerun)。

### `src/features/growth_features.py::_compute_location` 重写

旧版本:
```python
dist_km = haversine_km(p.exif_location, album.place_anchor.gps_center)
return 分段函数(dist_km)
```

新版本:
```python
context = infer_context(p, user_home_city)
match_result = match_new_photo(p, album.place_anchor, context, config)
return match_result   # 返回 band 直接, 不返回 score
```

### `compute_growth_bands` 调整

location band 不再走"score → 阈值"路径, 直接消费 `match_result.band`。

---

## 5 · 决策回滚条件

如果 DBCH 在 v0.2 真实数据上表现劣于 v0.1, 触发以下任一条件即回滚 (改 config feature flag):

- **eps 误聚率 > 15%**(本属不同区域的照片被聚成一簇)
- **outlier 转正率 < 5%**(每 10 张全量重跑几乎不让 outlier 转正,说明 eps 太小)
- **buffer 抵扣后 strong 命中率反而下降 > 20%**(说明 buffer 公式偏严)

回滚动作: `config/place_anchor.yaml` 加一行 `algorithm: "v01_haversine"`, 代码层支持双轨。

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-008 §8a (gps_center 算法) | 推荐几何中心 | **被本 ADR 解决** — 改为 DBSCAN 簇 centroids (多个) |
| OQ-008 §8f (gps_radius_m) | 推荐 90 分位 | **被本 ADR 解决** — 改为 hull + buffer (Hull 描述形状, buffer 描述置信度) |
| OQ-008 §8g (is_high_freq) | 推荐多数派 | **部分解决** — 现在是 cluster 级 `is_high_freq`, 但相册级 `is_high_frequency_anchor` 仍待 OQ-008 决策 |
| OQ-008 §8h (更新策略) | 推荐增量 | **被本 ADR 部分覆盖** — 增量更新簇 hull + 每 10 张全量重跑 |
| OQ-010 (新增) | — | user_home_city 推断模块 (P0 前置依赖) |
| OQ-011 (新增) | — | 相册完全为空 (无簇无 outlier) 是否可能 |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完 + spec 转入
2. ✅ `docs/10_mini_album_schema.md` 新建 (place_anchor 段)
3. ✅ `config/place_anchor.yaml` 新建
4. ✅ 新契约 + 现有契约调整
5. ✅ 算法实现 (纯 Python, 无外部依赖)
6. ✅ `_compute_location` 重写
7. ✅ Fixture 校准 (照片 GPS 紧凑到 100m 内确保 DBSCAN 能成簇)
8. ✅ 单元测试 + 场景测试 + golden 刷新
9. ⏳ v0.2: 接入真实 user_home_city 模块 (OQ-010)
10. ⏳ v0.2: P0.5 调优 eps 参数 (spec §六)
