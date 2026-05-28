# Place Anchor 算法规范 · 最终版

> **算法名**: DBSCAN + Bounded Convex Hull (DBCH)
> **适用**: Seenful Mini Album 的 `place_anchor` 字段生成与匹配
> **版本**: v0.5 · 2026-05-12

---

## 一、核心思想

新照片来时,判断它是否属于某本相册的某个聚集区域。
匹配输出统一的距离档位:**strong / medium / weak / none**。

设计三条原则:

1. **DBSCAN 分簇,outlier 独立** —— 一本相册可能有多个聚集区,outlier 不污染 hull
2. **凸包 + buffer** —— hull 描述形状,buffer 描述置信宽容度
3. **buffer 随簇大小衰减** —— 越用越准,但永不归零

---

## 二、关键数据结构

```
PlaceAnchor (挂在 Mini Album 上)
├── clusters: list[Cluster]      # 已成簇的聚集区
│   ├── cluster_id
│   ├── member_photo_ids
│   ├── convex_hull              # 凸包几何
│   ├── centroid                 # 几何中位数
│   └── buffer_m                 # 当前 buffer (随 n 衰减)
└── outliers: list[OutlierPoint] # 未成簇的孤立照片
    ├── photo_id
    └── gps
```

**关键性质**:

- 一张照片要么属于某个簇,要么是 outlier,二者必居其一
- outlier 不进任何凸包,不参与基于 hull 的匹配
- outlier 在全量重跑时有机会"转正"为簇成员

---

## 三、Context 判定

Context 是用户层级属性,基于用户高频 GPS 推断:

```python
def infer_user_home_city(user_id) -> CityRegion:
    """
    用户高频地点聚类 → 推断常驻城市
    返回: 一个 (city_center_gps, city_radius_km) 区域
    """
    # 实现细节: P0 单独模块,本文档不展开
    pass


def get_context_for_photo(photo: Photo, user_home_city: CityRegion) -> str:
    """每张照片独立判定 context"""
    d_km = haversine_km(photo.gps, user_home_city.center)
    
    if d_km < user_home_city.radius_km:
        return "home_city"
    
    if same_province(photo.gps, user_home_city.center):
        return "cross_province"
    
    return "cross_country"
```

**注意**: photo 的 context 是**判定时算出来的**,不预存。同一张照片可能在用户搬家后从 home_city 变 cross_province。

---

## 四、距离档位表 (绝对值,不随 n 变化)

```yaml
band_thresholds:
  home_city:
    strong_m: 100
    medium_m: 300
    weak_m: 800
  cross_province:
    strong_m: 500
    medium_m: 1500
    weak_m: 5000
  cross_country:
    strong_m: 2000
    medium_m: 5000
    weak_m: 15000
```

距离 → 档位:
```
d ≤ strong_m  → strong
d ≤ medium_m  → medium
d ≤ weak_m    → weak
d >  weak_m   → none
```

---

## 五、Buffer 公式

```
buffer = base / (1 + 0.6 × log(n))
```

- **base**: 每个 context 一个,取 strong 距离的一半
- **n**: 簇内点数
- **alpha = 0.6**: 三 context 共用

### Buffer base 配置

```yaml
buffer:
  alpha: 0.6
  base_m:
    home_city: 50       # = strong / 2 (100/2)
    cross_province: 250 # = strong / 2 (500/2)
    cross_country: 1000 # = strong / 2 (2000/2)
```

### Buffer 衰减表

| n | home buffer | province buffer | country buffer |
|---|---|---|---|
| 1 | 50m | 250m | 1000m |
| 3 | 30m | 151m | 602m |
| 5 | 25m | 127m | 509m |
| 10 | 21m | 105m | 420m |
| 20 | 18m | 91m | 363m |
| 30 | 16m | 82m | 329m |

**衰减特征**: n=5 时衰到一半,n=30 时衰到约 1/3,永不归零。

---

## 六、DBSCAN 参数

```yaml
dbscan:
  eps_m:
    home_city: 200       # P0.5 调优
    cross_province: 400  # P0.5 调优
    cross_country: 800   # P0.5 调优
  min_samples: 2
```

**判定逻辑**: DBSCAN 用的 eps 取**簇内主流照片的 context**对应的值。如果一个相册跨 context(罕见),取最严的 eps。

