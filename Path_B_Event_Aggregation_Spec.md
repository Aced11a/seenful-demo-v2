# L2 Path B · Event 维度判断规范

> **版本**: v0.2 (draft, 待 Ace 最终审核)
> **日期**: 2026-05-18
> **适用**: Seenful L2 Engine 路径 B (多张照片自身) event 维度
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (写 ADR-0012 + 后续 docs/src/config/tests).
> **v0.2 改动**: 收紧 event=strong 门槛 (event primary_share = 1.0 + activity ≥ 2/3 双重才 strong), 因 A3 真值表允许 event-only 单独成集 (Ace 2026-05-18 指出 v0.1 strong 阈值过松). 选定篮球/足球场景**接受 (a)** — sports 大类成集合理, 不动 A3. activity 双重门槛 = 2/3.

---

## 一、背景

### 1.1 · 现状

`src/features/event.py` 当前 26 行算法:

```python
def compute_event_score(photos):
    if len(photos) < 2: return 0.0
    hints = [p.semantic_facts.event_hint for p in photos]
    activities = [p.semantic_facts.activity for p in photos]

    valid_hints = [h for h in hints if h != "unknown"]
    if valid_hints and len(set(valid_hints)) == 1 and len(valid_hints) == len(hints):
        return 0.9         # 全部相同 event → 0.9
    if all(h == "unknown" for h in hints):
        valid_acts = [a for a in activities if a != "unknown"]
        if valid_acts and len(set(valid_acts)) == 1 and len(valid_acts) == len(activities):
            return 0.6     # 全 unknown 但 activity 一致 → 0.6
        return 0.0
    return 0.2             # 其他 → 0.2 (严格全员一致才有信号)
```

### 1.2 · 失败模式

**严格全员一致才有 strong 信号** 导致大量误判:

| 场景 | hints 分布 | 老 score | 应该 | 问题 |
|---|---|---|---|---|
| 1 张离群 | [meal, meal, meal, outing] | 0.2 → none | medium/strong | 1 张离群把 strong 拉到 none |
| 多数派 | [meal × 3, gathering × 1] | 0.2 → none | medium | 3:1 是明显多数派, 不该 none |
| 2 张二选一 | [meal, outing] | 0.2 → none | weak (有信号但散) | 2 张就一律 none 太严 |
| 大半 unknown + 少量信号 | [unknown × 3, meal × 2] | 0.2 → none | weak | unknown 不该算反面证据 |
| activity 多数派但不全一致 | hints 全 unknown, activity [walk, walk, walk, meal] | 0.0 → none | weak | activity 多数派应给 weak |

根因: **算法没有"内聚度" 概念**, 把"不完美一致" 一律打成 0.2, 与"完全不相关" 同档.

### 1.3 · 与 path A (ADR-0009) 的关系

**Path A** (ADR-0009 三级分层聚合) 解的是**"1 张新 vs 老相册 aggregation"** 的匹配问题:
- 老相册 N 张 → `aggregate_event(photos)` → `EventAggregation(primary, secondary, tertiary)`
- 新 1 张 event_hint → `match_event(new_event, agg)` → 4 档 band

**Path B 解的是不同问题**: "N 张照片自身的 event 内聚度". **目标不是匹配, 是判定这 N 张是不是讲同一件事**.

但**可以复用 ADR-0009 的 aggregation 算法** (`aggregate_event(photos, cfg)`), 然后在 aggregation 输出上做"内聚度判定" 而不是"匹配".

### 1.4 · 引发本 spec 的具体问题

OQ-009 §9b ("event 严格全员一致 → 多数派 ② 推荐方案 ~30min 改动") 长期未关闭. 现在 path B 时机成熟:
- ADR-0010 location / ADR-0011 time 已落地, **path B 已有 2/7 维直出 band**
- ADR-0009 aggregate_event 已落地, 算法范式 + 代码可直接复用
- 真值表 28 条 B 系列规则强依赖 event band, 修这块**直接影响命中率**

必须改算法范式: **不再算 score, 直出 band + 完整落痕, 与 ADR-0010/0011 输出范式对齐**.

### 1.5 · v0.2 关键约束: A3 让 event-only 单独成集

真值表 A3: `event = 强 → bounds=[medium, strong], type=event` — event 单独 strong 直接出 type="event" 小集, **不需要其他维度配合**.

→ event=strong 的判定门槛必须严, 否则 1 张离群也成集. v0.1 spec primary_share ≥ 0.8 = strong **被 Ace 2026-05-18 否决**, v0.2 收紧到 **event = 1.0 + activity ≥ 2/3 双重**.

