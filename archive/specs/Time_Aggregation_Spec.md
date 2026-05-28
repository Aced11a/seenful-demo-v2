# L2 Time 维度判断规范

> **版本**: v0.2 (draft, 待 Ace 审核)
> **日期**: 2026-05-18
> **适用**: Seenful L2 Engine 路径 B time 维度
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (写 ADR-0011 + 后续 docs/src/config/tests).
> **v0.2 改动**: 修问题① 算法误称 (DBSCAN→链式切分), 修问题④ T1.3/T1.5 strong 断层, 加 §4.7 边界保护带缓解 gap 阈值脆性.

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
| 核心信号 | total_span_hours (滚动小时窗) | K_days (自然日数) + events_per_day (**时间链式切分**) |
| 时段标签 | morning/midday/afternoon 等距硬切 (5 段) | 无, 数据自适应 |
| 多事件检测 | median_gap_ratio > 0.3 (统计指标) | 链式切分 cluster 数 (语义指标) |
| 旅游档触发 | LocationContext ∈ (cross_province, cross_country) | K_days + 跨夜连续性, 独立判 |
| fallback | × 0.5 全局 | 落痕 confidence, 不动 band |
| 与 location 关系 | 单向依赖 (旅游放宽) | 完全解耦 |
| 输出 | 0.0~1.0 score | 直出 band (4 档) |

### 2.2 · 时间链式切分 (gap-based time segmentation) — 替代时段硬切

**问题**: 等距时段硬切 (morning 6-11 / midday 11-14 / ...) 在边界附近 (10:59 vs 11:01) 把同事件切成两段, 不符合实际语义.

**解法**: 按相邻时间戳 gap 阈值做链式切分, 让数据自己说话:

```
输入: 该自然日内的全部 timestamp (排序后)
算法: 任意相邻 gap > eps_minutes → 切分; gap ≤ eps_minutes → 同 cluster
     (链式连通: A-B 同 cluster, B-C 同 cluster ⇒ A-B-C 同 cluster)
参数: eps_minutes = 120
输出: events_today (该日事件数) + 簇间 gap / 簇内 span
```

⚠ **命名澄清 (v0.2 修问题①)**: 早版称"1D 时间 DBSCAN" 是误称.
- DBSCAN 的核心是 `min_samples ≥ 2` 的密度核心点 + density-reachable 扩展.
- 本算法 `min_samples = 1` 退化为 single-linkage gap 切分, 跟 DBSCAN 的抗噪 / 核心点机制脱钩.
- 跟 ADR-0010 location 真 DBSCAN (`min_samples=2` + 密度扩展) **不是同构**, 仅"按距离阈值连通" 这一层相似.
- 改称"时间链式切分" / `gap_based_segmentation`, 避免 Wenyi prompt QA / 后续 reviewer 误读算法保证.

**eps_minutes = 120 (2h) 的直觉**:

| 场景 | 时间间隔 | 切分判定 |
|---|---|---|
| 同事件内连拍 (午餐拍 5 分钟一张) | < 30 min | 同 cluster ✓ |
| 同事件内分散 (午餐 + 餐后拍照) | 30-90 min | 同 cluster ✓ |
| 同事件内极分散 (午餐 + 餐后聊天 + 离开拍门口) | 90-120 min | 同 cluster (临界, 见 §4.7 边界保护带) |
| 早餐 → 午餐 (跨事件) | 3-4h | 不同 cluster ✓ |
| 午餐 → 晚餐 (跨事件) | 5-6h | 不同 cluster ✓ |

**与 ADR-0010 location 算法的关系 (诚实对照)**:

| 维度 | 路径 A 空间 DBSCAN (ADR-0010) | 路径 B 时间链式切分 (本 spec) |
|---|---|---|
| 算法本质 | DBSCAN (密度核心点 + 扩展) | gap 阈值链式切分 (single linkage) |
| 输入 | GPS (lat, lng) 二维 | timestamp 一维 |
| 阈值参数 | eps=1500m (外) / 500m (内), min_samples=2 | eps=120min, min_samples=1 |
| 抗噪 / 离群点 | DBSCAN 自动判离群 (噪声点) | 无 (单张时间戳即一个 cluster) |
| 退化形状处理 | A2 PCA OBB + τ 校正 | 不需要 (1D 无形状概念) |
| 输出 | K_outer / K_inner / shape | events_today / 簇间 gap |

