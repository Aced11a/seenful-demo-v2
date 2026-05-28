# L2 Time 维度判断规范

> **版本**: v0.1 (draft, 待 Ace 审核)
> **日期**: 2026-05-15
> **适用**: Seenful L2 Engine 路径 B time 维度
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (写 ADR-0011 + 后续 docs/src/config/tests).

---

## 一、背景

### 1.1 · 现状 (docs/07 §3.2.2 描述 + src/features/time.py 实际)

| 层 | 内容 | 状态 |
|---|---|---|
| docs/07 §3.2.2 设计 | 双峰检测 + 旅游放宽 (依赖 LocationContext) + 三档表 | 未实现 |
| src/features/time.py 实际 | `span_hours → 查 time_span_bands → score` 单一公式 16 行 | v0.1 简化版 |
| ADR-0004 | 设计了 v1.3.2 完整方案 | location/theme/time 部分 location 已被 ADR-0010 落地, time 仍漂着 |

**核心问题: docs 和代码不一致, 且 docs 设计本身有 21 个缺陷**:
- 双峰检测与旅游档死锁 (跨日游天然多峰, 旅游档判 strong, 双峰判 weak → 冲突)
- 旅游档依赖 `LocationContext`, ADR-0010 已删此字段 → 信号源消失
- 48h 跨度在 home_city 表 vs travel 表跨度跳变巨大 (0.50 vs 1.00)
- 时段不区分"同日 vs 跨日" 语义
- 没识别"自然日断点" / "睡眠时段"
- (完整 21 条见对话记录)

### 1.2 · 引发本 spec 的具体问题

ADR-0010 落地后, time 维度成为最大的算法漂移点:
- LocationContext 删除导致旅游档信号源消失
- TimeFeature.is_travel_relaxed 字段变成死字段
- docs/07 §3.2.2 描述的算法与代码长期不一致

需要重新设计 time 维度, 不只是补缺陷, 而是更换核心信号。

### 1.3 · 本 spec 要做的事

1. **核心范式切换**: 从 "滚动小时窗 (span)" 改为 "自然日 × 一日内事件聚类"
2. **直出 4 档 band**: 与 ADR-0010 location 直出范式对齐
3. **完全独立于 location**: 旅游档判定不依赖 location 任何字段
4. **删除时段硬标签**: morning/midday/afternoon 等距硬切已知缺陷 (10:59 vs 11:01 跨段), 改用基于数据的 1D 时间聚类

**核心约束**:
- time 维度是**放大器** (amplifier_signals), 真值表里 time 单独不能成集, 必须配合主载体 → time strong 不等于"该成集", 等于"时间信号强"
- band 输出严格 ∈ {strong, medium, weak, none}, 4 档, 与真值表 28 条结构对齐 (真值表不变)
- 跨自然日 ≥ 3 天默认不进 strong 档 (Ace 2026-05-15 明示"跨长日太宽松了")
- 不依赖 location.context (ADR-0010 已删此字段)

---

## 二、核心算法范式

### 2.1 · 设计哲学

| 维度 | 旧设计 | 新设计 |
|---|---|---|
| 核心信号 | total_span_hours (滚动小时窗) | K_days (自然日数) + events_per_day (1D 时间聚类) |
| 时段标签 | morning/midday/afternoon 等距硬切 (5 段) | 无, 数据自适应 |
| 多事件检测 | median_gap_ratio > 0.3 (统计指标) | 1D DBSCAN cluster 数 (语义指标) |
| 旅游档触发 | LocationContext ∈ (cross_province, cross_country) | K_days + 跨夜连续性, 独立判 |
| fallback | × 0.5 全局 | 落痕 confidence, 不动 band |
| 与 location 关系 | 单向依赖 (旅游放宽) | 完全解耦 |
| 输出 | 0.0~1.0 score | 直出 band (4 档) |

### 2.2 · "1D 时间 DBSCAN" — 替代时段硬切