**篮球/足球场景** (5 张全 event=sports, activity 都 gathering, 但内容混了篮球+足球):
- L1 activity 7 枚举不区分 sports 子类, 双重门槛仍会判 strong
- Ace 2026-05-18 选定方案 **a · 接受** — sports 大类成集合理, 不为这个场景动 A3 真值表
- 子类区分由 theme 维度 + B 系列规则承担 (用户嫌粒度粗时, theme=弱 触发降档)

---

## 二、核心算法范式

### 2.1 · 设计哲学

| 维度 | 旧设计 | v0.2 新设计 |
|---|---|---|
| 核心信号 | 严格全员一致 (set 大小 = 1) | event primary_share (主导 event 占比 / 总张数) |
| strong 门槛 | event 全员一致 → 0.9 | **event = 1.0 AND activity primary_share ≥ 2/3** (双重) |
| 离群容忍 (strong→medium) | 0 张 (1 张离群即降到 0.2 none) | event 80%-99% → medium; event=100% 但 activity 散 → medium |
| 兜底信号 | 全 unknown + activity 全一致 | N_valid ≤ 1 走 activity 多数派 (≥ 2/3) |
| 与 ADR-0009 | 完全独立 | **复用 `aggregate_event` 算 distribution**, 然后做 path B 专属内聚度判定 |
| 输出 | 0.0~1.0 score | 直出 band (4 档) |

### 2.2 · v0.2 核心: event 优先 + activity 二次门槛

```
event_hint distribution → 算 primary_share (event 主导占比)
   │
   ├─ = 1.0 (全员一致)  → 查 activity (二次门槛)
   │   ├─ activity ≥ 2/3 → strong  (E.1)
   │   └─ activity < 2/3 → medium  (E.2)
   │
   ├─ 0.6 ≤ < 1.0       → medium  (E.3)
   ├─ 0.4 ≤ < 0.6       → weak    (E.4)
   ├─ < 0.4 + N_valid ≥ 2 → weak  (E.5)
   │
   └─ N_valid ≤ 1 (event 缺位)  → activity 兜底
       ├─ activity ≥ 2/3 → weak   (E.6)
       └─ activity 散    → none   (E.7)
```

**关键性质** (Ace 2026-05-18 拍板):
- **event 100% 一致是 strong 必要条件**, 1 张离群即降 medium
- **activity 不污染 event distribution** (不做映射融合)
- **activity 仅作 strong 的二次门槛** (E.1 vs E.2) 和 event 缺位时的兜底 (E.6 / E.7)
- event < 1.0 时 (E.3/E.4/E.5) **不看 activity**, event 已自定档

### 2.3 · 与 ADR-0009 复用边界

```
photos
   │
   ▼
ADR-0009 `aggregate_event(photos, cfg)`  ← 共享
   │
   ▼
EventAggregation { primary, secondary, tertiary, distribution, total_events }
   │
   ├──→ Path A: `match_event(new_event, agg)` → 4 档匹配 band
   └──→ Path B (本 spec): 内聚度判定 grid → 4 档自身 band
```

⚠ **复用粒度**: 只复用 `aggregate_event` 这一个函数 (它本身就是纯函数, 无副作用). 不复用 `match_event` (语义不同).

⚠ **配置分离**: ADR-0009 的 `config/event_aggregation.yaml` 的 `primary_threshold = 0.6 / secondary_threshold = 0.2 / tertiary_min_count = 1` **path B 直接读相同值**, 因为 distribution 的形状定义本身共享; 但 path B 的 band 判定阈值独立配 `config/path_b_event.yaml`.

---

## 三、核心变量定义

### 3.1 · event 主信号

| 变量 | 类型 | 定义 |
|---|---|---|
| **N** | int | 总照片数 (len(photos)) |
| **N_valid** | int | event_hint != "unknown" 的数量 |
| **unknown_share** | float | (N - N_valid) / N |
| **agg** | EventAggregation | ADR-0009 `aggregate_event(photos)` 输出 |
| **primary** | str \| None | agg.primary (占比 ≥ 0.6 of N_valid 的最高频), 可能 None |
| **primary_count** | int | agg.distribution[primary] if primary else 0 |
| **event_primary_share** | float | primary_count / **N** (基于总数, 不是 N_valid) |
| **distinct_events** | int | len(agg.distribution), 不同 event_hint 数 |

**为什么 event_primary_share 基于 N 而不是 N_valid**:
- N_valid = 0 时 event_primary_share = 0, 自动走 activity 兜底 (E.6/E.7)
- N_valid = 2/5 时 share ≤ 0.4, 自动衰减为 weak (unknown 多本身就是信号弱)
- 避免 "[unknown × 3, meal × 2]" 因 N_valid 小而 share = 1.0 误判 strong

