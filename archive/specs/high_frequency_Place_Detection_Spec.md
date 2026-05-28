# 低质量地点判定 · 开发文档

> **版本**: v0.2
> **日期**: 2026-05-12

---

## 一、背景

L2 的 location 维度成集仅看单一 location strength，不检查内容关联度。

这导致一个问题：**家里 / 公司的照片也会因为 GPS 接近被聚合成集**，但这些照片之间内容松散、缺乏纪念意义，聚合后是一本"低质量小集"，用户体验差。

**关键区分** ——

| 类型 | 例子 | 是否应该聚合 |
|---|---|---|
| 高频 + 高质量 | 家附近常去的公园 | ✓ 应该 |
| 高频 + 低质量 | 家 / 公司 / 学校 | ✗ 不应该 |

**所以这个判定不是"高频地点"判定，而是"高频低质量地点"判定**。命中后，该 cluster 在 location 维度匹配时整体降一档（strong→medium / medium→weak / weak→none），避免被强制聚合。

---

## 二、两个方案

PlanA 为优先方案，但由于关键schema字段未验证，Plan B进行兜底

| 方案 | 质量信号 | 状态 |
|---|---|---|
| **Plan A** | L1 关键信号：meaning_density，aesthetic_density  | 默认启用 |
| **Plan B** | POI + NIMA + B/C/D 行为信号 | Plan A 验证失败后启用，需要 L1 改输出 NIMA |

两个方案共用同一个**频率信号**作为必须门槛。

---

## 三、共用 · 频率信号 (必须门槛)

```python
def pass_frequency_check(cluster, user, user_history, config) -> bool:
    """
    必须信号，任一不过直接判 not low_quality。
    """
    # 新用户保护
    if user.account_age_days < 30:
        return False
    if len(user_history) < 10:
        return False
    
    # 频率: 30 天内该簇 ≥ 5 个不同日子拍摄
    cluster_photo_ids = set(cluster.member_photo_ids)
    cutoff = datetime.now() - timedelta(days=30)
    
    recent_in_cluster = [
        p for p in user_history
        if p.photo_id in cluster_photo_ids
        and p.captured_at >= cutoff
    ]
    
    distinct_days = len(set(p.captured_at.date() for p in recent_in_cluster))
    return distinct_days >= 5
```

```yaml
frequency:
  radius_m: 500
  lookback_days: 30
  min_distinct_days: 5
  new_user_min_age_days: 30
  new_user_min_photos: 10
```

---

## 四、Plan A · L1 双 density (代码实现)

**状态**: 默认启用，但 L1 双 density 字段未验证。

### 用户个人 baseline

防"不会拍照"用户被全部误判低质量，阈值用**用户自己**的 25 分位数。

```python
@dataclass
class UserDensityBaseline:
    meaning_threshold: float    # 用户照片 meaning_density 的 25 分位
    aesthetic_threshold: float  # 用户照片 aesthetic_density 的 25 分位
    last_computed_at: datetime


def compute_user_density_baseline(user_history, config) -> Optional[UserDensityBaseline]:
    """
    用户照片不足 25 张时返回 None,此时 baseline 不可用 → 不判低质量
    """
    photos_with_l1 = [p for p in user_history if p.l1_output is not None]
    
    if len(photos_with_l1) < config.min_samples_for_baseline:
        return None
    
    meaning_values = [p.l1_output.meaning_density for p in photos_with_l1]
    aesthetic_values = [p.l1_output.aesthetic_density for p in photos_with_l1]
    
    return UserDensityBaseline(
        meaning_threshold=percentile(meaning_values, 25),
        aesthetic_threshold=percentile(aesthetic_values, 25),
        last_computed_at=datetime.now()
    )
```

### 双低占比判定