⚠ time **不是分级聚类** (无 K_inner) — 1D 时间无"退化形状" 问题, 但**也没有 DBSCAN 的密度概念**, 算法上更接近 numpy `np.split` 按 gap 切.

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
| **max_inter_cluster_gap_h** | float \| None | 同日内最大 cluster 间 gap (小时, 跨日为 None). v0.2 拆名澄清歧义 (问题⑦) |
| **max_intra_cluster_span_h** | float \| None | 同日内单 cluster 内部最大 span (小时), 用于落痕诊断, 永远 ≤ eps_minutes/60 |
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

| # | events_today | max_inter_cluster_gap_h | day_span_h | band | shape |
|---|---|---|---|---|---|
| T1.1 | 1 | — | ≤ 2 | **strong** | single_event_dense |
| T1.2 | 1 | — | > 2 | **strong** | single_event_extended |
| T1.3 | 2 | < 4 | — | **strong** | adjacent_events (午餐+下午紧接) |
| T1.4 | 2 | ≥ 4 | — | **medium** | distant_events (早+下午, 跨午餐间隔) |
| T1.5 | 3-5 | 全部 < 4 | ≤ 12 | **strong** | extended_chain (连续多事件, v0.2 升 strong, 见 §4.5) |
| T1.6 | ≥ 6 | 全部 < 4 | ≤ 12 | **medium** | dense_chain (单日过密多事件, v0.2 新增) |
| T1.7 | ≥ 3 | ≥ 4 (任一) | — | **weak** | multi_events_break (有≥4h断裂) |
| T1.8 | ≥ 3 | < 4 | > 12 | **weak** | overstretched_chain (跨度过长) |

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

### 4.5 · T1.5 "extended_chain" 解读 (v0.2 修问题④ 断层)

**场景**: 西湖一日游 5 张 (9:00 / 11:30 / 13:00 / 15:00 / 17:30)

**实际切分** (eps=120min):
- gaps (min): [150, 90, 120, 150]
- > 120 切 / ≤ 120 连 → cluster 边界在 9-11:30 (gap=150 切) 和 15-17:30 (gap=150 切)
- 结果: `[9:00] / [11:30, 13:00, 15:00] / [17:30]` → **events_today = 3**, 不是 v0.1 spec 写的 4-5
- 簇间 gap: [2.5h, 2.5h], max_inter_cluster_gap_h = 2.5h < 4h
- day_span = 8.5h ≤ 12h

**v0.1 设计的问题** (Ace 提出): events_today=3 命中老 T1.5 medium, 但跟 T1.3 (events=2 紧邻 = strong) 出现降档断层 — "多 1 张照片反而降档", 不符合"事件越多信号越足" 直觉.

**v0.2 修复**: T1.5 升 strong, 跟 T1.3 平齐. 范式调整:
- **单/少事件紧邻 = strong**: T1.1/T1.2 (单事件), T1.3 (2 紧邻), T1.5 (3-5 紧邻)
- **多事件过密 = medium**: T1.6 (≥6 紧邻, 单日内 6+ event 已经是充实活动但密集到"无主题感")
- **任何 ≥4h 断裂 = weak**: T1.7 (跨事件破裂)
- **任何跨度 > 12h = weak**: T1.8 (拉得太开)

**验证西湖一日游 (新 grid)**:
- events_today = 3 ∈ [3, 5] ✓
- 所有 gap < 4h ✓ (最大 2.5h)
- day_span = 8.5h ≤ 12h ✓
- 命中 T1.5 → **strong** ✓ (升档)

**边界验证**:
- 早餐+午餐 (events=2, gap=4h) → T1.4 medium (≥4h 切)
- 早餐+午餐+下午茶 (events=3 紧邻, span=6.5h) → T1.5 strong ✓ (跟 T1.3 一致)
- 早午晚 (events=3, gap=4h/6h) → T1.7 weak ✓ (有 ≥4h 断)
- 城市充实 1 日游 8 个 stop (events=8, span=10h, gap 都 < 2h) → T1.6 medium (≥6 过密)
- 跨 14h 的延续活动 (events=3, span=14h, gap 都<4h) → T1.8 weak (跨度过长)

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