### 3.2 · activity 二次信号 (v0.2 新增)

| 变量 | 类型 | 定义 |
|---|---|---|
| **N_activity_valid** | int | activity != "unknown" 的数量 |
| **activity_counter** | Counter[Activity] | activity 字段计数 (含 unknown? 不, 排除) |
| **activity_primary** | str \| None | activity 多数派值 (Counter.most_common(1), 排除 unknown) |
| **activity_primary_count** | int | activity_counter[activity_primary] |
| **activity_primary_share** | float | activity_primary_count / **N** (基于总数, 跟 event 对齐) |

**activity 二次门槛阈值**: 2/3 ≈ 0.667 (Ace 2026-05-18 选定)

**为什么 activity 也基于 N**:
- 跟 event_primary_share 对齐 (同分母)
- N_activity_valid 小时 share 自动衰减, 不会因"少量 activity 有效就 1.0" 误判
- 例 [unknown × 3, walk × 2] → activity_primary_share = 2/5 = 0.4 < 2/3 → 不通过 activity 二次门槛

---

## 四、判定网格 (E 系列, 8 行) — v0.2 收紧 strong 双重门槛

按行顺序匹配, 命中第一条即为基础值:

| # | event_primary_share | activity_primary_share | N_valid | band | shape |
|---|---|---|---|---|---|
| E.1 | **= 1.0** | **≥ 2/3** | — | **strong** | unanimous_event_activity |
| E.2 | = 1.0 | < 2/3 | — | **medium** | unanimous_event_mixed_activity |
| E.3 | 0.8 ≤ < 1.0 | — | — | **medium** | dominant_event |
| E.4 | 0.6 ≤ < 0.8 | — | — | **medium** | mixed_event |
| E.5 | 0.4 ≤ < 0.6 | — | — | **weak** | scattered_event |
| E.6 | < 0.4 | — | ≥ 2 | **weak** | fragmented_event |
| E.7 | — (兜底) | ≥ 2/3 | ≤ 1 | **weak** | activity_fallback |
| E.8 | — (兜底) | < 2/3 | ≤ 1 | **none** | no_event_signal |

### 4.1 · E.1 unanimous_event_activity (strong) — v0.2 新, 双重门槛

**条件**: event_primary_share = 1.0 (**全员同一 event**) AND activity_primary_share ≥ 2/3

**典型 case**:
- [event=meal × 5] + [activity=meal × 5] → 1.0 + 1.0 → **strong**
- [event=meal × 5] + [activity=meal × 4, unknown × 1] → 1.0 + 0.8 → **strong**
- [event=outing × 5] + [activity=walk × 4, sightseeing × 1] → 1.0 + 0.8 → **strong** (子 activity 不同但都属外出, OK)

**直觉**: 5 张照片**完全是同一类活动**, 而且**多数照片的具体行为也一致**, 才允许单独成集 (A3 strong 触发).

⚠ **A3 风险接受 (方案 a)**: [event=sports × 5] + [activity=gathering × 5] = strong, 即使内容可能是篮球+足球混合. activity 7 枚举无法区分 sports 子类, **接受 sports 大类成集语义**, 子类区分让 theme 维度 + 真值表 B 系列承担.

### 4.2 · E.2 unanimous_event_mixed_activity (medium) — v0.2 新

**条件**: event_primary_share = 1.0 AND activity_primary_share < 2/3

**典型 case**:
- [event=outing × 5] + [activity=walk × 2, sightseeing × 2, gathering × 1] (activity 散) → **medium**
- [event=daily_record × 5] + [activity=walk × 2, resting × 2, gardening × 1] → **medium**

**直觉**: event 大类完全一致, 但具体活动方式三心二意 — 不到 strong 力度.

### 4.3 · E.3 dominant_event (medium)

**条件**: 0.8 ≤ event_primary_share < 1.0

**典型 case**:
- [meal × 4, gathering × 1] (4/5 = 0.8) → medium (老 spec strong, **v0.2 降一档**)
- [meal × 5, unknown × 1] (5/6 ≈ 0.83) → medium
- [meal × 8, gathering × 2] (8/10 = 0.8) → medium

**直觉**: 80%+ 一致是明显主导, 但有 1-2 张离群, 不到 strong (event 单独成集) 的安全门槛.

### 4.4 · E.4 mixed_event (medium)

**条件**: 0.6 ≤ event_primary_share < 0.8

**典型 case**:
- [meal × 3, gathering × 2] (3/5 = 0.6) → medium
- [meal × 3, gathering × 1, performance × 1] (3/5 = 0.6) → medium
- [meal × 3, unknown × 1, gathering × 1] (3/5 = 0.6) → medium