> **OQ-001**: eps 取值经验值,需场景测试验证。是否应该按 1.5× strong 重新校准?

---

## 七、匹配函数 (核心)

新照片 P 到来时,对相册做匹配,返回档位:

```python
def match_new_photo(
    new_photo: Photo,
    anchor: PlaceAnchor,
    context: str,
    config: AnchorConfig
) -> MatchResult:
    """
    返回 strong / medium / weak / none + 诊断信息
    
    分两种情况:
    1. 相册已有簇 → 对每个簇算 hull+buffer 距离,取最强档,strong 早返
    2. 相册没有簇,只有 outlier → 对每个 outlier 算点点距离,取最近的查档位
    """
    if not new_photo.has_gps:
        return MatchResult(band="none", reason="no_gps")
    
    # ============ 场景 A: 有簇 ============
    if len(anchor.clusters) > 0:
        band_priority = {"strong": 3, "medium": 2, "weak": 1, "none": 0}
        best = ("none", None, None)
        
        for cluster in anchor.clusters:
            band, diag = match_against_cluster(new_photo, cluster, context, config)
            
            if band_priority[band] > band_priority[best[0]]:
                best = (band, cluster.cluster_id, diag)
            
            # ★ Strong 早返优化
            if band == "strong":
                break
        
        return MatchResult(
            band=best[0],
            matched_target_type="cluster",
            matched_target_id=best[1],
            diagnostics=best[2]
        )
    
    # ============ 场景 B: 无簇,只有 outlier ============
    if len(anchor.outliers) > 0:
        return match_against_outliers(new_photo, anchor.outliers, context, config)
    
    # ============ 场景 C: 相册完全为空 ============
    return MatchResult(band="none", reason="empty_anchor")
```

### 子函数 1: 匹配某个簇 (hull + buffer)

```python
def match_against_cluster(
    new_photo: Photo,
    cluster: Cluster,
    context: str,
    config: AnchorConfig
) -> tuple[str, dict]:
    """
    1. 算 buffer (随簇大小)
    2. 算 d = 新点到 (hull + buffer 区域) 的距离
    3. 查档位表
    """
    # ---- 算 buffer ----
    n = len(cluster.member_photo_ids)
    base = config.buffer.base_m[context]
    alpha = config.buffer.alpha
    
    decay = 1 + alpha * math.log(n) if n > 1 else 1.0
    buffer_m = base / decay
    
    # ---- 算 d ----
    hull = wkt_load(cluster.convex_hull_wkt)
    point_geom = Point(new_photo.gps)
    
    if hull.contains(point_geom):
        d_m = 0.0
        raw_distance_m = 0.0
    else:
        raw_distance_m = degrees_to_meters(
            hull.distance(point_geom),
            lat=new_photo.gps[1]
        )
        # buffer 抵扣
        d_m = max(0.0, raw_distance_m - buffer_m)
    
    # ---- 查档位 ----
    band = distance_to_band(d_m, context, config)
    
    # ---- 高频地点降档 ----
    if cluster.is_high_freq:
        band = downgrade_one_level(band)
    
    return band, {
        "cluster_id": cluster.cluster_id,
        "cluster_size": n,
        "raw_distance_m": raw_distance_m,
        "buffer_m": buffer_m,
        "effective_distance_m": d_m,
        "context": context,
        "is_high_freq": cluster.is_high_freq
    }
```

### 子函数 2: 匹配 outlier (点点距离,无 buffer)

```python
def match_against_outliers(
    new_photo: Photo,
    outliers: list[OutlierPoint],
    context: str,
    config: AnchorConfig
) -> MatchResult:
    """
    无簇场景: 取距离最近的 outlier 算点点距离,直接查档位表。
    不用 buffer (没有 hull 可外扩)。
    """
    distances = [
        (o, haversine_m(new_photo.gps, o.gps))
        for o in outliers
    ]
    nearest_outlier, d_m = min(distances, key=lambda x: x[1])
    
    band = distance_to_band(d_m, context, config)
    # outlier 模式不考虑高频降档 (因为没有 cluster 维度可降)
    
    return MatchResult(
        band=band,
        matched_target_type="outlier",
        matched_target_id=nearest_outlier.photo_id,
        diagnostics={
            "raw_distance_m": d_m,
            "buffer_m": 0,
            "effective_distance_m": d_m,
            "context": context,
            "is_first_match_in_album": True
        }
    )
```

