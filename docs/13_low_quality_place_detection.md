# 13 · 高频低质量地点判定 (Low Quality Place Detection)

> 决策来源: [ADR-0006](../decisions/0006-high-freq-low-quality-place.md)
> 原始 spec: `archive/specs/high_frequency_Place_Detection_Spec.md` v0.2

## 一、背景与目标

L2 的 location 维度成集只看 location strength,不区分内容质量。这导致**家/公司**这种高频地点的照片被强制聚合成"低质量小集"(松散、无纪念意义)。

**关键区分**:

| 类型 | 例子 | 是否应降档 |
|---|---|---|
| 高频 + 高质量 | 家附近常去的公园 | ❌ 不降档 |
| 高频 + 低质量 | 家 / 公司 / 学校 | ✅ 降档 |

判定的目标不是"高频地点"而是"**高频** + **低质量**"合取。命中后该 cluster 在 location 匹配时**整体降一档**:

```
strong → medium → weak → none
```

## 二、两个方案

| 方案 | 质量信号 | 状态 |
|---|---|---|
| **Plan A** | L1 双 density (meaning_density + aesthetic_density) | **默认启用** |
| **Plan B** | POI + NIMA + 行为信号 B/C/D | 留 stub, Plan A 验证失败后启用 |

共用 **频率信号** 作为必须门槛。

## 三、共用 · 频率门槛 (硬约束)

```python
def pass_frequency_check(cluster, user, user_history, cfg) -> bool:
    # 新用户保护
    if user.account_age_days < cfg.frequency.new_user_min_age_days:    # 30
        return False
    if len(user_history) < cfg.frequency.new_user_min_photos:          # 10
        return False

    # 30 天内该簇 ≥ 5 个不同日子拍摄
    cluster_photo_ids = set(cluster.member_photo_ids)
    cutoff = datetime.now() - timedelta(days=cfg.frequency.lookback_days)   # 30
    recent_in_cluster = [
        p for p in user_history
        if p.photo_id in cluster_photo_ids and p.captured_at >= cutoff
    ]
    distinct_days = len({p.captured_at.date() for p in recent_in_cluster})
    return distinct_days >= cfg.frequency.min_distinct_days             # 5
```

**配置**:
```yaml
frequency:
  radius_m: 500
  lookback_days: 30
  min_distinct_days: 5
  new_user_min_age_days: 30
  new_user_min_photos: 10
```

任一不过 → `is_low_quality = False` (return)。

## 四、Plan A · L1 双 density (代码实现)

### 4.1 · 用户个人 baseline

```python
@dataclass
class UserDensityBaseline:
    meaning_threshold: float    # user 历史 meaning_density 的 25 分位
    aesthetic_threshold: float  # user 历史 aesthetic_density 的 25 分位
    last_computed_at: datetime


def compute_user_density_baseline(user_history, cfg) -> UserDensityBaseline | None:
    photos_with_l1 = [p for p in user_history if p.l1_output is not None]
    if len(photos_with_l1) < cfg.plan_a.min_samples_for_baseline:    # 25
        return None    # 数据不足, baseline 不可用 → 保守不判低质量
    meaning_values = [p.l1_output.meaning_density for p in photos_with_l1]
    aesthetic_values = [p.l1_output.aesthetic_density for p in photos_with_l1]
    return UserDensityBaseline(
        meaning_threshold=percentile(meaning_values, cfg.plan_a.baseline_percentile),     # 25
        aesthetic_threshold=percentile(aesthetic_values, cfg.plan_a.baseline_percentile),
        last_computed_at=datetime.now(),
    )
```

**关键设计**: 阈值用**用户自己的 25 分位数**, 防止"不会拍照的用户被全部误判为低质量"。

### 4.2 · 双低占比判定

```python
def signal_l1_density(cluster, l1_data, baseline) -> bool:
    if baseline is None:
        return False    # 保守
    member_l1 = [l1_data[pid] for pid in cluster.member_photo_ids]
    double_low_count = sum(
        1 for p in member_l1
        if p.meaning_density < baseline.meaning_threshold
        and p.aesthetic_density < baseline.aesthetic_threshold
    )
    return double_low_count / len(member_l1) >= 0.5    # ≥ 50% 双低 → 低质量
```