**直觉**: 有主导事件但同时存在副事件 (生日会有 meal + celebration; 旅游有 sightseeing + meal).

### 4.5 · E.5 scattered_event (weak)

**条件**: 0.4 ≤ event_primary_share < 0.6

**典型 case**:
- [meal × 2, gathering × 1, unknown × 2] (primary=meal in valid 2/3=0.67 ≥ 0.6, share=2/5=0.4) → weak
- [meal × 2, gathering × 1, performance × 1, outing × 1] (primary=None, share=0) → 落 E.6 不是 E.5

⚠ **share vs ratio 区分**: ADR-0009 primary_threshold (0.6 of N_valid) 决定 primary 是否存在; path B share (基于 N) 决定 band. unknown 多时 share 会衰减.

### 4.6 · E.6 fragmented_event (weak)

**条件**: event_primary_share < 0.4 (含 primary=None) + N_valid ≥ 2

**典型 case**:
- [meal × 2, gathering × 2] (primary=None, share=0) + N_valid=4 → weak
- [meal × 1, gathering × 1, performance × 1] (primary=None, share=0) + N_valid=3 → weak
- [meal, gathering] (2 张二选一, primary=None, share=0) + N_valid=2 → weak

### 4.7 · E.7 activity_fallback (weak)

**条件**: N_valid ≤ 1 (event 几乎全 unknown) + activity_primary_share ≥ 2/3

**典型 case**:
- [unknown × 5] + [activity=walk × 4, meal × 1] (4/5 = 0.8 ≥ 2/3) → weak
- [unknown × 4, meal × 1] + [activity=walk × 5] (1.0) → weak

**为什么 activity 一致也只到 weak**: activity 跟 event 有重叠但语义更宽. 走兜底就该谦虚, 不能让 activity-only 单独触发 A3 strong.

### 4.8 · E.8 no_event_signal (none)

**条件**: N_valid ≤ 1 + activity_primary_share < 2/3

**典型 case**:
- [unknown × 5] + [activity=walk, meal, gathering, sightseeing, unknown] → none

---

## 五、Case 验证 (14 个, v0.2 加 4 个测 activity 二次门槛)

### Case 1 · 全部同事件 + activity 一致 (E.1 strong)
```
event_hints = [meal × 5]
activities  = [meal × 5]
event_share = 1.0, activity_share = 1.0
→ E.1 strong, shape=unanimous_event_activity
```

### Case 2 · 4:1 主导 (E.3 medium, v0.2 降档)
```
event_hints = [meal × 4, gathering × 1]
event_share = 4/5 = 0.8
→ E.3 medium, shape=dominant_event
(老 spec strong, v0.2 收紧到 medium — 防 1 张离群也单独成集)
```

### Case 3 · 3:2 主导 (E.4 medium)
```
event_hints = [meal × 3, gathering × 2]
event_share = 3/5 = 0.6
→ E.4 medium, shape=mixed_event
```

### Case 4 · 2 张 meal + 1 gathering + 2 unknown (E.5 weak)
```
event_hints = [meal × 2, gathering × 1, unknown × 2]
N=5, N_valid=3
primary=meal (2/3=0.67 ≥ 0.6 ADR-0009 threshold)
event_share = 2/5 = 0.4
→ E.5 weak, shape=scattered_event
```

⚠ **Case 4 解读**: 即使 meal 在 valid 中占主导 (2/3), 但 unknown 占 40%, 总体 share 仅 0.4 → weak. share 基于 N 的设计意图.

### Case 5 · 各半二选一 (E.6 weak)
```
event_hints = [meal × 2, gathering × 2]
primary=None (0.5 < 0.6 ADR-0009 threshold)
event_share = 0
→ E.6 weak, shape=fragmented_event
```

### Case 6 · 三向散乱 (E.6 weak)
```
event_hints = [meal, gathering, performance, outing]
primary=None, event_share = 0
→ E.6 weak, shape=fragmented_event
```

### Case 7 · 全 unknown + activity 一致 (E.7 weak)
```
event_hints = [unknown × 5]
activities  = [walk × 4, meal × 1]
N_valid=0 ≤ 1, activity_share = 4/5 = 0.8 ≥ 2/3
→ E.7 weak, shape=activity_fallback
```

### Case 8 · 全 unknown + activity 散 (E.8 none)
```
event_hints = [unknown × 5]
activities  = [walk, meal, gathering, sightseeing, unknown]
activity_share = 1/5 = 0.2 < 2/3
→ E.8 none, shape=no_event_signal
```

### Case 9 · 2 张同事件 + activity 一致 (E.1 strong)
```
event_hints = [meal, meal]
activities  = [meal, meal]
event_share = 1.0, activity_share = 1.0
→ E.1 strong, shape=unanimous_event_activity
```