**问题**: 等距时段硬切 (morning 6-11 / midday 11-14 / ...) 在边界附近 (10:59 vs 11:01) 把同事件切成两段, 不符合实际语义.

**解法**: 用基于密度的 1D 聚类, 让数据自己说话:

```
输入: 该自然日内的全部 timestamp (排序后)
DBSCAN(eps_minutes=120, min_samples=1)
输出: events_today (该日事件数) + per_event 内部跨度
```

**eps_minutes = 120 (2h) 的直觉**:

| 场景 | 时间间隔 | 聚类判定 |
|---|---|---|
| 同事件内连拍 (午餐拍 5 分钟一张) | < 30 min | 同 cluster ✓ |
| 同事件内分散 (午餐 + 餐后拍照) | 30-90 min | 同 cluster ✓ |
| 同事件内极分散 (午餐 + 餐后聊天 + 离开拍门口) | 90-120 min | 同 cluster (临界) |
| 早餐 → 午餐 (跨事件) | 3-4h | 不同 cluster ✓ |
| 午餐 → 晚餐 (跨事件) | 5-6h | 不同 cluster ✓ |

**与 ADR-0010 location DBSCAN 算法范式同构**:

| 维度 | 路径 A 空间 DBSCAN (ADR-0005) | 路径 B 时间 DBSCAN (本 spec) |
|---|---|---|
| 输入 | GPS (lat, lng) | timestamp |
| eps | 1500m (外层) / 500m (内层) | 120 分钟 |
| min_samples | 2 | 1 (单张也可成事件) |
| 输出 | K_outer / K_inner | events_today |
| 几何特征 | 凸包 / PCA OBB | 簇内 span / 簇间 gap |

⚠ time DBSCAN **没有分级聚类** (不需要 K_inner) — 1D 时间无"退化形状"问题.

### 2.3 · 自然日归属规则

**问题**: 凌晨 2 点拍的照片算"今天" 还是 "昨天" 的活动?

**解法**: **0-6 点归"前一日 night"**:

```python
def get_natural_date(ts):
    if 0 <= ts.hour < 6:
        return ts.date() - timedelta(days=1)
    return ts.date()
```

**理由**:
- 用户体感: 凌晨 2 点的活动是"昨晚的延续", 不是"今天的开始"
- 跨夜活动 (晚 19 点 + 凌晨 2 点) 应判 K_days=1 (同一日), 不是 K_days=2
- 与"自然作息"对齐 (用户睡眠周期 22-23 点入睡, 6-8 点起床)

**边界**: 用户作息差异 (夜班/凌晨工作者) → 极少数, 接受为已知边界 (v0.2 可观察).

---

## 三、核心变量定义

| 变量 | 类型 | 定义 |
|---|---|---|
| **K_days** | int | 涉及自然日数 (有照片的, 应用 §2.3 归属规则后) |
| **span_days** | int | 最早到最晚跨的自然日数 (含空日) |
| **has_empty_days** | bool | span_days > K_days |
| **events_per_day** | dict[date, int] | 每自然日的 1D DBSCAN cluster 数 |
| **max_events_in_any_day** | int | 单日最多事件数 |
| **max_inter_event_gap_h** | float \| None | 同日内最大事件间 gap (小时) |
| **has_overnight_chain** | bool | day1 末事件结束 → day2 首事件开始 gap < 12h |
| **has_dawn_photos** | bool | 是否有 0-6 点照片 (跟自然日归属相关) |
| **total_span_hours** | float | 总跨度 (兜底展示) |
| **fallback_count** | int | upload_time_fallback 数 |
| **fallback_ratio** | float | fallback_count / total |

---

## 四、判定网格

### 4.1 · 路径分流 (K_days 主键)

```
K_days = 0  → 0 张有时间戳 或 全无效 → none
K_days = 1  → 路径 T1 (单日, 用 events_today + intra-day gap)
K_days = 2  → 路径 T2 (跨双日, 用跨夜连续性 + 每日质量)
K_days ≥ 3  → 路径 T3 (长跨, K_days + has_empty_days)
```

