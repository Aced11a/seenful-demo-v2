# 17 · 路径 B Time 维度: 自然日归属 + 时间链式切分 + 三路 grid

> 路径 B (L2 主路径, **多张照片自身判定**) time 维度的算法规范.
> 算法依据: [ADR-0011](../decisions/0011-time-natural-day-event-clustering.md).
> 仅覆盖路径 B. 路径 A (动态生长) time 维度不做独立判定 (时间仅作为指纹元数据存档).
>
> ⚠ **算法范式对齐 ADR-0010, 但底层算法不同源**:
> - ADR-0010 location: 真 DBSCAN (`min_samples=2` + density-reachable) + PCA OBB + 形状校正
> - ADR-0011 time: **时间链式切分** (`min_samples=1`, 退化为 gap > eps 切分) + 自然日归属 + 三路 grid
> - 两者共享"直出 4 档 band + rule_fired 落痕"范式 + 真值表 28 条结构不动, 但不是同算法.

---

## 一、变量定义

| 变量 | 定义 | 计算时机 |
|---|---|---|
| **K_days** = unique_days_count | 应用自然日归属 (§二.2) 后, 有照片的自然日数 | 任何时候 |
| **span_days** | 最早 ~ 最晚跨的自然日数 (含空日) | K_days ≥ 1 |
| **has_empty_days** | span_days > K_days | K_days ≥ 1 |
| **events_per_day** | dict[date_str, int], 每自然日的 cluster 数 | K_days ≥ 1 |
| **max_events_in_any_day** | 单日最多事件数 | K_days ≥ 1 |
| **max_inter_cluster_gap_h** | 同日内最大 cluster 间 gap (h, 跨日 None) | K_days = 1 |
| **max_intra_cluster_span_h** | 单 cluster 内最大 span (永远 ≤ eps/60) | K_days = 1 |
| **day_span_h** | 当日最早最晚跨度 (单日 grid 用) | K_days = 1 |
| **has_overnight_chain** | day1 末事件 → day2 首事件 gap < `overnight.max_gap_hours` (默认 12h) | K_days = 2 |
| **has_dawn_photos** | 是否有 0-6 点照片 (自然日归属相关) | 任何时候 |
| **total_span_hours** | max - min 跨度 (落痕展示, 永远计算) | 任何时候 |
| **fallback_count / fallback_ratio** | upload_time_fallback 计数 / 占比 | 任何时候 |
| **near_eps_boundary_count** | 切分时 gap 落 `[eps - δ, eps + δ]` 的次数 | K_days = 1 |

⚠ **K_days vs span_days**: K_days 只计有照片的日, span_days 含空日. has_empty_days = span_days > K_days 用来分流 T3.1 vs T3.2.

⚠ **max_inter_cluster_gap_h vs max_intra_cluster_span_h** (v0.2 字段拆分): 前者是 cluster 与 cluster 之间的 gap (T1.5/T1.7 判定用); 后者是单 cluster 内最大 span (永远 ≤ eps_minutes/60, 落痕诊断用). 拆字段是 [Time_Aggregation_Spec.md v0.2](../Time_Aggregation_Spec.md) 修问题⑦.

---

## 二、算法步骤

### 2.1 · 整体流水线

```text
照片列表 (含 captured_at + captured_at_source)
       │
       ▼
┌──────────────────────────────────────────────┐
│ Phase 1 · 自然日归属                          │
│  · 0-6 点 → 归"前一日 night"                 │
│  · 其他 → 本日                                │
└──────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│ Phase 2 · K_days 分流                         │
└──────────────────────────────────────────────┘
       │
   ┌───┼────┬─────────┬──────────────┐
   ▼   ▼    ▼         ▼              ▼
K_days  =0  =1        =2             ≥3
  │     │   │         │              │
  none  │   T1 grid   T2 grid        T3 grid
        │   (8 行)    (4 行)         (4 行, cap medium)
        │   │         │              │
        │   ▼         ▼              ▼
        └─→ Phase 3 · 边界保护带计数 (gap ∈ [100, 140]) → +near_eps_boundary 落痕
                │
                ▼
        ┌──────────────────────────────────────┐
        │ Phase 4 · Fallback 处理               │
        │  · ratio = 1.0 → confidence=0.5,     │
        │     rule_fired += "+k_days_uncertain"│
        │  · 0 < ratio < 1 → confidence = 1 -  │
        │     ratio * 0.3                       │
        └──────────────────────────────────────┘
                │
                ▼
            TimeFeature.band (4 档终值)
            + rule_fired + shape + 完整落痕
```