```python
def signal_l1_density(cluster, l1_data, user_baseline) -> bool:
    """
    簇内 ≥ 50% 照片满足 "meaning_density 和 aesthetic_density 都低于用户 baseline"
    → 低质量地点
    """
    if user_baseline is None:
        return False  # baseline 不可用,保守判否
    
    member_l1 = [l1_data[pid] for pid in cluster.member_photo_ids]
    
    double_low_count = sum(
        1 for p in member_l1
        if p.meaning_density < user_baseline.meaning_threshold
        and p.aesthetic_density < user_baseline.aesthetic_threshold
    )
    
    return double_low_count / len(member_l1) >= 0.5
```

### Plan A 主入口

```python
def is_low_quality_plan_a(cluster, user, user_history, l1_data, baseline, config):
    # Step 1: 频率门槛
    if not pass_frequency_check(cluster, user, user_history, config):
        return False
    
    # Step 2: L1 density 质量判定
    return signal_l1_density(cluster, l1_data, baseline)
```

### Plan A 配置

```yaml
plan_a:
  enabled: true
  baseline_percentile: 25
  min_samples_for_baseline: 25
  baseline_refresh_days: 30
  double_low_ratio: 0.5
```

---

## 五、Plan B · POI + NIMA + 行为信号 (仅伪代码)

**状态**: Plan A 验证失败后启用。需要 L1 模型改输出 NIMA 评分替换 density 字段。

### Plan B 决策流程

```
Step 1: 频率门槛 (同 Plan A)
   ↓
Step 2.1: POI 信号
  ├─ likely_routine → return True
  ├─ non_routine    → return False
  └─ unknown        → 继续 Step 2.2
   ↓
Step 2.2: NIMA 评分 E (相对用户 clean baseline)
  ├─ E < mean - 1σ        → return True  (明显低于均值)
  ├─ mean - 1σ ≤ E < mean → 继续 Step 2.3 (略低于均值)
  └─ E ≥ mean             → return False (不低于均值)
   ↓
Step 2.3: B/C/D 行为信号
  ├─ B · 当日 7h 跨度
  ├─ C · 工作日为主
  └─ D · 室内场景占比
  
  判定:
    公司 = B + C + D 任 2 个命中
    家   = B + D 都命中
    任一命中 → True，否则 False
```

### Plan B 伪代码

```
function is_low_quality_plan_b(cluster, user, user_history, photo_meta, l1_data):
    if not pass_frequency_check(cluster, user, user_history):
        return False
    
    # POI 信号 (客户端 CLGeocoder + MKLocalSearch 上传时附带)
    poi = signal_poi(cluster, photo_meta)
    if poi == "likely_routine":
        return True
    if poi == "non_routine":
        return False
    
    # NIMA 评分,baseline 需去污染
    clean_baseline = compute_clean_nima_baseline(user_history)
    e = avg_nima_score(cluster, l1_data)
    
    if e < clean_baseline.mean - 1 * clean_baseline.std:
        return True
    if e >= clean_baseline.mean:
        return False
    
    # 略低于均值，走 B/C/D
    b = check_overnight_span_7h(cluster, user_history)
    c = check_weekday_dominant(cluster, user_history)
    d = check_indoor_scene(cluster, l1_data)
    
    is_office = sum([b, c, d]) >= 2
    is_home = b and d
    
    return is_office or is_home
```

### NIMA Baseline 防污染

```
function compute_clean_nima_baseline(user_history):
    # 1. 识别用户的高频 cluster (有低质量嫌疑)
    high_freq_clusters = identify_high_freq_clusters(user_history)
    
    # 2. 排除这些 cluster 的照片
    clean_photos = [
        p for p in user_history
        if p.cluster_id not in high_freq_clusters
        and p.nima_score is not None
    ]
    
    if len(clean_photos) < 30:
        return None  # 干净样本不足
    
    # 3. 用剩余样本算 mean 和 σ
    return {
        "mean": mean([p.nima_score for p in clean_photos]),
        "std": stdev([p.nima_score for p in clean_photos])
    }
```