### 4.7 · 边界保护带 (v0.2 缓解问题③ gap 阈值脆性)

**问题**: §2.2 把硬边界从"绝对时刻 (11:00)" 搬到"相对 gap (120min)", 仍存在边界脆性 — gap=119min 同 cluster, gap=121min 不同 cluster, 临界 case 输出不稳定. **band 输出固定不能改 (Ace 明示), 只能在落痕层缓解.**

**解法**: 引入"边界保护带" (`near_eps_band`):
- 定义边界保护带 = `[eps_minutes - δ, eps_minutes + δ]`, 默认 δ = 20 分钟 → 100-140 分钟
- 切分逻辑**不变** (仍按 gap ≤ eps 连 / > eps 切), band 输出**不变**
- 但若任一相邻 gap 落入保护带, **rule_fired 后缀加 `+near_eps_boundary`** (落痕信号)
- 上游 LLM / 真值表读到这个 flag 可决定是否复审

**与 ADR-0010 落痕范式同构**:
- ADR-0010 把不稳定信号 (transit 速度临界 / 形状临界) 通过 rule_fired 后缀传给 LLM
- 本 spec 把 gap 临界通过同样机制传给 LLM
- **band 直出, 不稳定性走落痕**, 算法层保持确定

**触发示例**:

| 场景 | gap | 切分 | events | rule_fired |
|---|---|---|---|---|
| 午餐 1.5h | 90min | 连 | 1 | T1.1 (无保护带) |
| 午餐 + 下午茶 2.5h | 150min | 切 | 2 | T1.3 (无保护带, gap=150 > 140) |
| 边界 case 2h gap | 120min | 连 (≤ eps) | 1 (合并) | T1.2**+near_eps_boundary** |
| 边界 case 1h50 gap | 110min | 连 | 1 | T1.2**+near_eps_boundary** |
| 边界 case 2h10 gap | 130min | 切 | 2 | T1.3**+near_eps_boundary** |

**关键性质**:
1. **band 是确定的** (按 eps=120 硬切, 不引入随机性 / 重叠区)
2. **临界 case 留痕** — LLM 看到 `+near_eps_boundary` 可在 prompt 里决定 "本次时间信号不充分, 多依赖主载体"
3. **统计意义** — 真实数据里 `+near_eps_boundary` 占比可用来调 eps_minutes 初值 (若 > 15% case 触发, 说明 eps 选偏中位 gap, 应调离实际数据峰值)

**δ 的选取**:
- δ = 20min = eps 的 ~17%, 是经验初值
- v0.2 真实数据后可调到 δ ∈ [15, 30]
- δ 过大 → 大量 case 触发, flag 失去信号意义
- δ 过小 → 真正边界 case 漏标

**未解决的部分** (诚实承认):
- 该机制**不消除** band 在临界 case 的不稳定性, 只让上游知情
- 真要完全消除 gap 脆性需要软聚类 (例如多 eps 投票 / kernel density), 但成本远高于当前问题严重度
- v0.2 决定**接受边界存在, 落痕兜底**, 跟 ADR-0010 transit 临界处理范式一致

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
    """TimeFeature.shape 枚举 (类比 ADR-0010 LocationShape).

    v0.2: T1 grid 重排, 加 DENSE_CHAIN / MULTI_EVENTS_BREAK / OVERSTRETCHED_CHAIN.
    """
    SINGLE_EVENT_DENSE = "single_event_dense"            # T1.1
    SINGLE_EVENT_EXTENDED = "single_event_extended"      # T1.2
    ADJACENT_EVENTS = "adjacent_events"                  # T1.3
    DISTANT_EVENTS = "distant_events"                    # T1.4
    EXTENDED_CHAIN = "extended_chain"                    # T1.5 (v0.2 升 strong)
    DENSE_CHAIN = "dense_chain"                          # T1.6 (v0.2 新增, ≥6 过密)
    MULTI_EVENTS_BREAK = "multi_events_break"            # T1.7 (v0.2 重命名, ≥4h 断裂)
    OVERSTRETCHED_CHAIN = "overstretched_chain"          # T1.8 (v0.2 新增, span>12h)
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

    # ─── 时间几何特征 (v0.2 拆字段澄清问题⑦) ────────────────
    total_span_hours: float
    max_inter_cluster_gap_h: float | None                   # 同日内最大 cluster 间 gap, 跨日 None
    max_intra_cluster_span_h: float | None                  # cluster 内最大 span (≤ eps), 落痕用
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