### 4.2 · 路径 T1 · 单日 (K_days = 1)

按行顺序匹配, 命中第一条即为基础值:

| # | events_today | max_inter_event_gap_h | day_span_h | band | shape |
|---|---|---|---|---|---|
| T1.1 | 1 | — | ≤ 2 | **strong** | single_event_dense |
| T1.2 | 1 | — | > 2 | **strong** | single_event_extended |
| T1.3 | 2 | < 4 | — | **strong** | adjacent_events (午餐+下午紧接) |
| T1.4 | 2 | ≥ 4 | — | **medium** | distant_events (早+下午, 跨午餐间隔) |
| T1.5 | 3+ | 全部 < 4 | ≤ 12 | **medium** | extended_chain (连续多事件, 见 §4.5) |
| T1.6 | 3+ | — | — | **weak** | multi_events (早午晚 3+ 事件) |

### 4.3 · 路径 T2 · 跨双日 (K_days = 2)

| # | has_overnight_chain | 各日 events | 总跨度 | band | shape |
|---|---|---|---|---|---|
| T2.1 | 是 | 各日 ≤ 2 events | — | **strong** | overnight (过夜活动) |
| T2.2 | 否 | 各日 ≤ 2 events | < 30h | **medium** | weekend_trip (周末双日) |
| T2.3 | — | 至少一日 events ≥ 3 | — | **weak** | sparse_two_days (跨日且某日多事件) |
| T2.4 | 否 | — | ≥ 30h | **weak** | sparse_two_days |

### 4.4 · 路径 T3 · 长跨 (K_days ≥ 3) — 最高 medium

⚠ **设计意图**: 3 天以上即使每日有照片也不进 strong 档 (Ace 2026-05-15 明示"跨长日太宽松了"). 真值表里 time 是 amplifier, 跨日游的 strong 信号由 K_days=2 + 跨夜连续 (T2.1) 承担; ≥ 3 日的判定让主载体 (theme/event/location) 接手.

| # | K_days | has_empty_days | 每日 events | band | shape |
|---|---|---|---|---|---|
| T3.1 | 3-7 | 否 (无空日) | 每日 ≥ 1 event | **medium** | short_trip |
| T3.2 | 3-7 | 是 (中间断裂) | — | **weak** | sparse_short_trip |
| T3.3 | 8-14 | — | — | **weak** | long_trip |
| T3.4 | > 14 | — | — | **none** | scattered_long |

### 4.5 · T1.5 "extended_chain" 解读 (Ace 2026-05-15 提出的边界场景)

**场景**: 西湖一日游 5 张 (9:00 / 11:30 / 13:00 / 15:00 / 17:30)
- 5 张各间隔 2-3h, DBSCAN(eps=120min) 可能切成 4 个 cluster (events_today=4)
- 落 T1.6 weak → 误判 (用户体感"一次连续游玩")

**解法**: 引入 T1.5 "extended_chain"
- 条件: events_today ≥ 3 + 所有相邻事件 gap < 4h + 总跨度 ≤ 12h
- 判定 medium (不进 strong, 但也不掉到 weak)
- 语义: "连续多事件" — 一气呵成的游玩, 但事件数多于普通"两件事"

**验证西湖一日游**:
- events_today = 4 (或 5), gap 都 ≈ 2.5h < 4h, span = 8.5h ≤ 12h
- 命中 T1.5 → **medium** ✓

⚠ T1.5 不进 strong 是有意的: 真"单事件连续" (例如咖啡店连拍 4 张, gap < 1h) 仍走 T1.1/T1.2 strong; T1.5 是"多事件连续" 的中间档.

### 4.6 · 跨夜连续判定

```python
has_overnight_chain = (
    K_days == 2
    and day1_last_event_end is not None
    and day2_first_event_start is not None
    and (day2_first_event_start - day1_last_event_end).total_seconds() / 3600 < 12
)
```