### Case 10 · 2 张二选一 (E.6 weak)
```
event_hints = [meal, gathering]
event_share = 0 (primary=None)
→ E.6 weak, shape=fragmented_event
(老算法 0.2 = none, 新算法 weak)
```

### Case 11 · event 一致但 activity 散 — v0.2 关键 (E.2 medium)
```
event_hints = [outing × 5]
activities  = [walk × 2, sightseeing × 2, gathering × 1]
event_share = 1.0, activity_share = 2/5 = 0.4 < 2/3
→ E.2 medium, shape=unanimous_event_mixed_activity
```

⚠ **Case 11 验证 v0.2 双重门槛**: 5 张 event 完全一致 (outing) 但 activity 三心二意 (走/观/聚) → 不 strong, 降 medium. 老 spec 给 strong.

### Case 12 · event=sports 一致 + activity=gathering 一致 (E.1 strong, 篮球/足球场景)
```
event_hints = [sports × 5]
activities  = [gathering × 5]  # 篮球/足球 activity 都落 gathering
event_share = 1.0, activity_share = 1.0
→ E.1 strong, shape=unanimous_event_activity
```

⚠ **Case 12 接受边界 (方案 a)**: 此 case 内容可能混了篮球+足球, 但 L1 activity 7 枚举区分不了. 接受 sports 大类成集语义. 子类区分让 theme 维度承担 (theme=weak 会通过 B 系列降档).

### Case 13 · event 100% + activity 多数派 (E.1 strong)
```
event_hints = [outing × 5]
activities  = [walk × 4, sightseeing × 1]
event_share = 1.0, activity_share = 4/5 = 0.8 ≥ 2/3
→ E.1 strong, shape=unanimous_event_activity
(activity 主导 walk 多数派, 1 张 sightseeing 离群可接受)
```

### Case 14 · event 100% + activity 有 unknown (E.1 或 E.2 边界)
```
event_hints = [meal × 5]
activities  = [meal × 3, unknown × 2]
event_share = 1.0
activity_share = 3/5 = 0.6 < 2/3
→ E.2 medium, shape=unanimous_event_mixed_activity
```

⚠ **Case 14**: activity 有 unknown 降低 activity_share. 即使 valid activity 全是 meal, 总分母含 unknown 后 share=0.6 < 2/3 → 降 medium. 这是基于 N 的设计意图.

---

## 六、数据结构 (EventFeature 升级, v0.2)

```python
class EventShape(str, Enum):
    """EventFeature.shape 落痕枚举 (v0.2, 8 行 grid 对应)."""
    UNANIMOUS_EVENT_ACTIVITY = "unanimous_event_activity"           # E.1 strong
    UNANIMOUS_EVENT_MIXED_ACTIVITY = "unanimous_event_mixed_activity"  # E.2 medium
    DOMINANT_EVENT = "dominant_event"                               # E.3 medium
    MIXED_EVENT = "mixed_event"                                     # E.4 medium
    SCATTERED_EVENT = "scattered_event"                             # E.5 weak
    FRAGMENTED_EVENT = "fragmented_event"                           # E.6 weak
    ACTIVITY_FALLBACK = "activity_fallback"                         # E.7 weak
    NO_EVENT_SIGNAL = "no_event_signal"                             # E.8 none


class EventFeature(BaseModel):
    """路径 B event 维度产出 (ADR-0012 直出 band).

    band 是真值表消费的 4 档终值. 其他字段为落痕诊断.
    """

    # ★ 真值表直消费
    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "E.1" / "E.2" / "E.7" 等

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── event 分布诊断 ──────────────────────────────────────
    total_photos: int                                # N
    valid_event_count: int                           # N_valid
    unknown_share: float                             # unknown 占比 (N - N_valid) / N
    primary_event: str | None                        # agg.primary
    primary_count: int                               # distribution[primary]
    event_primary_share: float                       # primary_count / N (基于总数)
    secondary_events: list[str]                      # agg.secondary
    tertiary_events: list[str]                       # agg.tertiary
    distinct_events: int                             # len(distribution)

    # ─── activity 二次门槛诊断 (v0.2 新) ────────────────────
    activity_primary: str | None                     # activity 多数派 (Counter.most_common, 排除 unknown)
    activity_primary_count: int
    activity_primary_share: float                    # activity_primary_count / N
    used_activity_gate: bool                         # 是否走 E.1 二次门槛 (event=1.0 时启用)
    used_activity_fallback: bool                     # 是否走 E.7 (N_valid ≤ 1 兜底)

    # ─── 落痕 ────────────────────────────────────────────────
    shape: EventShape
    primary_signal: str = "event_hint"
```