### Case 2 · 西湖一日游 5 张 (T1.5, v0.2 strong)

```
timestamps = [9:00, 11:30, 13:00, 15:00, 17:30]
K_days = 1
gap (min): [150, 90, 120, 150]
切分 (eps=120): 切 / 连 / 连 / 切 → cluster: [9:00] / [11:30, 13:00, 15:00] / [17:30]
events_today = 3 (修 v0.1 spec 错算"4-5")
max_inter_cluster_gap_h = 2.5h < 4h
day_span = 8.5h ≤ 12h
events ∈ [3, 5] ✓
→ T1.5 extended_chain
band = strong, shape = extended_chain
rule_fired = "T1.5"
(注: 150min gap > 140min, 不进 §4.7 边界保护带; 若有 gap=130 case 会落痕 +near_eps_boundary)
```

### Case 3 · 早午晚 3 事件 (T1.7)

```
timestamps = [9:00, 13:00, 19:00]
K_days = 1, events_today = 3, gap = [4h, 6h]
gap = [240, 360] min, 都 > 120 → 3 个独立 cluster
max_inter_cluster_gap_h = 6h ≥ 4h → 命中 T1.7 (有≥4h 断裂)
band = weak, shape = multi_events_break
rule_fired = "T1.7"
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
max_inter_cluster_gap_h = 6h ≥ 4h → T1.4
band = medium, shape = distant_events
```

### Case 12 · 午餐 + 下午紧接 (T1.3)

```
timestamps = [12:30, 14:30]
K_days = 1, events_today = 2 (gap = 2h > 120min? 边界)
若 gap = 2.5h → events_today = 2, max_inter_cluster_gap_h = 2.5h < 4h → T1.3
band = strong, shape = adjacent_events
```

---

## 八、与 ADR-0010 location 的对称性 (诚实对照, v0.2 修问题①)

⚠ 早版 spec 暗示 time 跟 location "算法范式同构", 实际**只在"按阈值连通"层面相似**, 在密度 / 抗噪 / 形状识别上**不是同构**. 此表区分了真同构 (✓) 与表面相似 (~).

| 字段 | ADR-0010 location | 本 spec (将来 ADR-0011) time | 同构? |
|---|---|---|---|
| 算法本质 | DBSCAN (密度核心点 + 扩展) | gap 阈值链式切分 (single linkage) | **~** 表面相似 |
| 主聚类信号 | K_outer (eps=1500m, min_samples=2) | events_per_day (eps=120min, min_samples=1) | ~ |
| 抗噪 | 是 (离群点不入 cluster) | 否 (单点也成 cluster) | **不同构** |
| 退化形状识别 | K_inner (eps=500m 重定向) | 不需要 (1D 无形状) | N/A |
| 内部形状校正 | A2 (PCA OBB + τ) | T1.5 extended_chain (多事件 gap 小) | ~ |
| 边界缓解 | transit 临界 / shape 临界 落痕 | §4.7 near_eps_boundary 落痕 | ✓ 落痕范式同构 |
| 高频降档 | ADR-0006 location 高频 (外部 hook) | 无 (Ace 2026-05-15 明示) | N/A |
| 路径分流主键 | K_outer (0/1/2/≥3) | K_days (0/1/2/≥3) | ✓ 范式同构 |
| 输出 | LocationFeature.band + shape + rule_fired | TimeFeature.band + shape + rule_fired | ✓ 直出 band 同构 |
| 跟另一维度关系 | 独立 (不读 time) | 独立 (不读 location) — **断 ADR-0007 location→time 依赖链** | ✓ |