### 2.2 · 自然日归属 (`natural_day.dawn_cutoff_hour`)

```python
def get_natural_date(ts: datetime, dawn_cutoff_hour: int = 6) -> date:
    """0-6 点归'前一日 night', 其他归本日."""
    if 0 <= ts.hour < dawn_cutoff_hour:
        return (ts - timedelta(days=1)).date()
    return ts.date()
```

**理由 (ADR-0011 §2.3)**: 凌晨 2 点的活动是"昨晚的延续". 跟自然作息对齐.

**边界**: 夜班 / 凌晨工作者 < 5% 用户, v0.2 真实数据观察 ([OQ-022e](./12_open_questions.md)).

### 2.3 · 时间链式切分 (`chain_segmentation.eps_minutes`)

```python
def chain_split(
    timestamps_sorted: list[datetime],
    eps_minutes: int = 120,
    delta_minutes: int = 20,
) -> tuple[list[list[datetime]], int]:
    """gap > eps → 切; gap ≤ eps → 连. 同时计 near_eps_boundary 次数."""
    if not timestamps_sorted:
        return [], 0
    clusters: list[list[datetime]] = [[timestamps_sorted[0]]]
    near_count = 0
    for prev, curr in zip(timestamps_sorted, timestamps_sorted[1:]):
        gap_min = (curr - prev).total_seconds() / 60.0
        if abs(gap_min - eps_minutes) <= delta_minutes:
            near_count += 1
        if gap_min > eps_minutes:
            clusters.append([curr])        # 切新 cluster
        else:
            clusters[-1].append(curr)      # 加入当前 cluster
    return clusters, near_count
```

⚠ **不是 DBSCAN** (ADR-0011 §2.4): `min_samples = 1` 退化为单链 gap 切分, 跟 DBSCAN 核心点 + density-reachable 机制脱钩. 见 Time_Aggregation_Spec.md v0.2 §2.2 命名澄清.

### 2.4 · T1 网格 · 单日 (K_days = 1) — 8 行

按行顺序匹配, 命中第一条即为基础值:

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

**T1.5 设计意图 (修 v0.1 spec 的 T1.3/T1.5 strong 断层)**:
- T1.3 (2 紧邻 events) = strong, T1.5 (3-5 紧邻 events) 跟着 strong 平齐, 不再降档
- "events 越多信号越足"直觉成立
- 西湖一日游 (events=3, gaps 都 < 4h, span=8.5h) → T1.5 strong ✓
- 真"过密单日活动" (≥ 6 events) 走 T1.6 medium, 避免污染 strong 语义

### 2.5 · T2 网格 · 跨双日 (K_days = 2) — 4 行

| # | has_overnight_chain | 各日 events | total_span_h | band | shape |
|---|---|---|---|---|---|
| T2.1 | 是 | 各日 ≤ 2 | — | **strong** | overnight |
| T2.2 | 否 | 各日 ≤ 2 | < 30 | **medium** | weekend_trip |
| T2.3 | — | 至少一日 ≥ 3 | — | **weak** | sparse_two_days |
| T2.4 | 否 | — | ≥ 30 | **weak** | sparse_two_days |

**跨夜判定 (`overnight.max_gap_hours = 12`)**:

```python
def has_overnight_chain(day1_last: datetime, day2_first: datetime, max_h: int = 12) -> bool:
    gap_h = (day2_first - day1_last).total_seconds() / 3600.0
    return gap_h < max_h
```

直觉: 用户合理睡眠 + 早起 ≈ 8-10h, 12h 已宽容 "晚 21 点结束 + 早 9 点拍摄"; > 12h 是真断裂.

### 2.6 · T3 网格 · 长跨 (K_days ≥ 3) — 4 行, cap medium

| # | K_days | has_empty_days | band | shape |
|---|---|---|---|---|
| T3.1 | 3-7 | 否 | **medium** | short_trip |
| T3.2 | 3-7 | 是 | **weak** | sparse_short_trip |
| T3.3 | 8-14 | — | **weak** | long_trip |
| T3.4 | > 14 | — | **none** | scattered_long |

⚠ **T3 cap medium 是有意收紧** (Ace 2026-05-15 明示): 跨日 ≥ 3 天即使每日有照片也不进 strong 档. time 是 amplifier, 跨长日的 strong 信号由 T2.1 overnight chain 承担, ≥ 3 日交主载体 (theme/event/location) 接手.