**v0.2 新增字段**: `activity_primary_count` + `used_activity_gate` (区分二次门槛 vs 兜底).

**⚠ FeaturePackage.event** 字段需要新增 (类比 location / time):
```python
class FeaturePackage(BaseModel):
    ...
    location: LocationFeature | None    # ADR-0010
    time: TimeFeature | None             # ADR-0011
    event: EventFeature | None           # ADR-0012 新增
    theme: ThemeFeature | None
```

---

## 七、与 ADR-0009 的关系

| 维度 | ADR-0009 (Path A) | 本 spec (Path B, ADR-0012) | 共享/独立 |
|---|---|---|---|
| 算法目标 | "1 张新 vs 老相册 aggregation" 匹配 | "N 张自身 event_hint 内聚度" 判定 | **独立 (不同问题)** |
| `aggregate_event(photos)` | 用于构建 album.event_agg | 用于 N 张自身的 distribution | **共享 (同函数)** |
| `match_event(new_event, agg)` | 4 档匹配 band | 不用 | 仅 Path A |
| primary_threshold / secondary_threshold | 0.6 / 0.2 (基于 N_valid) | 同上, 复用 ADR-0009 yaml | **共享 (同 config)** |
| band 判定阈值 | match 4 档 (primary=strong / secondary=medium / tertiary=weak / 其他=none) | E.1~E.6 grid (基于 primary_share) | **独立 (path_b_event.yaml)** |
| 输出契约 | EventMatchResult | EventFeature | **独立** |
| L1 字段 event_hint 10 枚举 | 共享 | 共享 | **共享** |
| EventAggregation 数据结构 | 共享 | 共享 | **共享** |

**结论**: Path A vs Path B 共享底层 distribution 算法 + L1 枚举, 但**匹配 vs 内聚度** 是不同问题, 各自的 band 判定独立设计.

---

## 八、不变性 (v0.2)

1. **band 4 档终值**, 真值表 28 条直读, 不再 score → 阈值
2. **event_primary_share / activity_primary_share 都基于 N (总数), 不是 N_valid** — unknown 是信号衰减因子
3. **strong 双重门槛**: event = 1.0 AND activity ≥ 2/3 (E.1 唯一通道)
4. **event < 1.0 时不看 activity** — event 自定档 (E.3/E.4/E.5/E.6)
5. **N < 2 → band="none"** (path B 最低门槛 ≥ 2 张, CLAUDE.md 红线 §3 "2 张永远不成集" 对齐)
6. **复用 ADR-0009 `aggregate_event`**, 不重新实现 distribution 算法
7. **activity 兜底 (E.7) 仅在 N_valid ≤ 1 启用**, 最高 weak (不超过 event 信号能给的上限)
8. **activity 二次门槛 (E.1) 与 activity 兜底 (E.7) 是两种独立用法** — 用 `used_activity_gate` / `used_activity_fallback` 字段区分
9. **rule_fired 必填**, 落痕命中规则 (例: "E.1" / "E.2" / "E.7")
10. **shape 与 rule_fired 一一对应** (8 个 shape ↔ 8 个 E.X 规则)
11. **A3 风险已知接受**: event=sports 大类成集允许混合子类 (篮球+足球), 子类区分由 theme 维度承担

---

## 九、配置 (新增 `config/path_b_event.yaml`)

```yaml
path_b_event:

  # ─── event 内聚度阈值 (基于 event_primary_share) ──────
  band_thresholds:
    strong_share: 1.0              # E.1: event 全员一致 (v0.2 收紧)
    medium_dominant_share: 0.8     # E.3: 80%-100% 主导
    medium_mixed_share: 0.6        # E.4: 60%-80% 混合
    weak_scattered_share: 0.4      # E.5: 40%-60% 散乱
    # < 0.4 → E.6 fragmented weak

  # ─── activity 二次门槛 (v0.2 新, E.1 strong 必需) ────
  activity_gate:
    min_consensus_ratio: 0.667     # 2/3 多数派, Ace 2026-05-18 选定

  # ─── activity 兜底 (E.7, N_valid ≤ 1 时启用) ────────
  activity_fallback:
    min_consensus_ratio: 0.667     # 同 gate, 共享 2/3 阈值
    max_valid_event_for_fallback: 1  # N_valid ≤ 1 才启用
    fallback_band: "weak"          # 兜底永不超过 weak

  # ─── 引用 ADR-0009 配置 (不复制) ────────────────────
  # aggregate_event 内部仍读 config/event_aggregation.yaml::event_aggregation
  # primary_threshold = 0.6 (基于 N_valid 的 ratio)
  # secondary_threshold = 0.2
  # tertiary_min_count = 1
```

