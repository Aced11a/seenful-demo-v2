# 18 · 路径 B Event 维度: event primary_share + activity 二次门槛

> 路径 B (L2 主路径) event 维度的算法规范.
> 算法依据: [ADR-0012](../decisions/0012-path-b-event-aggregation.md).
> 仅覆盖路径 B (N 张照片自身内聚度). 路径 A (1 张 vs 老相册 aggregation 匹配) 见 [ADR-0009](../decisions/0009-event-aggregation.md) + [docs/15](./15_event_aggregation.md).
>
> ⚠ **path A vs path B event 算法对比**:
> - path A: "1 张新 vs 老相册 EventAggregation" — **匹配**问题, 输出 EventMatchResult
> - path B: "N 张新照片自身" — **内聚度判定**问题, 输出 EventFeature.band
> 二者**共享** `aggregate_event(photos)` 函数 (ADR-0009 实现), 但 band 判定逻辑独立.
>
> ⚠ **A3 真值表约束**: event=强 → bounds=[medium, strong], type=event — event 单独 strong 直接触发 A3 成集, **不需要其他维度配合**. 因此本 spec 的 strong 门槛设计为**双重**: event=1.0 + activity ≥ 2/3.

---

## 一、变量定义

### 1.1 · event 主信号

| 变量 | 定义 |
|---|---|
| **N** | 总照片数 (len(photos)) |
| **N_valid** | event_hint != "unknown" 的数量 |
| **unknown_share** | (N - N_valid) / N |
| **agg** | ADR-0009 `aggregate_event(photos)` 输出 |
| **primary** = agg.primary | 占比 ≥ 0.6 of N_valid 的最高频 event_hint, 可能 None |
| **primary_count** | distribution[primary] |
| **event_primary_share** | primary_count / **N** (基于总数 N, 不是 N_valid) |
| **distinct_events** | len(distribution) |

### 1.2 · activity 二次信号

| 变量 | 定义 |
|---|---|
| **activity_counter** | Counter(activity for activity in photos if activity != "unknown") |
| **activity_primary** | activity_counter.most_common(1) (排除 unknown) |
| **activity_primary_count** | activity_counter[activity_primary] |
| **activity_primary_share** | activity_primary_count / **N** (跟 event 同分母) |

⚠ **event_primary_share / activity_primary_share 都基于 N (总数)** — unknown 是衰减因子.

---

## 二、算法步骤

### 2.1 · 整体流水线

```text
photos (含 event_hint + activity)
       │
       ▼
┌─────────────────────────────────────────────┐
│ Phase 1 · ADR-0009 aggregate_event(photos)  │
│  · 算 distribution / primary / secondary    │
│  · 返回 EventAggregation                    │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│ Phase 2 · 计算 event_primary_share          │
│   = primary_count / N                       │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│ Phase 3 · 计算 activity_primary_share       │
│   = activity_counter.most_common(1) / N     │
│   (排除 unknown)                            │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│ Phase 4 · 8 行 grid 判定 → band + shape    │
└─────────────────────────────────────────────┘
       │
       ▼
   EventFeature.band (4 档终值)
   + rule_fired + shape + 完整落痕
```

### 2.2 · 8 行 grid (E.1~E.8) — 按行顺序匹配

| # | event_primary_share | activity_primary_share | N_valid | band | shape |
|---|---|---|---|---|---|
| E.1 | **= 1.0** | **≥ 2/3** | — | **strong** | unanimous_event_activity |
| E.2 | = 1.0 | < 2/3 | — | **medium** | unanimous_event_mixed_activity |
| E.3 | 0.8 ≤ < 1.0 | — | — | **medium** | dominant_event |
| E.4 | 0.6 ≤ < 0.8 | — | — | **medium** | mixed_event |
| E.5 | 0.4 ≤ < 0.6 | — | — | **weak** | scattered_event |
| E.6 | < 0.4 | — | ≥ 2 | **weak** | fragmented_event |
| E.7 | — | ≥ 2/3 | ≤ 1 | **weak** | activity_fallback |
| E.8 | — | < 2/3 | ≤ 1 | **none** | no_event_signal |