**场景验证**:
- 晚 19 点最后一张 + 次日早 8 点第一张: gap = 13h, > 12h → **不是跨夜连续**
- 晚 22 点最后一张 + 次日早 8 点: gap = 10h → **跨夜连续** ✓
- 晚 23 点最后一张 + 次日早 10 点: gap = 11h → **跨夜连续** ✓

**12h 阈值的直觉**: 用户合理睡眠 + 早起 ≈ 8-10h, 12h 已足够宽容 "晚到 21 点结束 + 早 9 点拍摄" 这类 case; > 12h 是真正的"中间断裂", 不是连续过夜.

---

## 五、Fallback 处理

```python
fallback_count = sum(1 for p in photos if p.captured_at_source == "upload_time_fallback")
fallback_ratio = fallback_count / total_photos

if fallback_ratio == 1.0:
    # 全 fallback: upload_time 不精确, K_days 可能 ±1 天误差
    confidence = 0.5
    落痕 rule_fired += "+k_days_uncertain"
    # band 不直接降, 让 LLM / 真值表上层兜底判
elif fallback_ratio > 0:
    confidence = 1.0 - fallback_ratio * 0.3
else:
    confidence = 1.0
```

**与旧 × 0.5 全局降权的差异**:
- 旧: 全 fallback 时把 score 一刀切减半, 但 score 不再被真值表读 (band 才是)
- 新: band 不动, confidence 落痕给 LLM, 与 ADR-0010 "落痕信号留 LLM 兜底" 范式一致

---

## 六、数据结构 (TimeFeature 升级)

```python
class TimeShape(str, Enum):
    """TimeFeature.shape 枚举 (类比 ADR-0010 LocationShape)."""
    SINGLE_EVENT_DENSE = "single_event_dense"            # T1.1
    SINGLE_EVENT_EXTENDED = "single_event_extended"      # T1.2
    ADJACENT_EVENTS = "adjacent_events"                  # T1.3
    DISTANT_EVENTS = "distant_events"                    # T1.4
    EXTENDED_CHAIN = "extended_chain"                    # T1.5
    MULTI_EVENTS = "multi_events"                        # T1.6
    OVERNIGHT = "overnight"                              # T2.1
    WEEKEND_TRIP = "weekend_trip"                        # T2.2
    SPARSE_TWO_DAYS = "sparse_two_days"                  # T2.3 / T2.4
    SHORT_TRIP = "short_trip"                            # T3.1
    SPARSE_SHORT_TRIP = "sparse_short_trip"              # T3.2
    LONG_TRIP = "long_trip"                              # T3.3
    SCATTERED_LONG = "scattered_long"                    # T3.4
    NO_TIMESTAMP = "no_timestamp"                        # K_days = 0


class TimeFeature(BaseModel):
    """路径 B time 维度产出 (本 spec / ADR-0011 直出 band)."""

    # ★ 真值表直消费
    band: BandLevel                                       # strong | medium | weak | none
    rule_fired: str = Field(min_length=1)                 # "T1.3" / "T2.1" / "T3.1+k_days_uncertain" 等

    # 派生展示 (老 score 字段保留, 真值表不读)
    score: float = Field(ge=0.0, le=1.0)

    # ─── 自然日 + 事件诊断 ──────────────────────────────────
    unique_days_count: int                                # K_days
    span_days: int
    has_empty_days: bool
    events_per_day: dict[str, int]                        # {"2026-05-15": 2, ...}
    max_events_in_any_day: int

    # ─── 时间几何特征 ────────────────────────────────────────
    total_span_hours: float
    max_inter_event_gap_h: float | None                   # 同日内最大 gap, 跨日 None
    has_overnight_chain: bool
    has_dawn_photos: bool

    # ─── fallback ────────────────────────────────────────────
    fallback_count: int
    fallback_ratio: float
    confidence: float

    # ─── 落痕 ────────────────────────────────────────────────
    shape: TimeShape
    primary_signal: str = "captured_at"
```