**结论**: time 跟 location 在**输出范式 / 路径分流 / 落痕机制** 三层同构, 但在**底层聚类算法** 上是两套东西. 写 ADR-0011 时不要复用 ADR-0010 的 "DBSCAN" 措辞.

---

## 九、核心不变性

1. **band 4 档终值**, 真值表 28 条直读, 不再 score → 阈值
2. **K_days 是路径分流主键**: 0/1/2/≥3 分流
3. **0-6 点归"前一日 night"**, 决定 K_days 计数, 跟自然作息对齐
4. **时间链式切分 eps=120min** (非 DBSCAN, v0.2 澄清), 不再用等距时段标签 (morning/midday/...)
5. **K_days ≥ 3 默认不进 strong 档** (Ace 明示, 跨长日太宽松收紧)
6. **跨夜连续判定 (T2.1) 用 12h 阈值** — 用户合理睡眠周期
7. **旅游档独立于 location.context** — 不依赖 ADR-0010 删除的字段
8. **fallback 不动 band, 落痕 confidence** — 跟 ADR-0010 落痕范式对齐
9. **time 维度独立于 location 维度** — 断单向依赖链
10. **rule_fired 必填** — 落痕命中规则 + 修饰 (例: "T3.1+k_days_uncertain", "T1.5+near_eps_boundary")
11. **T1 grid 无降档断层** (v0.2 新): events 增多不导致 strong→medium 倒挂, 升 medium 阈值在 ≥6 (过密) 或 ≥4h 断裂 / span>12h
12. **gap 临界 case 强制按 ≤/> eps 硬切, 落痕 +near_eps_boundary** (v0.2 新, §4.7): band 由算法直出, 不稳定性走 rule_fired 给 LLM

---

## 十、配置 (新增 `config/path_b_time.yaml`)