⚠ **代码禁止硬编码**: `strong_share / medium_share / weak_share / min_consensus_ratio` 都走 yaml.

---

## 十、待决 OQ (本 spec v0.2)

### OQ-23a · band_thresholds 经验值

- v0.2 阈值: strong=1.0 / medium_dominant=0.8 / medium_mixed=0.6 / weak_scattered=0.4
- v0.2 真实数据 grid search:
  - strong: 仅 1.0 (不可调, 这是设计原则 — 全员一致才 strong)
  - medium_dominant: 0.75 / 0.8 / 0.85
  - medium_mixed: 0.55 / 0.6 / 0.65
  - weak_scattered: 0.35 / 0.4 / 0.45
- 与 ADR-0009 primary_threshold (0.6 of N_valid) **的关系**: 不直接可比 (一个 N 基, 一个 N_valid 基)

### OQ-23b · activity 二次门槛 ratio = 2/3 是否合理

- v0.2 选定: 2/3 ≈ 0.667 (Ace 2026-05-18)
- 候选: 0.6 (≥3/5) / 2/3 (Ace 选) / 0.75 (≥3/4) / 0.8 (≥4/5)
- 风险: 2/3 太松 → Case 13 [outing × 5] + [walk × 4, sightseeing × 1] 升 strong 是否符合直觉?
- v0.2 真数据 + 人工 review 后调

### OQ-23c · activity 兜底 max_valid_event_for_fallback

- 当前: N_valid ≤ 1 才启用 activity 兜底 (E.7/E.8)
- 候选: ≤ 0 (严格全 unknown 才用) / ≤ 1 (1 张 event 也容忍兜底) / ≤ 2
- **推荐 ≤ 1**: "1 张 event 信号不稳, 用 activity 多数派救一下" 直觉合理

### OQ-23d · activity fallback band 上限 weak

- 当前: 永不超过 weak (E.7)
- 候选: 让 activity 兜底也能到 medium (如果 activity 100% 一致)?
- **推荐保留 weak 上限**: activity 语义比 event 宽, 不该比 event 信号更强

### OQ-23e · sports 子类 (篮球/足球) 接受边界 v0.2 验证

- v0.2 选定方案 a (接受 sports 大类成集)
- 风险: 真实用户上传 5 张运动照片, 内容混 (篮球 + 足球 + 网球), 单独成"运动相册" 是否符合体感?
- v0.2 真实数据收集 100+ sports 案例:
  - "希望成集" 占比 > 70% → 方案 a 验证通过
  - "希望细分" 占比 > 30% → 触发 ADR-0012-补丁 (拆 A3 真值表 / 扩 activity 枚举 / event 维度内吸收 main_subjects)
- 依赖 theme 维度同期升级 (path B theme ADR-0014 待规划), theme=弱 才能通过 B 系列降档

### OQ-23f · 真值表 B / D / E 系列与新 medium 大量出现的兼容性

- 老算法严格全员一致才 0.9 strong, 否则 0.2 none
- 新算法 v0.2: 4:1 / 3:2 / 80%-100% 都变 medium (新增大量 medium 命中)
- 影响: B 系列 (multi-medium 组合) 命中率上升, 多 mini album 数会涨
- 依赖 ADR-0012 实施时 golden 重生 + 人工 review B 系列命中样本是否合理

---

## 十一、与 docs/07 老设计的边界对照 (v0.2)

| 场景 | 老 score | 老 band | v0.2 band | 体感判断 |
|---|---|---|---|---|
| [meal × 5] + [activity=meal × 5] | 0.9 | strong | **E.1 strong** | ✓ 一致 |
| [meal × 5] + [activity 散] | 0.9 | strong | **E.2 medium** | **v0.2 新降** (event 一致但 activity 散) |
| [meal × 4, gathering × 1] | 0.2 | none | **E.3 medium** | **v0.2 升** (4:1 是 medium, 不再 none, 但也不 strong) |
| [meal × 3, gathering × 2] | 0.2 | none | **E.4 medium** | **v0.2 升** (3:2 是 medium) |
| [meal × 3, gathering × 1, performance × 1] | 0.2 | none | **E.4 medium** | **v0.2 升** |
| [meal, meal] + [activity=meal × 2] | 0.9 | strong | **E.1 strong** | ✓ 一致 |
| [meal, gathering] | 0.2 | none | **E.6 weak** | **v0.2 升** (2 张二选一 weak) |
| [unknown × 5] + [activity=walk × 5] | 0.6 | medium | **E.7 weak** | **v0.2 降** (activity 兜底不该 medium) |
| [unknown × 5] + [activity=walk × 4, meal × 1] | 0.0 | none | **E.7 weak** | **v0.2 升** (4:1 多数派应 weak) |
| [unknown × 3, meal × 2] | 0.2 | none | **E.5 weak** | **v0.2 升** (有信号但弱) |
| [sports × 5] + [activity=gathering × 5] (篮球/足球混) | 0.9 | strong | **E.1 strong** | 接受边界 (方案 a, OQ-23e 验证) |
| [outing × 5] + [activity=walk × 4, sightseeing × 1] | 0.9 | strong | **E.1 strong** | ✓ activity 主导一致, strong 合理 |

