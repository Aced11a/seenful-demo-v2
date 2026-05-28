# ADR-0011 · 路径 B time 维度: 自然日归属 + 时间链式切分 + 三路 grid

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-18 |
| 决策 | 与 Claude Code 联合设计, 经 5 轮迭代 (period 硬切否决 → 1D 切分引入 → 三路 grid 设计 → T1.3/T1.5 断层修复) |
| 影响范围 | 重写 `src/features/time.py` + 升级 `src/contracts/features.py::TimeFeature` + 新增 `config/path_b_time.yaml` + 新增 `docs/17_path_b_time.md`; 改 `docs/{00,01,02,07,11,12}`; 新增 fixtures + 单测 + 重生 golden |
| 相关文档 | `docs/17_path_b_time.md` (本算法主规范), `Time_Aggregation_Spec.md` v0.2 (设计来源, 实施完后归档 `archive/specs/`) |
| 关联 OQ | **新增** [OQ-022](../docs/12_open_questions.md#oq-022-adr-0011-接受边界的真实数据验证) 跟踪本 ADR 接受边界的 v0.2 真实数据验证 (10 个子问题 22a~j: eps 调优 / extended_chain 边界 / T3 收紧 / 跨夜 12h / 凌晨归属 / D 系列阈值 / 凌晨与 overnight 冗余 / 时区 / 字段拆分 / T2.3 误伤) |
| 关联 ADR | supersede [ADR-0004](./0004-feature-assembler-revision.md) §3.2.2 time_score 段 (滚动小时窗 + 双峰 + 旅游放宽); 与 [ADR-0010](./0010-path-b-location-dbch-pca-shape.md) 路径 B location **输出范式同构** (band 直出 + rule_fired 落痕), 但**底层算法不同源** (location 是 DBSCAN; time 是 gap 链式切分, 非 DBSCAN) |

---

## 1 · 背景

### 1.1 · 路径 B time 现状

`src/features/time.py::compute_time_score` 算法:
- max - min 取总跨度 (span_hours)
- 查 `config/dimension_thresholds.yaml::time_span_bands` 单一档位表 → score
- 全 fallback 时 × 0.5 (来自 OQ-003)

`docs/07_dimension_thresholds.md` §3.2.2 描述的设计 (双峰检测 + 旅游放宽 + 三档表) **未实现**, 代码层与 docs 长期漂移. ADR-0010 落地后, `LocationContext` 字段被删, 旅游档信号源消失, time 维度成为最大算法漂移点.

### 1.2 · 失败模式 (Ace 2026-05-15 提出)

span 单跨度判定 + docs 漂移设计共有 21 个缺陷, 其中影响最严重的 7 类:

| # | 场景 | 现 score | 应该 | 失败根因 |
|---|---|---|---|---|
| 1 | 早午晚 3 事件 (9/13/19, span=10h) | 0.70 medium | weak | span 看不出"多事件断裂" |
| 2 | 西湖一日游 5 张 (9-17:30, span=8.5h) | 0.70 medium | strong (本 ADR) | 多事件但连续, 应升 strong (修问题④ 断层) |
| 3 | 凌晨 3 点 + 上午 9 点 | 0.70 medium | strong (overnight) | span=6h 看不出"跨睡眠" |
| 4 | 过夜活动 (晚 19 + 次日早 8, span=13h) | 0.50 weak | strong (overnight chain) | 跨 12h 阈值, 旧 score 错配 |
| 5 | 周末双日游 (周六 10 + 周日 15, span=29h) | 0.50 weak | medium | 双日游应 medium 而非 weak |
| 6 | 春节 5 天 (each day photos) | 0.20 none | medium (T3.1) | 旅游档未实现, 落空 |
| 7 | 双峰检测漂移设计 + 旅游档依赖 LocationContext | docs 描述 ≠ 代码 | 重新设计 | ADR-0010 删 context 后死锁 |

### 1.3 · 引发本 ADR 的具体问题

ADR-0010 落地把 location 输出范式改为"直出 band + rule_fired 落痕", time 维度不跟随升级会:
- docs/07 §3.2.2 描述的 `is_travel_relaxed` 死字段
- 真值表 28 条中 D 系列 (time 放大器) 在 score=0.20 全 fallback 时无法触发
- 跟 ADR-0009 event / ADR-0010 location 直出 band 不一致, 真值表消费层语义割裂

必须改算法范式: **不再算 score, 直出 band + 完整落痕, 与 ADR-0010 路径 B location 输出范式对齐**.

---

## 2 · 决策

### 2.1 · 算法范式

**路径 B time 不再算 score, 直出 4 档 band (strong/medium/weak/none) 为终值**, 真值表 28 条结构不变, 只读 `TimeFeature.band`.

跨自然日多事件 / 凌晨 / 过夜的歧义通过 **time 维度内部** 消化 (自然日归属 + 跨夜判定 + T1/T2/T3 grid 分流), 不依赖 location.context / location.shape 等外部信号. **断 ADR-0004 / ADR-0007 location → time 单向依赖链**.

### 2.2 · 三路判定流水线

```
照片 captured_at + captured_at_source
    │
    ▼
应用自然日归属规则 (§2.3, 0-6 归前日)
    │
    ▼
计算 K_days
    │
    ├─ K_days = 0       → none (T0)
    ├─ K_days = 1       → 路径 T1 (单日, 8 行 grid)
    ├─ K_days = 2       → 路径 T2 (跨双日, 4 行 grid + overnight chain)
    └─ K_days ≥ 3       → 路径 T3 (长跨, 4 行 grid, cap medium)
    │
    ▼
fallback 处理 (§2.7): 不动 band, 只落痕 confidence
    │
    ▼
TimeFeature.band (4 档终值) + rule_fired + shape + 完整落痕
```

### 2.3 · 自然日归属规则

```python
def get_natural_date(ts: datetime) -> date:
    if 0 <= ts.hour < 6:
        return (ts - timedelta(days=1)).date()
    return ts.date()
```

**理由**: 凌晨 2 点的活动是"昨晚的延续", 不是"今天的开始". 0-6 切点对齐自然作息.

**边界 (已知接受)**: 夜班 / 凌晨工作者 < 5% 用户, v0.2 真实数据观察 (OQ-022e).

### 2.4 · 时间链式切分 (gap-based segmentation)

```
输入: 该自然日内全部 timestamp (排序后)
算法: gap > eps_minutes → 切; gap ≤ eps_minutes → 连 (single-linkage 链式连通)
参数: eps_minutes = 120 (2h)
输出: events_today (该日 cluster 数) + per-cluster span / 簇间 gap
```

⚠ **不是 DBSCAN** (Time_Aggregation_Spec.md v0.2 修问题①): `min_samples = 1` 退化为按 gap 切分, 与 DBSCAN 核心点 + density-reachable 机制脱钩. 跟 ADR-0010 location 真 DBSCAN 仅在"按阈值连通" 表面相似, 在密度 / 抗噪 / 形状识别上**不同源**.

### 2.5 · 核心变量定义

| 变量 | 定义 | 计算时机 |
|---|---|---|
| **K_days** | 应用自然日归属后, 有照片的自然日数 | 任何时候 |
| **span_days** | 最早 ~ 最晚跨的自然日数 (含空日) | K_days ≥ 1 |
| **has_empty_days** | span_days > K_days | K_days ≥ 1 |
| **events_per_day** | dict[date, int], 每自然日的 cluster 数 | K_days ≥ 1 |
| **max_events_in_any_day** | 单日最多事件数 | K_days ≥ 1 |
| **max_inter_cluster_gap_h** | 同日内最大 cluster 间 gap (h), 跨日 None | K_days = 1 |
| **max_intra_cluster_span_h** | 同日内单 cluster 内部最大 span (≤ eps/60) | K_days = 1 |
| **day_span_h** | 当日最早最晚跨度 (K_days=1) | K_days = 1 |
| **has_overnight_chain** | day1 末事件 → day2 首事件 gap < 12h | K_days = 2 |
| **has_dawn_photos** | 是否有 0-6 点照片 | 任何时候 |
| **total_span_hours** | max - min 跨度 (落痕展示) | 任何时候 |
| **fallback_count / fallback_ratio** | upload_time_fallback 计数 / 占比 | 任何时候 |
| **near_eps_boundary_count** | 切分时 gap ∈ [eps - δ, eps + δ] 的次数 (§2.8) | K_days = 1 |

### 2.6 · 三路 grid

#### Step T1 · 单日 (K_days = 1) — 8 行网格, 按行顺序匹配

| # | events_today | max_inter_cluster_gap_h | day_span_h | band | shape |
|---|---|---|---|---|---|
| T1.1 | 1 | — | ≤ 2 | **strong** | single_event_dense |
| T1.2 | 1 | — | > 2 | **strong** | single_event_extended |
| T1.3 | 2 | < 4 | — | **strong** | adjacent_events |
| T1.4 | 2 | ≥ 4 | — | **medium** | distant_events |
| T1.5 | 3-5 | 全部 < 4 | ≤ 12 | **strong** | extended_chain (v0.2 升 strong 修问题④) |
| T1.6 | ≥ 6 | 全部 < 4 | ≤ 12 | **medium** | dense_chain |
| T1.7 | ≥ 3 | ≥ 4 (任一) | — | **weak** | multi_events_break |
| T1.8 | ≥ 3 | 全部 < 4 | > 12 | **weak** | overstretched_chain |

#### Step T2 · 跨双日 (K_days = 2) — 4 行网格

| # | has_overnight_chain | 各日 events | total_span_h | band | shape |
|---|---|---|---|---|---|
| T2.1 | 是 | 各日 ≤ 2 | — | **strong** | overnight |
| T2.2 | 否 | 各日 ≤ 2 | < 30 | **medium** | weekend_trip |
| T2.3 | — | 至少一日 ≥ 3 | — | **weak** | sparse_two_days |
| T2.4 | 否 | — | ≥ 30 | **weak** | sparse_two_days |

#### Step T3 · 长跨 (K_days ≥ 3) — 4 行网格, cap medium

| # | K_days | has_empty_days | band | shape |
|---|---|---|---|---|
| T3.1 | 3-7 | 否 | **medium** | short_trip |
| T3.2 | 3-7 | 是 | **weak** | sparse_short_trip |
| T3.3 | 8-14 | — | **weak** | long_trip |
| T3.4 | > 14 | — | **none** | scattered_long |

⚠ **T3 cap medium** (Ace 2026-05-15 明示): K_days ≥ 3 即使每日有照片也不进 strong 档, 跨长日由主载体接手. T3 收紧是有意的算法收紧.

### 2.7 · Fallback 处理

```python
fallback_count = sum(1 for p in photos if p.captured_at_source == "upload_time_fallback")
fallback_ratio = fallback_count / len(photos)

if fallback_ratio == 1.0:
    confidence = 0.5
    rule_fired += "+k_days_uncertain"
    # band 不动
elif fallback_ratio > 0:
    confidence = 1.0 - fallback_ratio * 0.3
else:
    confidence = 1.0
```

**与旧 × 0.5 全局降权差异**: 旧把 score 一刀切减半, 新 band 不动, confidence 落痕给 LLM, 跟 ADR-0010 transit 临界 / shape 临界 落痕范式同构.

### 2.8 · 边界保护带 (gap 阈值脆性缓解)

```python
δ = 20  # 分钟, 配 near_eps_band.delta_minutes
for gap in adjacent_gaps:
    if abs(gap_minutes - eps_minutes) <= δ:
        near_eps_boundary_count += 1
        # 切分仍按 gap ≤ eps 连 / > eps 切, 不动 band
if near_eps_boundary_count > 0:
    rule_fired += "+near_eps_boundary"
```

**关键性质**:
1. **band 是确定的** (按 eps=120 硬切, 不引入随机性 / 重叠区)
2. **临界 case 留痕**, LLM 看到 `+near_eps_boundary` 可决定"时间信号不充分, 多依赖主载体"
3. 跟 ADR-0010 transit / shape 临界落痕范式一致

### 2.9 · 配置

```yaml
# config/path_b_time.yaml
path_b_time:
  chain_segmentation:
    eps_minutes: 120

  near_eps_band:
    delta_minutes: 20

  natural_day:
    dawn_cutoff_hour: 6

  overnight:
    max_gap_hours: 12

  t1_grid:
    single_event_dense_max_h: 2
    adjacent_gap_max_h: 4
    extended_chain_max_span_h: 12
    extended_chain_events_max: 5
    dense_chain_events_min: 6

  t2_grid:
    each_day_events_max: 2
    total_span_max_h: 30

  t3_grid:
    short_trip_max_days: 7
    long_trip_max_days: 14

  fallback:
    full_fallback_confidence: 0.5
    partial_confidence_penalty: 0.3
```

---

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| **A. 仅 span 单跨度 + 单一档位表 (v0.1 现状)** | 失败模式见 §1.2 共 7 类场景判错 |
| **B. 滚动小时窗 + 双峰检测 + 旅游放宽 (docs/07 §3.2.2 设计)** | 双峰与旅游档死锁 (跨日游天然多峰, 旅游档 strong 双峰 weak 冲突); 旅游档依赖 ADR-0010 已删的 LocationContext; 21 个设计缺陷 (见 spec §一) |
| **C. 等距时段硬切 (morning/midday/...)** | 边界附近 (10:59 vs 11:01) 把同事件切两段 (Ace 2026-05-15 明示否决) |
| **D. 1D DBSCAN (min_samples=2)** | min_samples=2 时合理但路径 B 输入 3-10 张, 大量场景单点 cluster 被判 outlier 不合理 |
| **E. 1D DBSCAN (min_samples=1) + 真值表 28 条全改 score 驱动** | 真值表不动是 Ace 明确约束, 改 28 条规则结构涉及面太广; 且 min_samples=1 时本质就是 gap 链式切分, 不必伪装 DBSCAN |
| **F. 本 ADR — 自然日归属 + 时间链式切分 + 三路 grid (T1/T2/T3) + 边界保护带** | 修了 §1.2 的 7 类失败 + 修 T1.3/T1.5 strong 断层 (问题④) + 跟 ADR-0010 输出范式对齐 + 真值表 28 条结构不动 + 算法命名诚实 (不假装 DBSCAN) |

---

## 4 · 影响范围

### 4.1 · 契约变更

**修改** `src/contracts/features.py::TimeFeature`:

```python
# 旧 (v1.3.2 ADR-0004 引入, 现 supersede):
class TimeFeature(BaseModel):
    score: float
    confidence: float
    time_span_hours: float
    median_gap_hours: float = 0.0
    is_bimodal: bool = False                # ← 删
    is_travel_relaxed: bool = False         # ← 删 (ADR-0010 删 LocationContext 后已死)
    all_fallback: bool = False              # ← 删 (用 fallback_ratio 表达更细)
    primary_signal: str = "captured_at"

# 新 (本 ADR):
class TimeFeature(BaseModel):
    # ★ 真值表直消费
    band: BandLevel                                       # ← 新, 终值 (4 档)
    rule_fired: str = Field(min_length=1)                 # ← 新 ("T1.5" / "T2.1+k_days_uncertain" 等)

    # 派生展示 (老 score 保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── 自然日 + 事件诊断 ──────────────────────────────────
    unique_days_count: int                                # K_days
    span_days: int
    has_empty_days: bool
    events_per_day: dict[str, int]                        # {"2026-05-15": 2}
    max_events_in_any_day: int

    # ─── 时间几何 (v0.2 拆字段) ──────────────────────────
    total_span_hours: float
    max_inter_cluster_gap_h: float | None
    max_intra_cluster_span_h: float | None
    has_overnight_chain: bool
    has_dawn_photos: bool
    near_eps_boundary_count: int

    # ─── fallback ────────────────────────────────────────────
    fallback_count: int
    fallback_ratio: float
    confidence: float

    # ─── 落痕 ────────────────────────────────────────────────
    shape: TimeShape                                       # ← 新枚举
    primary_signal: str = "captured_at"
```

⚠ **Ace 偏好: 老方案直接删, 不留 deprecated 兼容**. `is_bimodal` / `is_travel_relaxed` / `median_gap_hours` / `all_fallback` 直接删, `time_span_hours` 重命名为 `total_span_hours` (与 ADR-0010 命名风格对齐).

**新增** `TimeShape` 枚举 (14 值):
- T1: `SINGLE_EVENT_DENSE` / `SINGLE_EVENT_EXTENDED` / `ADJACENT_EVENTS` / `DISTANT_EVENTS` / `EXTENDED_CHAIN` / `DENSE_CHAIN` / `MULTI_EVENTS_BREAK` / `OVERSTRETCHED_CHAIN`
- T2: `OVERNIGHT` / `WEEKEND_TRIP` / `SPARSE_TWO_DAYS`
- T3: `SHORT_TRIP` / `SPARSE_SHORT_TRIP` / `LONG_TRIP` / `SCATTERED_LONG`
- 边界: `NO_TIMESTAMP`

**修改** `FeaturePackage.time` 字段: 由旧 TimeFeature 替换为新 TimeFeature (含 band 终值). 老 `time_score` 派生填充 (展示值, 非判定输入).

### 4.2 · 新增算法模块

**重写** `src/features/time.py`:
- `build_time_feature(photos, cfg) -> TimeFeature` 高层入口
- 内部子函数:
  - `_get_natural_date(ts, dawn_cutoff_hour)` 自然日归属
  - `_chain_split(timestamps, eps_minutes, delta_minutes)` 链式切分 + 边界保护带计数
  - `_compute_events_per_day(photos, dawn_cutoff_hour)` 每日 cluster 拆分
  - `_compute_overnight_chain(day1_photos, day2_photos, max_gap_h)` 跨夜判定
  - `_step_t1_grid(events_today, max_inter_gap_h, day_span_h, cfg)` 单日 8 行
  - `_step_t2_grid(events_per_day, has_overnight_chain, total_span_h, cfg)` 跨双日 4 行
  - `_step_t3_grid(K_days, has_empty_days, cfg)` 长跨 4 行
  - `_compute_fallback(photos, cfg)` confidence + rule 后缀

纯 Python, **零额外依赖** — 不调 numpy/sklearn (项目无此依赖).

### 4.3 · 配置

新增 `config/path_b_time.yaml` (见 §2.9).

`config/dimension_thresholds.yaml::time_span_bands` 段**保留**为派生 score 计算用 (TimeFeature.score 仍输出, 但不参与 band 判定 — band 来自 `path_b_time.yaml`).

`time_score` 段 (v1.3.2 设计的 bimodal_detection / home_city_brackets / travel_brackets) 设为**死段**, 不读. v0.2 决定是否删 (留 ADR-0011 实施后跟 ADR-0007 同批清理).

### 4.4 · 调用方

**修改** `src/features/assemble.py`:
- 调 `build_time_feature(photos, cfg)` 替代 `compute_time_score`
- `FeaturePackage.time` 填新 TimeFeature
- `FeaturePackage.time_score` 由 `feature.score` 派生
- `FeaturePackage.time_is_fallback` 由 `feature.fallback_ratio == 1.0` 派生

**修改** `src/policy/bands.py`:
- `Bands.time` 直接读 `TimeFeature.band`, 不再走 `score → 阈值查表`
- 兜底: `features.time is None` (历史路径) 回退老 `_classify(time_score, db["time"])`

### 4.5 · 测试

**新建** `tests/fixtures/photos/` time 相关:
- `time_t1_1_lunch_burst.json` (午餐 4 张, T1.1)
- `time_t1_5_westlake_walk.json` (西湖 5 张, T1.5 strong v0.2)
- `time_t1_7_three_meals.json` (早午晚 9/13/19, T1.7 weak)
- `time_t2_1_overnight.json` (跨夜 19 + 次日 8, T2.1 strong)
- `time_t2_2_weekend_trip.json` (周末双日, T2.2 medium)
- `time_t3_1_spring_festival.json` (春节 5 天, T3.1 medium)
- `time_t3_2_sparse_holiday.json` (国庆 4 天中 1 天空, T3.2 weak)
- `time_dawn_attribution.json` (凌晨 3 点 + 上午 9, T2.1 strong via 自然日归属)
- `time_t3_4_long_scattered.json` (2 周以上, T3.4 none)
- `time_full_fallback.json` (全 fallback, confidence=0.5 落痕)
- `time_near_eps_boundary.json` (gap=130min 临界, +near_eps_boundary 落痕)

**新建** `tests/unit/features/test_time.py`:
- T1.1~T1.8 每行 ≥ 1 正例 + 1 边界
- T2.1~T2.4 每行 ≥ 1 例
- T3.1~T3.4 每行 ≥ 1 例
- 自然日归属: 凌晨边界 (0:00/3:00/5:59/6:00 各 1 例)
- 跨夜判定: 11h/12h/13h gap 边界各 1 例
- 边界保护带: gap=100/110/120/130/140 各 1 例 (140 临界)
- Fallback: 0%/50%/100% 三档 confidence 验证
- 工具函数单测: `_chain_split` / `_get_natural_date` / `_compute_overnight_chain`

**重生** golden:
- `tests/scenarios/*` 涉及 time 的 golden 重跑 `scripts/generate_golden.py`
- 人工 diff 审 time 字段从 score-driven 到 band-driven 的变化
- 预期 ~ 8-10 个 golden 需重生

---

## 5 · 决策回滚条件

| 回滚条件 | 动作 |
|---|---|
| v0.2 真实数据上 T1.5 误判率 > 30% (人工 review "连续多事件" 实际不该 strong) | T1.5 回 medium, 拆 T1.5a (events=3) / T1.5b (events∈[4,5]) |
| dawn-cross case 占比 > 10% 且 K_days 字段被下游误用 | 删自然日归属, 只保留 overnight chain (OQ-022g 方案 a) |
| eps_minutes=120 真实数据 grid search 上准确率不如 90 / 180 | 调 eps, 写新 ADR 记录 |
| 跨时区旅行误判率高 | 引入 `captured_at_tz` 字段 + 时区规整, 写新 ADR (OQ-022h) |
| T2.3 误伤跨日游率 > 25% | 拆 T2.3: day1+day2 都 ≥ 3 才 weak, 否则 medium (OQ-022j 方案 b) |
| near_eps_boundary 触发率 > 15% | δ 调整或 eps 偏离真实数据峰值, 写新 ADR |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-003 (time_is_fallback 全局降权) | 已决策 (× 0.5) | **supersede** — 本 ADR 改为 confidence 落痕, 不动 band |
| OQ-009 §9b/§9c (event/people 严格度) | 待决 | **不变** — 本 ADR 不动 event/people |
| **OQ-022 (新增)** | — | ADR-0011 接受边界 v0.2 真实数据验证, 10 个子问题 22a~j (eps / extended_chain / T3 收紧 / 跨夜阈值 / 凌晨归属 / D 系列 / 凌晨 vs overnight 冗余 / 时区 / 字段拆分 / T2.3 误伤) |
| docs/07 §3.2.2 (双峰检测 + 旅游放宽) | 描述与代码漂移 | **关闭漂移** — 描述指向 docs/17, 旧设计完全 supersede |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完 (Step 1)
2. ⏳ `docs/17_path_b_time.md` 完整算法规范 (Step 2)
3. ⏳ `config/path_b_time.yaml` 新建 (Step 3)
4. ⏳ `src/contracts/features.py::TimeFeature` 升级 + `TimeShape` 枚举 + `__init__.py` 导出 (Step 4-5)
5. ⏳ `src/features/time.py` 重写 + `assemble.py` 适配 + `bands.py` 直读 (Step 6-8)
6. ⏳ `docs/{02,07,00,01,11,12}` 同步 (Step 9)
7. ⏳ Fixtures + 单测 + golden 重生 + grep 自检 (Step 10-11)
8. ⏳ Spec 归档 — `Time_Aggregation_Spec.md` v0.2 → `archive/specs/` + `archive/specs/README.md` 加索引 + `docs/00_index.md` 已归档段更新 (Step 12)
9. ⏳ v0.2: OQ-022 真实数据验证