⚠ **删除的旧字段** (Ace 偏好"老方案直接删, 不留兼容"):
- `is_bimodal` → shape 字段表达更完整
- `is_travel_relaxed` → ADR-0010 删 LocationContext 后已成死字段, 旅游档独立判定不需此字段
- `median_gap_hours` → 不再用 median, 改用 cluster gap
- `all_fallback` → 用 `fallback_ratio` 表达更细
- `time_span_hours` → 重命名为 `total_span_hours` (与 ADR-0010 命名风格对齐)

---

## 七、Case 验证

### Case 1 · 午餐 4 张连拍 (T1.1)

```
timestamps = [12:00, 12:05, 12:10, 12:30]
K_days = 1, events_today = 1 (全在 30 分钟内, eps=120 min 全连)
day_span = 0.5h ≤ 2h → T1.1
band = strong, shape = single_event_dense
```

### Case 2 · 西湖一日游 5 张 (T1.5)

```
timestamps = [9:00, 11:30, 13:00, 15:00, 17:30]
K_days = 1
events_today: 各张间隔 2-2.5h, DBSCAN(eps=120) → 4-5 cluster
max_inter_event_gap_h = 2.5h < 4h
day_span = 8.5h ≤ 12h
→ T1.5 extended_chain
band = medium, shape = extended_chain
```

### Case 3 · 早午晚 3 事件 (T1.6)

```
timestamps = [9:00, 13:00, 19:00]
K_days = 1, events_today = 3, gap = [4h, 6h]
max_inter_event_gap_h = 6h ≥ 4h → T1.6 (不是 T1.5)
band = weak, shape = multi_events
```

### Case 4 · 过夜活动 (T2.1)

```
timestamps = [day1 19:00, day1 21:00, day2 08:00]
K_days = 2
day1 events = 1 (19-21 同 cluster), day1_last_event_end ≈ 21:00
day2 events = 1, day2_first_event_start = 08:00
overnight_gap = 11h < 12h → has_overnight_chain = True
各日 events ≤ 2 → T2.1
band = strong, shape = overnight
```

### Case 5 · 周末双日游 (T2.2)

```
timestamps = [day1 10:00, day2 15:00]
K_days = 2, 各日 events = 1
overnight_gap = 29h ≥ 12h → has_overnight_chain = False
day1 events = 1 ≤ 2, day2 events = 1 ≤ 2
total_span = 29h < 30h → T2.2
band = medium, shape = weekend_trip
```

### Case 6 · 春节回家 5 天 (T3.1)

```
K_days = 5, span_days = 5, has_empty_days = False
每日 events ≥ 1
→ T3.1
band = medium, shape = short_trip
(从旧"strong 旅游档" 收紧到 medium, Ace 2026-05-15 明示)
```

### Case 7 · 国庆 4 天中间 1 天空 (T3.2)

```
K_days = 3 (day1, day2, day4 各有照片), span_days = 4
has_empty_days = True
→ T3.2
band = weak, shape = sparse_short_trip
```

### Case 8 · 凌晨 3 点 + 上午 9 点 (跨睡眠断点 → 自然日归属)

```
timestamps = [03:00, 09:00] (同一日历日)
应用 §2.3 归属: 03:00 归"前一日 night"
→ K_days = 2
day1 events = 1 (03:00 → 实际算前一日), day1_last_event_end = 03:00
day2 events = 1, day2_first_event_start = 09:00
overnight_gap = 6h < 12h → has_overnight_chain = True
各日 events ≤ 2 → T2.1
band = strong, shape = overnight
```

### Case 9 · 2 周以上跨度 (T3.4)

```
K_days = 18
→ T3.4
band = none, shape = scattered_long
(用户大概率把多次出游错合, 不该当一次活动)
```

### Case 10 · 全 fallback (confidence 降低)

```
all photos captured_at_source = "upload_time_fallback"
K_days, events 计算照常, 命中规则照常
但 confidence = 0.5, rule_fired += "+k_days_uncertain"
band 不动, LLM 看到 confidence 可决定是否复审
```