### 2.7 · 边界保护带 (`near_eps_band.delta_minutes`)

```python
δ = 20  # minutes
for prev, curr in zip(timestamps_sorted, timestamps_sorted[1:]):
    gap_min = (curr - prev).total_seconds() / 60.0
    if abs(gap_min - eps_minutes) <= δ:
        near_eps_boundary_count += 1
if near_eps_boundary_count > 0:
    rule_fired += "+near_eps_boundary"
```

**关键性质 (ADR-0011 §2.8)**:
1. band 是确定的 (按 eps=120 硬切, 不引入随机性)
2. 临界 case 留痕, LLM 看到 `+near_eps_boundary` 可决定"时间信号不充分, 多依赖主载体"
3. 跟 ADR-0010 transit / shape 临界落痕范式一致

### 2.8 · Fallback 处理

```python
fallback_count = sum(1 for p in photos if p.captured_at_source == "upload_time_fallback")
fallback_ratio = fallback_count / len(photos)

if fallback_ratio == 1.0:
    confidence = 0.5
    rule_fired += "+k_days_uncertain"
elif fallback_ratio > 0:
    confidence = 1.0 - fallback_ratio * 0.3
else:
    confidence = 1.0
# band 不动
```

**与旧 OQ-003 (× 0.5 全局降权) 差异**: 旧把 score 一刀切减半, 新 band 不动, confidence 落痕给 LLM. 跟 ADR-0010 落痕范式同构. **OQ-003 被本 ADR supersede**.

---

## 三、TimeShape 枚举 (14 + 1 边界)

| 值 | rule_fired | 语义 |
|---|---|---|
| `single_event_dense` | T1.1 | 单日单事件密集 |
| `single_event_extended` | T1.2 | 单日单事件延展 |
| `adjacent_events` | T1.3 | 单日 2 紧邻事件 |
| `distant_events` | T1.4 | 单日 2 远距事件 (跨午餐间隔) |
| `extended_chain` | T1.5 | 单日 3-5 连续事件 (v0.2 升 strong) |
| `dense_chain` | T1.6 | 单日 ≥ 6 紧邻事件 (过密) |
| `multi_events_break` | T1.7 | 单日 ≥ 3 事件 + ≥ 4h 断裂 |
| `overstretched_chain` | T1.8 | 单日 ≥ 3 事件 + span > 12h |
| `overnight` | T2.1 | 跨夜双日 (12h 内续上) |
| `weekend_trip` | T2.2 | 周末双日游 (无跨夜续上, span < 30h) |
| `sparse_two_days` | T2.3 / T2.4 | 跨双日但稀疏 |
| `short_trip` | T3.1 | 3-7 天连续 (medium cap) |
| `sparse_short_trip` | T3.2 | 3-7 天中间断裂 |
| `long_trip` | T3.3 | 8-14 天 |
| `scattered_long` | T3.4 | > 14 天 (none) |
| `no_timestamp` | T0 | K_days = 0 (全无效) |

---

## 四、场景验证 (12 个 Case)

详见 [Time_Aggregation_Spec.md v0.2 §七](../Time_Aggregation_Spec.md). 关键 case 摘要:

| Case | timestamps | K_days | events | rule_fired | band |
|---|---|---|---|---|---|
| 午餐 4 张连拍 | [12:00, 12:05, 12:10, 12:30] | 1 | 1 | T1.1 | strong |
| 西湖一日游 5 张 | [9:00, 11:30, 13:00, 15:00, 17:30] | 1 | 3 | T1.5 | **strong** (v0.2 升) |
| 早午晚 3 事件 | [9:00, 13:00, 19:00] | 1 | 3 | T1.7 | weak |
| 过夜活动 | [day1 19:00, day1 21:00, day2 08:00] | 2 | day1:1, day2:1 | T2.1 | strong |
| 周末双日游 | [day1 10:00, day2 15:00] | 2 | day1:1, day2:1 | T2.2 | medium |
| 春节回家 5 天 | (5 days each ≥ 1 event) | 5 | — | T3.1 | medium |
| 国庆 4 天 1 天空 | (K_days=3, span_days=4) | 3 | — | T3.2 | weak |
| 凌晨 + 上午 (自然日归属) | [03:00, 09:00] | 2 (归属后) | day1:1, day2:1 | T2.1 | strong |
| 2 周以上 | (K_days=18) | 18 | — | T3.4 | none |
| 全 fallback | (任意, captured_at_source=upload_time_fallback) | — | — | T*+k_days_uncertain | (band 不动) |
| 早 + 下午 2 事件 | [9:00, 15:00] | 1 | 2 | T1.4 | medium |
| 午餐 + 下午紧接 | [12:30, 14:30] | 1 | 2 (gap=120 临界) | T1.3+near_eps_boundary | strong |