### 共用工具

```python
def distance_to_band(d_m: float, context: str, config: AnchorConfig) -> str:
    th = config.band_thresholds[context]
    if d_m <= th["strong_m"]:
        return "strong"
    elif d_m <= th["medium_m"]:
        return "medium"
    elif d_m <= th["weak_m"]:
        return "weak"
    else:
        return "none"


def downgrade_one_level(band: str) -> str:
    return {"strong": "medium", "medium": "weak", "weak": "none", "none": "none"}[band]
```

---

## 八、增量更新 vs 全量重跑

新照片入簇后:
- **增量路径**: 该簇 n+1, buffer 重算, hull 重算
- **每 10 张全量重跑一次 DBSCAN**: 给 outlier 转正机会

具体流程见 `Place_Anchor_DBSCAN_Hull_Pseudocode.md` (v0.1) 第五节。

---

## 九、几个完整匹配场景

### 场景 1: home_city,3 张簇,新照片 80m

```
n=3, buffer = 50/(1+0.6×log(3)) = 30m
new_photo 到 hull 距离: 80m
effective_d = max(0, 80-30) = 50m
查表: 50 ≤ 100 → strong ✓
```

### 场景 2: cross_country,10 张簇,新照片到 hull 距离 800m

```
n=10, buffer = 1000/(1+0.6×log(10)) = 420m
effective_d = max(0, 800-420) = 380m
查表: 380 ≤ 2000 → strong ✓
```

### 场景 3: home_city 相册无簇,只有 2 个 outlier

```
new_photo 到 outlier_1: 150m
new_photo 到 outlier_2: 600m
取最近: outlier_1, d=150m
查表: 150 ≤ 300 → medium
```

### 场景 4: 多簇取最强(strong 早返)

```
对 cluster_0: band=medium (continue)
对 cluster_1: band=strong (★ break)
不再算 cluster_2
最终: strong, matched_target=cluster_1
```

---

## 十、Schema 输出统一

无论命中 cluster 还是 outlier,返回结构一致:

```python
class MatchResult:
    band: Literal["strong", "medium", "weak", "none"]
    matched_target_type: Literal["cluster", "outlier", None]
    matched_target_id: str | None
    diagnostics: dict   # raw_distance / buffer / effective_distance / context 等
```

`band` 是真值表唯一消费的字段,`diagnostics` 用于落痕排查。

---

## 十一、配置全集 (config/place_anchor.yaml)

```yaml
# 距离档位 (绝对值)
band_thresholds:
  home_city:
    strong_m: 100
    medium_m: 300
    weak_m: 800
  cross_province:
    strong_m: 500
    medium_m: 1500
    weak_m: 5000
  cross_country:
    strong_m: 2000
    medium_m: 5000
    weak_m: 15000

# Buffer 配置
buffer:
  alpha: 0.6
  base_m:
    home_city: 50
    cross_province: 250
    cross_country: 1000

# DBSCAN 参数 (P0.5 调优)
dbscan:
  eps_m:
    home_city: 200
    cross_province: 400
    cross_country: 800
  min_samples: 2

# 重跑策略
rerun:
  full_rerun_interval: 10
```

---

## 十二、待补 OQ

| 编号 | 问题 | 优先级 |
|---|---|---|
| OQ-001 | user_home_city 推断模块的具体实现规范 | P0 (前置依赖) |
| OQ-002 | 相册完全为空 (无簇无 outlier) 是否可能发生 | P0 |

---

## 十三、核心不变性

```
1. band 输出 ∈ {strong, medium, weak, none},schema 永远统一
2. 同一相册多簇时,band = 最强簇的 band
3. 命中 strong 即早返,不再算其他簇
4. 无簇但有 outlier 时,退化为点点距离匹配,不用 buffer
5. outlier 不进任何凸包,不参与基于 hull 的匹配
6. buffer 随 n 单调不增 (越用越严),永不为 0
7. 距离档位本身是绝对值,不随 n 变化
8. context 是查询时算的,不预存
```

---

*v0.5 终版 · 待 KY 评审后转 ADR-0005*