### 2.3 · E.1 strong 通道 — 双重门槛

**唯一进 strong 的通道**: event=1.0 AND activity ≥ 2/3

```python
if event_primary_share == 1.0:
    if activity_primary_share >= 2 / 3:
        return "strong", "E.1", EventShape.UNANIMOUS_EVENT_ACTIVITY
    return "medium", "E.2", EventShape.UNANIMOUS_EVENT_MIXED_ACTIVITY
```

**典型 case**:
- [event=meal × 5] + [activity=meal × 5] → strong
- [event=outing × 5] + [activity=walk × 4, sightseeing × 1] (activity_share=0.8) → strong
- [event=sports × 5] + [activity=gathering × 5] → strong (篮球/足球 case, 接受边界)

**为什么 strong 严格**: A3 真值表让 event=强单独触发 type=event 小集, 不严会 1 张离群也成集.

### 2.4 · E.2~E.6 — event 自定档, 不看 activity

`event_primary_share < 1.0` 时, **不查 activity**, event 自定档:
- 0.8~1.0 → medium (E.3)
- 0.6~0.8 → medium (E.4)
- 0.4~0.6 → weak (E.5)
- < 0.4 + N_valid ≥ 2 → weak (E.6)

⚠ 即使 activity 100% 一致, event<1.0 时也不能升 strong. activity 仅作 strong 二次门槛, 不能反转 event 信号.

### 2.5 · E.7/E.8 — event 缺位时 activity 兜底

`N_valid ≤ 1` 时启用兜底:
- activity ≥ 2/3 → weak (E.7)
- activity < 2/3 → none (E.8)

**永不超 weak 上限**: activity 语义比 event 宽 (sightseeing 不一定是同次出游), 兜底就该谦虚.

---

## 三、EventShape 枚举 (8 + 1 边界)

| 值 | rule_fired | 语义 |
|---|---|---|
| `unanimous_event_activity` | E.1 | event 全员一致 + activity 多数派 (strong) |
| `unanimous_event_mixed_activity` | E.2 | event 全员一致 + activity 散 (medium) |
| `dominant_event` | E.3 | event 80%-100% 主导 (medium) |
| `mixed_event` | E.4 | event 60%-80% 主导 (medium) |
| `scattered_event` | E.5 | event 40%-60% 弱主导 (weak) |
| `fragmented_event` | E.6 | event 散乱 (weak) |
| `activity_fallback` | E.7 | N_valid ≤ 1 + activity 多数派 (weak) |
| `no_event_signal` | E.8 | N_valid ≤ 1 + activity 散 (none) |

---

## 四、场景验证 (14 个 Case)

详见 [Path_B_Event_Aggregation_Spec.md v0.2 §五](../Path_B_Event_Aggregation_Spec.md). 摘要:

| Case | event_hints | activities | band |
|---|---|---|---|
| 全部 meal + meal 一致 | [meal × 5] | [meal × 5] | E.1 strong |
| 4:1 主导 | [meal × 4, gathering × 1] | — | E.3 medium |
| 3:2 主导 | [meal × 3, gathering × 2] | — | E.4 medium |
| 2:1 + 2 unknown | [meal × 2, gathering × 1, unknown × 2] | — | E.5 weak |
| 各半二选一 | [meal × 2, gathering × 2] | — | E.6 weak |
| 三向散乱 | [meal, gathering, performance, outing] | — | E.6 weak |
| 全 unknown + activity 一致 | [unknown × 5] | [walk × 4, meal × 1] | E.7 weak |
| 全 unknown + activity 散 | [unknown × 5] | [walk, meal, gathering, sightseeing, unknown] | E.8 none |
| 2 张同事件 | [meal × 2] | [meal × 2] | E.1 strong |
| 2 张二选一 | [meal, gathering] | — | E.6 weak |
| event 一致 + activity 散 | [outing × 5] | [walk × 2, sightseeing × 2, gathering × 1] | **E.2 medium** |
| sports + activity gathering (篮球/足球) | [sports × 5] | [gathering × 5] | E.1 strong (接受边界) |
| event=1 + activity 主导 | [outing × 5] | [walk × 4, sightseeing × 1] | E.1 strong |
| event=1 + activity 有 unknown | [meal × 5] | [meal × 3, unknown × 2] | E.2 medium (activity_share=0.6<2/3) |