### Case 11 · 早 + 下午 2 事件 (T1.4)

```
timestamps = [9:00, 15:00]
K_days = 1, events_today = 2 (gap = 6h > 120min)
max_inter_event_gap_h = 6h ≥ 4h → T1.4
band = medium, shape = distant_events
```

### Case 12 · 午餐 + 下午紧接 (T1.3)

```
timestamps = [12:30, 14:30]
K_days = 1, events_today = 2 (gap = 2h > 120min? 边界)
若 gap = 2.5h → events_today = 2, max_inter_event_gap_h = 2.5h < 4h → T1.3
band = strong, shape = adjacent_events
```

---

## 八、与 ADR-0010 location 的对称性

| 字段 | ADR-0010 location | 本 spec (将来 ADR-0011) time |
|---|---|---|
| 主聚类信号 | K_outer (空间 DBSCAN, eps=1500m) | events_per_day (时间 DBSCAN, eps=120min) |
| 退化形状识别 | K_inner (eps=500m 重定向) | 不需要 (1D 时间无退化) |
| 内部形状校正 | A2 (PCA OBB + τ) | T1.5 extended_chain (多事件但 gap 小) |
| 高频降档 | ADR-0006 location 高频 (外部 hook) | 无 (不需要, Ace 2026-05-15 明示) |
| 路径分流主键 | K_outer (0/1/2/≥3) | K_days (0/1/2/≥3) |
| 输出 | LocationFeature.band + shape + rule_fired | TimeFeature.band + shape + rule_fired |
| 跟另一维度关系 | 独立 (不读 time) | 独立 (不读 location) — **断 ADR-0007 location→time 依赖链** |

---

## 九、核心不变性

1. **band 4 档终值**, 真值表 28 条直读, 不再 score → 阈值
2. **K_days 是路径分流主键**: 0/1/2/≥3 分流
3. **0-6 点归"前一日 night"**, 决定 K_days 计数, 跟自然作息对齐
4. **1D 时间 DBSCAN eps=120min**, 不再用等距时段标签 (morning/midday/...)
5. **K_days ≥ 3 默认不进 strong 档** (Ace 明示, 跨长日太宽松收紧)
6. **跨夜连续判定 (T2.1) 用 12h 阈值** — 用户合理睡眠周期
7. **旅游档独立于 location.context** — 不依赖 ADR-0010 删除的字段
8. **fallback 不动 band, 落痕 confidence** — 跟 ADR-0010 落痕范式对齐
9. **time 维度独立于 location 维度** — 断单向依赖链
10. **rule_fired 必填** — 落痕命中规则 + 修饰 (例: "T3.1+k_days_uncertain")

---

## 十、配置 (新增 `config/path_b_time.yaml`)

```yaml
path_b_time:

  # ─── 时间 DBSCAN ────────────────────────────────────────
  dbscan:
    eps_minutes: 120              # 同事件最大时间间隔 (经验初值)
    min_samples: 1                # 单张照片也可成事件

  # ─── 自然日归属 ─────────────────────────────────────────
  natural_day:
    dawn_cutoff_hour: 6           # 0-6 点归"前一日 night"

  # ─── 跨夜连接 ───────────────────────────────────────────
  overnight:
    max_gap_hours: 12             # day1 末 → day2 首 gap < 12h 视为连续

  # ─── T1 单日网格 ────────────────────────────────────────
  t1_grid:
    single_event_dense_max_h: 2   # T1.1 day_span ≤ 2h
    adjacent_gap_max_h: 4         # T1.3 / T1.5 内部 gap < 4h
    extended_chain_max_span_h: 12 # T1.5 day_span ≤ 12h

  # ─── T2 跨双日网格 ──────────────────────────────────────
  t2_grid:
    each_day_events_max: 2        # T2.1 / T2.2 各日 events ≤ 2
    total_span_max_h: 30          # T2.2 total_span < 30h, ≥ 30h 走 T2.4

  # ─── T3 长跨网格 ────────────────────────────────────────
  t3_grid:
    short_trip_max_days: 7        # T3.1 / T3.2 K_days ≤ 7
    long_trip_max_days: 14        # T3.3 K_days ≤ 14
    # K_days > 14 → T3.4 none

  # ─── fallback ───────────────────────────────────────────
  fallback:
    full_fallback_confidence: 0.5
    partial_confidence_penalty: 0.3    # confidence = 1 - ratio * 0.3
```