⚠ **主要变化**:
- **新 strong 严格化**: 仅 event=1.0 + activity ≥ 2/3 才 strong (老 0.9 strong 大量降到 medium)
- **新 medium 大量出现**: 老 none 类 case (4:1/3:2 等) 升到 medium → B 系列规则命中率上升, mini album 数会涨, 需 golden review
- **activity 兜底从 medium 降到 weak**: 老 0.6 medium → 新 weak, B 系列触发率轻微下降

---

## 十二、实施清单 (后续 ADR-0012 走 12 步)

本 spec 审核通过后, 按 memory `spec-implementation-workflow` 走 12 步:

| Step | 动作 |
|---|---|
| 1 | 写 `decisions/0012-path-b-event-aggregation.md` (引用本 spec) |
| 2 | 写 `docs/18_path_b_event.md` (算法专项规范) |
| 3 | 改 `docs/02_data_contracts.md` (EventFeature + EventShape) |
| 4 | 改 `docs/07_dimension_thresholds.md` §3.2.4 (event_score 段重写, 指向 docs/18) |
| 5 | 改 `docs/00/01/11/12` (索引 + 架构 + observability + OQ-023) |
| 6 | 改 OQ-009 §9b 状态: "待决 → 已关闭 (ADR-0012)" |
| 7 | 写 `config/path_b_event.yaml` |
| 8 | 改 `src/contracts/features.py` (EventFeature + EventShape + FeaturePackage.event) |
| 9 | 改 `src/contracts/__init__.py` 导出 |
| 10 | 重写 `src/features/event.py` (build_event_feature 高层入口 + E.1~E.7 grid) |
| 11 | 改 `src/features/assemble.py` (注入 EventFeature) + `src/policy/bands.py` (Bands.event 直读) |
| 12 | 新建单测 (E.1~E.7 + activity 兜底 + 边界) + 重生 golden + grep 自检 + 归档本 spec |

**预估量级**: 1 ADR + 1 新 doc + 1 config + 2 src (contracts + features/event + bands 适配) + 5 docs + ~15 单测 + ~5 golden 重生. 比 ADR-0011 略小.

---

## 十三、待 Ace 最终审核 (v0.2, 已根据 Y/A/2/3 修订)

已确认的决策 (Ace 2026-05-18 拍板, 写进 spec):
- ✅ **方案 Y**: event 100% + activity ≥ 2/3 双重门槛
- ✅ **方案 a**: 接受 sports 大类成集 (篮球/足球场景), 不动 A3
- ✅ **activity 二次门槛 = 2/3**

最终审核点 (剩 6 个):

1. **§四 8 行 grid 命名 / 行号 排列** OK 吗?
2. **§五 14 个 Case 验证** 有没有要补的边界?
3. **§六 EventShape 8 个枚举值命名** OK 吗?
4. **§九 config 命名 `path_b_event.yaml`** 跟 `path_b_location.yaml` / `path_b_time.yaml` 对齐. OK?
5. **§十 OQ-23a~f** 6 个 OQ 编号 + 内容 OK 吗?
6. **关闭 OQ-009 §9b**: ADR-0012 落地后 §9b 转 "已关闭". OK 吗?

审完一句"全 OK" 或挑要改的, 我立即走 12 步实施 (写 ADR-0012 + docs/18 + config/path_b_event.yaml + src/contracts/EventFeature + 重写 src/features/event.py + 测试 + golden 重生 + 归档).

---

## 十四、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-18 | 初版, 复用 ADR-0009 aggregate_event + 引入 primary_share 内聚度 grid (E.1~E.7) + activity 兜底 |
| v0.2 (draft) | 2026-05-18 | Ace 拍板收紧 strong 门槛 (Y/A/2/3): event=1.0 + activity ≥ 2/3 双重才 strong; 8 行 grid (E.1~E.8); 加 EventShape 8 枚举 (UNANIMOUS_EVENT_ACTIVITY 等); 加 activity_primary_share 字段 + used_activity_gate 区分二次门槛 vs 兜底; A3 风险接受边界 (方案 a) + OQ-23e 跟踪; 14 Case 验证含 4 个 v0.2 新边界 |