```yaml
path_b_time:

  # ─── 时间链式切分 (gap-based segmentation, v0.2 改名, 非 DBSCAN) ──
  chain_segmentation:
    eps_minutes: 120              # 相邻 gap > eps 切, ≤ eps 连 (经验初值)
    # min_samples 字段移除 — 早版误用 DBSCAN 术语, 实际固定单点也成 cluster

  # ─── 边界保护带 (v0.2 新, §4.7) ─────────────────────────
  near_eps_band:
    delta_minutes: 20             # eps ± δ 内 gap 触发 +near_eps_boundary 落痕
                                  # band 不动, 落痕给上游 LLM 复审

  # ─── 自然日归属 ─────────────────────────────────────────
  natural_day:
    dawn_cutoff_hour: 6           # 0-6 点归"前一日 night"

  # ─── 跨夜连接 ───────────────────────────────────────────
  overnight:
    max_gap_hours: 12             # day1 末 → day2 首 gap < 12h 视为连续

  # ─── T1 单日网格 (v0.2: T1.5 升 strong, 加 T1.6/T1.7/T1.8) ──
  t1_grid:
    single_event_dense_max_h: 2   # T1.1 day_span ≤ 2h
    adjacent_gap_max_h: 4         # T1.3 / T1.5 内部 gap < 4h
    extended_chain_max_span_h: 12 # T1.5 / T1.6 day_span ≤ 12h
    extended_chain_events_max: 5  # T1.5 events ∈ [3, 5], > 5 走 T1.6 medium
    dense_chain_events_min: 6     # T1.6 events ≥ 6 (单日过密)

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

### OQ-22b · T1.5 extended_chain 边界 (v0.2 已采纳新方案, 留 OQ 跟踪)
- **场景**: events ∈ [3, 5] + 所有 gap < 4h + span ≤ 12h
- **v0.2 决议**: T1.5 = **strong** (修问题④ T1.3/T1.5 断层)
- **回滚条件**:
  - v0.2 真实数据上 T1.5 误判率 > 30% (人工 review "连续多事件" 实际不该 strong) → 回 medium
  - 或 events∈[3,5] 区间有明显语义分裂 (例如 3 紧邻 = strong / 5 紧邻 = medium) → 拆 T1.5a/T1.5b
- **依赖**: v0.2 真实数据标注

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

### OQ-22g · 凌晨归属 + overnight chain 双重逻辑冗余 (问题⑤)
- **场景**: §2.3 "0-6 归前日" + §4.6 "12h 跨夜 chain" 两套机制都处理"睡眠跨日 case"
  - Case 8 ([03:00, 09:00]): 归前日 → K_days=2; 然后 overnight chain 12h 内 → has_overnight_chain=True → T2.1 strong
  - 实际是一段连续 6h 活动, 直觉应 K_days=1 走 T1
  - 当前 band 终值正确 (strong), 但 K_days 字段语义错乱 (落痕 K_days=2)
- **候选**:
  - (a) 删自然日归属, 只保留 overnight chain — 简化, 但 Case 8 直接 K_days=1, day_span=6h, 命中 T1.2 strong, ✓
  - (b) 删 overnight chain, 只保留归属 — 凌晨归属后 K_days=2 还得救回, 不通
  - (c) 保留两套但落痕标 `+merged_overnight` 避免下游误读 K_days
- **v0.2 spec 暂留**: 保留两套 + 标记落痕 (方案 c); 真实数据观察 ADR-0011 实施期间是否触发频繁; **若 v0.2 数据上 dawn-cross 占比 < 2%, 转方案 a 简化**
- **回滚条件**: dawn-cross case 占比 > 10% 且 K_days 字段被下游误用 → 转方案 a

### OQ-22h · 时区 / 夏令时未处理 (问题⑥)
- **场景**: spec 12 个 Case 默认 "single timezone home_city"
  - 跨时区旅行 (北京→纽约, 时差 13h): timestamp 是 UTC 还是 local?
  - 北京 22:00 飞 (UTC 14:00) → 落地纽约 23:00 local (UTC 04:00 次日, 北京 12:00 次日)
  - 自然日归属 (0-6 归前日) 用拍照地 local 还是 UTC?
- **v0.2 spec 假设**: `L1Output.captured_at` **已规整为拍摄地 local time** (上游 L1 / EXIF 责任)
  - L1 字段 `captured_at` (datetime) 默认 naive, 时区视为拍摄地本地
  - 跨时区旅行时, 每张照片各自的 local time 用于 K_days 计数 (按时间戳数值, 不补偿时差)
  - 后果: 跨时区旅行可能 K_days 比"真实物理日" 多/少 1, 接受为已知边界
- **依赖**: ADR-0011 实施时在 docs/17 § 假设段显式落痕该约定
- **完成条件**: v0.2 EXIF 真接入时验证 captured_at 字段是否带 tz; 带 tz 则规整 / 不带 tz 则按拍摄地 local 处理
- **风险**: 国内用户跨时区旅行 < 5% case, v0.1 demo 可暂缓

### OQ-22i · `max_inter_cluster_gap_h` vs `max_intra_cluster_span_h` 字段拆分 (问题⑦)
- **场景**: v0.1 spec 单字段 `max_inter_event_gap_h` 同时承担"cluster 间 gap" 与 T1.5"相邻事件 gap < 4h" 判断, 语义二义
- **v0.2 spec 已修**: 拆成两个字段
  - `max_inter_cluster_gap_h`: cluster 与 cluster 之间最大 gap (T1.3/T1.5/T1.7 判定用), 跨日 None
  - `max_intra_cluster_span_h`: 单 cluster 内最大 span, 永远 ≤ eps_minutes/60, 落痕诊断用
- **回滚条件**: 无, 这是命名修复, 不影响算法
- **实施提醒**: ADR-0011 代码层严格按拆字段实施, 避免回落 v0.1 二义

### OQ-22j · T2.3 "单日 events ≥ 3 一律 weak" 误伤跨日游 (问题⑧)
- **场景**: K_days=2 + 某日 events ≥ 3 一律 weak (T2.3)
  - 例: day1 早 9 + 午 13 + 晚 19 + day2 早 10 → day1 events=3, T2.3 weak
  - 但这可能是充实 day1 + day2 继续, 强信号被压制
- **候选**:
  - (a) 保留 T2.3 weak — 简化, 接受误伤 (现 spec)
  - (b) 拆分: 仅 day1+day2 都 ≥ 3 events 才 weak; 一日 ≥ 3 一日 ≤ 2 → medium
  - (c) 引入 cross-day 综合判定 (跨日总 events + 是否有 overnight chain)
- **v0.2 spec 暂留方案 a**: 跨日游充实场景由主载体 (theme/event/location) 承担, time amplifier 信号稳一点
- **回滚条件**: v0.2 真实数据上"day1≥3 events + day2 少量" 类 case 漏判率 > 25% → 转方案 b

---

## 十二、与 docs/07 §3.2.2 老设计的边界对照 (体感对齐)

| 场景 | 老 (docs/07 §3.2.2 + v0.1 代码) | 新 (本 spec) | 改变 |
|---|---|---|---|
| 午餐 4 张 (12:00-12:30) | 1.00 strong | T1.1 strong | ✓ 一致 |
| 西湖一日游 5 张 (9-17:30) | 0.70 medium (12h 段) | T1.5 **strong** (v0.2 升) | **新更强**: 修 T1.3/T1.5 断层 |
| 早午晚 3 事件 (9/13/19) | 0.70 medium (旧未实现双峰检测) | T1.7 weak (v0.2 重命名) | **新好**: 修了双峰漏判 |
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

1. **核心范式切换** (§二): 从 "span + 双峰" → "K_days + 时间链式切分 (gap segmentation)", 你认可吗?
2. **eps_minutes = 120 + δ=20 边界保护带** (§2.2 + §4.7): 默认 120 + 边界 100-140 落痕 `+near_eps_boundary` 给 LLM, OK?
3. **T1.5 升 strong** (§4.5, v0.2 修问题④): 西湖游 events=3 走 T1.5 strong; 跟 T1.3 (events=2 strong) 平齐, 修降档断层. OK?
4. **T1.6/T1.7/T1.8 grid 拆分** (§4.2, v0.2): T1.6 ≥6 events 过密 medium / T1.7 ≥4h 断裂 weak / T1.8 span>12h weak. 拆分合理吗?
5. **T3 收紧到最高 medium** (§4.4): K_days ≥ 3 即使每日有照片也不进 strong. 这是 Ace 已表态的方向, 这里再确认.
6. **0-6 点归"前一日 night"** (§2.3): 决定 K_days 计数, 你认可吗?
7. **跨夜连续 12h 阈值** (§4.6): 用户合理睡眠 + 早起, 12h 偏宽还是偏严?
8. **删除字段清单** (§六): is_bimodal / is_travel_relaxed / median_gap_hours / all_fallback / time_span_hours 重命名, 都按 Ace "老字段直接删" 偏好处理. OK 吗?
9. **fallback 不动 band 改 confidence** (§五): 跟 ADR-0010 范式对齐. OK?
10. **配置文件命名 `path_b_time.yaml`** (§十): 跟 `path_b_location.yaml` 对齐. OK?

审完确认 → 我走 12 步实施 (写 ADR-0011 + 后续 docs/src/config/tests).

---

## 十五、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-15 | 初版, 基于 ADR-0010 落地后 location/time 解耦的需求设计 |
| v0.2 (draft) | 2026-05-18 | 修问题① 算法误称 (DBSCAN→链式切分, §2.2/§八 全面修订); 修问题④ T1.3/T1.5 strong 断层 (T1.5 升 strong, T1.6/T1.7/T1.8 重排 grid); 加 §4.7 边界保护带 (`+near_eps_boundary` rule_fired 落痕, 缓解问题③ gap 阈值脆性); TimeShape 加 DENSE_CHAIN / MULTI_EVENTS_BREAK / OVERSTRETCHED_CHAIN; config 加 `near_eps_band.delta_minutes`; 不变性加 §9 11/12 两条 |
| v0.2 (修订) | 2026-05-18 | 加 §三 字段拆 max_inter_cluster_gap_h / max_intra_cluster_span_h 修问题⑦; 加 §十一 OQ-22g (凌晨归属 vs overnight 冗余, 问题⑤) / OQ-22h (时区/夏令时未处理, 问题⑥) / OQ-22i (字段拆分修问题⑦) / OQ-22j (T2.3 误伤跨日游, 问题⑧); §六 TimeFeature 字段拆分同步 |