---

## 十一、待决 OQ (本 spec 草稿层面)

### OQ-22a · eps_minutes = 120 是否合理
- **场景**: 影响 events_today 计数, 直接决定 T1 路径命中
- **候选**: 90 / 120 / 180 分钟
- **推荐初值**: 120 分钟, 真实数据 grid search 调
- **依赖**: v0.2 真实数据 (100+ 用户案例标注 "是否同事件")

### OQ-22b · T1.5 extended_chain 边界 (Ace 提出的西湖游边界)
- **场景**: events ≥ 3 但 gap 都 < 4h 且 span ≤ 12h
- **候选**:
  - (a) 调 eps 到 180min (3h), 让西湖游 5 张落到 events=1 走 T1.2 strong
  - (b) 加 T1.5 medium 规则 (本 spec 选)
  - (c) T1.5 改 strong (西湖游强信号)
- **推荐**: (b) — 不污染 T1.1/T1.2 单事件 strong 语义, 又救出真"连续多事件"
- **等 Ace 拍板**

### OQ-22c · T3.1 K_days = 3-7 改 medium 而非 strong
- **场景**: 跨日 3-7 天连续每日有照片
- **方向**: Ace 2026-05-15 明示"跨长日太宽松了" → 收紧到 medium
- **本 spec 已采纳**: T3.1 = medium
- **回滚条件**: v0.2 真实数据上发现"3-7 天连续游" 漏判率 > 30% → 放宽到 strong

### OQ-22d · 跨夜连续 12h 阈值
- **场景**: T2.1 has_overnight_chain 判定
- **候选**: 10h / 12h / 14h
- **推荐**: 12h, 用户合理睡眠 + 早起
- **真实数据后调**

### OQ-22e · 时段归属边界 (0-6 点归前一日)
- **场景**: 凌晨 2 点照片算"昨天" 还是 "今天"
- **本 spec 采纳**: 归"前一日 night"
- **风险**: 夜班工作者 / 凌晨工作者 体感不一致
- **真实数据上 < 5% 用户受影响, 接受**

### OQ-22f · 真值表 D 系列阈值 (time 作为放大器)
- **场景**: time 现 4 档输出, 真值表 28 条不改, 但 D 系列 (time 升档) 是否仍用 time=strong 触发?
- **依赖**: 真值表层校验, ADR-0011 实施时同步审 docs/03

---

## 十二、与 docs/07 §3.2.2 老设计的边界对照 (体感对齐)

| 场景 | 老 (docs/07 §3.2.2 + v0.1 代码) | 新 (本 spec) | 改变 |
|---|---|---|---|
| 午餐 4 张 (12:00-12:30) | 1.00 strong | T1.1 strong | ✓ 一致 |
| 西湖一日游 5 张 (9-17:30) | 0.70 medium (12h 段) | T1.5 medium | ✓ 一致, 但路径变了 |
| 早午晚 3 事件 (9/13/19) | 0.70 medium (旧未实现双峰检测) | T1.6 weak | **新好**: 修了双峰漏判 |
| 过夜活动 (晚 19 + 次日早 8) | 0.50 weak (跨 48h 内) | T2.1 strong | **新好**: 跨夜连续应 strong |
| 周末双日游 (周六 10 + 周日 15) | 0.50 weak | T2.2 medium | **新好**: 周末游应 medium |
| 春节回家 5 天 | 0.20 none (旧旅游档未实现) | T3.1 medium | **新好**: 收紧到 medium 但不 none |
| 国庆 4 天中间 1 天空 | 0.20 none | T3.2 weak | **新好**: 区分"中间断裂" |
| 周一到周五每天午餐 (5 天) | 0.20 none | T3.1 medium | **风险**: 周期性午餐被判 medium, 但靠 location 高频降档兜底 |
| 凌晨 3 点 + 上午 9 点 | 0.70 medium (12h, 不识别跨夜) | T2.1 strong | **新好**: 跨睡眠断点正确归属 |
| 2 周以上跨度 | 0.20 none | T3.4 none | ✓ 一致 |
| 48h 边界 (home vs travel) | 0.50 vs 1.00 巨大跳变 | T2.x medium 平滑 | **新好**: 边界连续 |