---

## 五、不变性

1. **band 4 档终值**, 真值表 28 条直读, 不再 score → 阈值
2. **event_primary_share / activity_primary_share 都基于 N (总数)** — unknown 是衰减因子
3. **strong 双重门槛**: event=1.0 AND activity ≥ 2/3 (E.1 唯一通道)
4. **event < 1.0 时不看 activity** — event 自定档 (E.3/E.4/E.5/E.6)
5. **N < 2 → band="none"** (path B 最低门槛 ≥ 2 张, CLAUDE.md 红线 §3)
6. **复用 ADR-0009 `aggregate_event`**, 不重新实现 distribution 算法
7. **activity 兜底 (E.7) 仅在 N_valid ≤ 1 启用**, 最高 weak
8. **activity 二次门槛 (E.1) 与 activity 兜底 (E.7) 是两种独立用法** — 用 `used_activity_gate` / `used_activity_fallback` 字段区分
9. **rule_fired 必填**, 落痕命中规则 (E.1~E.8)
10. **shape 与 rule_fired 一一对应** (8 个 shape ↔ 8 个 E.X)
11. **A3 风险已知接受**: event=sports 大类成集允许混合子类, 子类区分由 theme 维度承担

---

## 六、配置

完整配置见 `config/path_b_event.yaml` (ADR-0012 §2.6). 关键字段:

| 字段 | 默认 | 说明 |
|---|---|---|
| `band_thresholds.strong_share` | 1.0 | E.1 阈值, 不可调 (设计原则: 全员一致才 strong) |
| `band_thresholds.medium_dominant_share` | 0.8 | E.3 阈值 |
| `band_thresholds.medium_mixed_share` | 0.6 | E.4 阈值 |
| `band_thresholds.weak_scattered_share` | 0.4 | E.5 阈值 |
| `activity_gate.min_consensus_ratio` | 0.667 | E.1 二次门槛 2/3 |
| `activity_fallback.min_consensus_ratio` | 0.667 | E.7 兜底 2/3 (共享 gate) |
| `activity_fallback.max_valid_event_for_fallback` | 1 | E.7 启用条件 (N_valid ≤ 1) |
| `activity_fallback.fallback_band` | "weak" | E.7 永不超过 weak |

⚠ **代码禁止硬编码任何上述数值** (CLAUDE.md §3 配置与代码分离).

---

## 七、与 ADR-0009 / ADR-0010 / ADR-0011 的关系

| 维度 | 算法 | 输出范式 | 落痕字段 |
|---|---|---|---|
| ADR-0010 path B location | DBSCAN + PCA OBB + shape 校正 | 直出 band + shape + rule_fired | LocationFeature |
| ADR-0011 path B time | 自然日归属 + 链式切分 + T1/T2/T3 grid | 直出 band + shape + rule_fired | TimeFeature |
| **ADR-0012 path B event (本文)** | **aggregate_event + event/activity 双重 grid** | **直出 band + shape + rule_fired** | **EventFeature** |
| ADR-0009 path A event | aggregate_event + 4 档匹配 | 直出 band + matched_tier | EventMatchResult |

**path B 三维 (location/time/event) 输出范式完全同构**, 真值表 28 条结构不变.

**path A path B event 共享** `aggregate_event(photos)` 函数, 但 band 判定独立 (path A 匹配 / path B 内聚度).