### 4.3 · Plan A 主入口

```python
def is_low_quality_plan_a(cluster, user, user_history, l1_data, baseline, cfg) -> bool:
    if not pass_frequency_check(cluster, user, user_history, cfg):
        return False
    return signal_l1_density(cluster, l1_data, baseline)
```

### 4.4 · 配置

```yaml
plan_a:
  enabled: true
  baseline_percentile: 25
  min_samples_for_baseline: 25
  baseline_refresh_days: 30
  double_low_ratio: 0.5
```

## 五、Plan B · POI + NIMA + 行为 (留 stub)

详见 `archive/specs/high_frequency_Place_Detection_Spec.md` §五。当前实现:

```python
def is_low_quality_plan_b(*args, **kwargs):
    raise NotImplementedError("Plan B 留 stub, 待 OQ-016 完成后实现")
```

Plan B 配置占位:
```yaml
plan_b:
  enabled: false    # Plan A 失败 (OQ-015) 后切 true
  poi: {...}
  nima: {...}
  behavior: {...}
```

## 六、主入口 (方案分发)

```python
def is_low_quality_place(cluster, user, user_history, photo_meta, l1_data, baseline, cfg) -> bool:
    if cfg.plan_a.enabled:
        return is_low_quality_plan_a(cluster, user, user_history, l1_data, baseline, cfg)
    elif cfg.plan_b.enabled:
        return is_low_quality_plan_b(cluster, user, user_history, photo_meta, l1_data, cfg)
    return False    # 都关 → 不判低质量
```

## 七、降级使用

`match_against_cluster` 命中后:

```python
band = distance_to_band(d_m, context)

# 实时低质量判定 (依赖 user_context, v0.1 None 时跳过)
if user_context is not None and is_low_quality_place(cluster, ..., user_context, cfg):
    band = downgrade_one_level(band)    # strong→medium / medium→weak / weak→none
```

**判定实时计算, 不持久化**, 支持滚动 30 天窗口自动遗忘(用户搬家后旧 cluster 自然失去频率)。

## 八、Case 验证 (Plan A · 来自 spec §七)

| Case | 描述 | 频率门槛 | 双 density 双低占比 | 判定 |
|---|---|---|---|---|
| 1 | 杭州家 | ✅ ≥ 5 天 | 75% (流水账多) | **低质量** ✅ 降档 |
| 2 | 常去公园 | ✅ | 20% (照片有调性) | **非低质量** ✅ 不降档 |
| 3 | 公司工位 | ✅ | 80% | **低质量** ✅ 降档 |
| 4 | 度假酒店 5 天 | ❌ 只 5 天可能不达 | — | **非低质量** ✅ |
| 5 | 搬家后老家 | ❌ 30 天 0 次 | — | **非低质量** ✅ 自动遗忘 |
| 6 | 新用户家 | ❌ 注册 < 30 天 | — | **非低质量** ✅ 保护期 |
| 7 | 不会拍照用户的家 | ✅ | 取决于个人 baseline | 个人 baseline 校准后正确判 |

## 九、核心不变性

1. **频率门槛是硬约束**, 不满足直接 return False
2. **Plan A / Plan B 替代关系**, 不同时运行
3. **判定实时计算, 不持久化**, 自动遗忘
4. **个人 baseline / NIMA baseline 防污染** — 用户的"低质量"是相对自己的
5. **降级只影响 location 维度**, event/theme 等独立工作

## 十、关联

- ADR: [ADR-0006](../decisions/0006-high-freq-low-quality-place.md)
- 上游使用方: `src/mini_album/place_anchor.py::match_against_cluster` (实时调用)
- 字段语义变更: [docs/02 §Cluster](./02_data_contracts.md) `Cluster.is_high_freq` → `is_low_quality`
- 硬规则: [docs/06 §HR-BANDS-01](./06_hard_rules.md) (HR-BANDS-01 现引 ADR-0006)
- 待补 OQ:
  - [OQ-013](./12_open_questions.md) — L1 双 density 验证标准
  - [OQ-014](./12_open_questions.md) — baseline 25 分位是否合理
  - [OQ-015](./12_open_questions.md) — Plan A 失败的判定标准
  - [OQ-016](./12_open_questions.md) — Plan B 启用工程改造