---

## 十三、实施清单 (后续 ADR-0011 走 12 步)

本 spec 审核通过后, 按 memory `spec-implementation-workflow` 走 12 步:

| Step | 动作 |
|---|---|
| 1 | 写 `decisions/0011-time-natural-day-event-clustering.md` (引用本 spec) |
| 2 | 写 `docs/17_path_b_time.md` (算法专项规范) |
| 3 | 改 `docs/02_data_contracts.md` (TimeFeature 升级 + TimeShape 枚举) |
| 4 | 改 `docs/07_dimension_thresholds.md` §3.2.2 (重写, 指向 docs/17) |
| 5 | 改 `docs/00/01/11` (索引 + 架构 + observability) |
| 6 | 改 `docs/12_open_questions.md` (新增 OQ-022, 关闭 docs/07 §3.2.2 漂移问题) |
| 7 | 写 `config/path_b_time.yaml` |
| 8 | 改 `src/contracts/features.py` (TimeFeature 升级 + TimeShape) |
| 9 | 改 `src/contracts/__init__.py` 导出 |
| 10 | 重写 `src/features/time.py` (1D DBSCAN + T1/T2/T3 三路判定) |
| 11 | 改 `src/features/assemble.py` 调用方 (输出 TimeFeature 含 band) + `src/policy/bands.py` (Bands.time 直读 TimeFeature.band) |
| 12 | 新建 fixtures + 单测 (T1.1~T1.6 / T2.1~T2.4 / T3.1~T3.4 各 ≥ 1 正例) + 重生 golden + grep 自检 |

**预估量级**: 1 ADR + 1 新 doc + 1 config + 2 src (contracts + features/time + bands 适配) + 6 docs + ~25 单测 + ~10 golden 重生. 跟 ADR-0010 同量级.

---

## 十四、待 Ace 审核

按重要性排序的问题:

1. **核心范式切换** (§二): 从 "span + 双峰" → "K_days + 1D 时间 DBSCAN", 你认可吗?
2. **eps_minutes = 120** (§2.2): 这是关键参数, 决定事件粒度. 默认 120 可接受吗? 还是要调?
3. **T1.5 extended_chain 引入** (§4.5): 救西湖游 5 张被误判为 weak. 你倾向 medium 还是 strong?
4. **T3 收紧到最高 medium** (§4.4): K_days ≥ 3 即使每日有照片也不进 strong. 这是 Ace 已表态的方向, 这里再确认.
5. **0-6 点归"前一日 night"** (§2.3): 决定 K_days 计数, 你认可吗?
6. **跨夜连续 12h 阈值** (§4.6): 用户合理睡眠 + 早起, 12h 偏宽还是偏严?
7. **删除字段清单** (§六): is_bimodal / is_travel_relaxed / median_gap_hours / all_fallback / time_span_hours 重命名, 都按 Ace "老字段直接删" 偏好处理. OK 吗?
8. **fallback 不动 band 改 confidence** (§五): 跟 ADR-0010 范式对齐. OK?
9. **配置文件命名 `path_b_time.yaml`** (§十): 跟 `path_b_location.yaml` 对齐. OK?

审完确认 → 我走 12 步实施 (写 ADR-0011 + 后续 docs/src/config/tests).

---

## 十五、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-15 | 初版, 基于 ADR-0010 落地后 location/time 解耦的需求设计 |