---

## 五、不变性

1. **band 4 档终值**, 真值表 28 条直读, 不再 score → 阈值
2. **K_days 是路径分流主键**: 0/1/2/≥3
3. **0-6 点归"前一日 night"**, 决定 K_days 计数
4. **时间链式切分 eps=120min** (非 DBSCAN, v0.2 命名澄清)
5. **K_days ≥ 3 默认不进 strong 档** (T3 cap medium, Ace 明示)
6. **跨夜连续判定 (T2.1) 用 12h 阈值**
7. **旅游档独立于 location.context** (ADR-0010 已删 context 字段, 不依赖)
8. **fallback 不动 band, 落痕 confidence** — 与 ADR-0010 落痕同构
9. **time 维度独立于 location 维度** — 断 ADR-0007 单向依赖链
10. **rule_fired 必填** — 落痕命中规则 + 修饰 (例: "T3.1+k_days_uncertain", "T1.5+near_eps_boundary")
11. **T1 grid 无降档断层**: events 增多不导致 strong→medium 倒挂 (v0.2 修问题④)
12. **gap 临界 case 强制硬切, 落痕 `+near_eps_boundary`** — band 由算法直出, 不稳定性走 rule_fired

---

## 六、配置

完整配置见 `config/path_b_time.yaml` (ADR-0011 §2.9). 关键字段:

| 字段 | 默认 | 说明 |
|---|---|---|
| `chain_segmentation.eps_minutes` | 120 | 同事件最大 gap (经验初值, [OQ-022a](./12_open_questions.md) 调优) |
| `near_eps_band.delta_minutes` | 20 | 边界保护带宽 (eps ± δ) |
| `natural_day.dawn_cutoff_hour` | 6 | 0-6 点归前日 |
| `overnight.max_gap_hours` | 12 | 跨夜 chain 阈值 |
| `t1_grid.adjacent_gap_max_h` | 4 | T1.3 / T1.5 内部 gap 上限 |
| `t1_grid.extended_chain_max_span_h` | 12 | T1.5 / T1.6 day_span 上限 |
| `t1_grid.extended_chain_events_max` | 5 | T1.5 events 上限 |
| `t1_grid.dense_chain_events_min` | 6 | T1.6 events 下限 |
| `t2_grid.each_day_events_max` | 2 | T2.1 / T2.2 各日 events 上限 |
| `t2_grid.total_span_max_h` | 30 | T2.2 总跨度上限 |
| `t3_grid.short_trip_max_days` | 7 | T3.1 / T3.2 K_days 上限 |
| `t3_grid.long_trip_max_days` | 14 | T3.3 K_days 上限 |
| `fallback.full_fallback_confidence` | 0.5 | ratio=1.0 时 confidence |
| `fallback.partial_confidence_penalty` | 0.3 | confidence = 1 - ratio × 0.3 |

⚠ **代码禁止硬编码任何上述数值** (CLAUDE.md §3 配置与代码分离).

---

## 七、与 ADR-0010 的关系

| 字段 | ADR-0010 location | ADR-0011 time | 同构? |
|---|---|---|---|
| 算法本质 | DBSCAN (密度核心点 + 扩展) | gap 链式切分 (single linkage) | **不同源** |
| 抗噪 | 是 (离群点不入 cluster) | 否 (单点也成 cluster) | 不同 |
| 输入维度 | 2D GPS | 1D timestamp | N/A |
| 路径分流主键 | K_outer (0/1/2/≥3) | K_days (0/1/2/≥3) | ✓ 同构 |
| 输出范式 | band + shape + rule_fired | band + shape + rule_fired | ✓ 同构 |
| 落痕机制 | transit / shape 临界落痕 | `+near_eps_boundary` / `+k_days_uncertain` | ✓ 同构 |
| 跟另一维度关系 | 独立于 time | 独立于 location (本 ADR 断单向依赖) | ✓ 同构 |

**写代码时勿混淆**: 路径 B time 不能复用 ADR-0010 的 DBSCAN 工具函数 (不同算法), 但**可复用** rule_fired 后缀 / shape 枚举的"诊断落痕"思路.