**为什么防污染**: 如果用户大量照片在家/公司，未过滤直接算均值，会把均值拉低，导致家/公司照片"看起来正常"，漏判。

### B/C/D 三个信号定义

```
B · 当日 7h 跨度
  → 30 天内该簇有 ≥ 3 个不同日子，首尾拍摄间隔 ≥ 7 小时

C · 工作日为主  
  → 30 天内该簇拍摄 ≥ 80% 在工作日

D · 室内场景
  → 簇内 ≥ 70% 照片的 semantic_facts.scene_type ∈ {"home", "indoor"}
```

### Plan B 配置

```yaml
plan_b:
  enabled: false  # Plan A 验证失败后切 true
  
  poi:
    non_routine_categories:
      [park, beach, museum, amusement_park, aquarium, zoo,
       stadium, movie_theater, restaurant, cafe, bar, hotel,
       library, cinema]
    non_routine_ratio_threshold: 0.3
    likely_routine_ratio_threshold: 0.6
  
  nima:
    sigma_threshold: 1.0  # E < mean - 1σ 直接判低质量
    min_clean_samples: 30
  
  behavior:
    overnight_span_hours: 7
    min_long_span_days: 3
    weekday_ratio_threshold: 0.8
    indoor_ratio_threshold: 0.7
```

---

## 六、主入口 (方案分发)

```python
def is_low_quality_place(cluster, user, user_history, photo_meta, l1_data, baseline, config):
    if config.plan_a.enabled:
        return is_low_quality_plan_a(cluster, user, user_history, l1_data, baseline, config)
    elif config.plan_b.enabled:
        return is_low_quality_plan_b(cluster, user, user_history, photo_meta, l1_data, config)
    else:
        return False  # 两个都关,不判低质量
```

---

## 七、Case 验证 (Plan A)

| Case | 描述 | 频率 | L1 density 双低占比 | 判定 |
|---|---|---|---|---|
| 1 | 杭州家 | ✓ | 75% (流水账多) | **低质量 ✓** |
| 2 | 常去公园 | ✓ | 20% (照片有调性) | **非低质量 ✓** |
| 3 | 公司工位 | ✓ | 80% | **低质量 ✓** |
| 4 | 度假酒店 5 天 | ✗ (只 5 天，可能不达频率) | - | **非低质量 ✓** |
| 5 | 搬家后老家 | ✗ (30 天 0 次) | - | **非低质量 ✓** 自动遗忘 |
| 6 | 新用户家 | ✗ (注册 < 30 天) | - | **非低质量 ✓** 保护期 |
| 7 | 不会拍照用户的家 | ✓ | 取决于用户 baseline | 个人 baseline 校准后正确判定 |

---

## 八、降级使用

新照片匹配命中某个 cluster 时:

```python
if is_low_quality_place(cluster, ...):
    band = downgrade_one_level(band)
# strong → medium
# medium → weak  
# weak   → none
```

判定**实时计算，不持久化**，支持滚动窗口自动遗忘。

---

## 九、待补 OQ

| OQ | 问题 | 优先级 |
|---|---|---|
| OQ-1 | L1 双 density 验证标准 (达多少准确率算可用) | P0 (依赖 L1 测试) |
| OQ-2 | baseline 25 分位是否合理 | P0.5 |
| OQ-3 | Plan A 失败的判定标准 (上线观察期多久) | P0 |
| OQ-4 | Plan B 启用时 L1 模型改输出 NIMA 的工程改造 | P0.5 |

---

## 十、核心不变性

1. **频率门槛是硬约束**，不满足直接 return False
2. **Plan A / Plan B 替代关系**，不同时运行
3. **判定不持久化，实时计算**，自动遗忘
4. **个人 baseline / NIMA baseline 防污染** —— 用户的"低质量"是相对用户自己的
5. **降级只影响 location 维度**，event/theme 等其他维度独立工作

---

*v0.2 · 2026-05-12 · Plan A 上线后观察，决定是否切 Plan B*
