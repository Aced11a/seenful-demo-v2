# ADR-0009 · Event 字段扩充 + 路径 A event 维度三级分层聚合

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-14 |
| 决策 |  — 来自 `archive/specs/Event_Field_And_Aggregation_Spec.md` v0.2 (2026-05-12, 实施后归档) |
| 影响范围 | 新增 `src/contracts/event.py` + `src/mini_album/event_aggregation.py` + `config/event_aggregation.yaml` + `docs/15_event_aggregation.md`; 改 `src/contracts/l1_output.py::EventHint` (6→10 枚举) + `src/contracts/growth.py::MiniAlbumFingerprint` + `src/features/growth_features.py::_compute_event_match` + `src/policy/truth_table_growth.py::compute_growth_bands` + `tests/fixtures/albums/*.json` + `docs/{00,01,02,04,07,10,11,12}` + 根目录 5 个 md |
| 相关文档 | `docs/15_event_aggregation.md` (本算法主规范), `docs/10_mini_album_schema.md` (指纹总览引用) |
| 关联 OQ | **关闭 [OQ-008](../docs/12_open_questions.md#oq-008-小集指纹合成-mini-album-fingerprint-synthesis) §8d** (dominant_event_hint 计算); 引发 [OQ-020](../docs/12_open_questions.md#oq-020-event-枚举与聚合调优) |
| 关联 ADR | 与 [ADR-0008](./0008-theme-semantic-clustering.md) 互补 — 同样是路径 A "1 张 vs 老相册指纹"模式, 但 event 是封闭枚举不需 embedding |

---

## 1 · 背景

L1 当前 `event_hint` 字段为 6 个枚举:
```
meal | outing | family_visit | festival | daily_record | unknown
```

### 失败模式

1. **粒度不足**: 30-50% 的真实事件被挤到 `daily_record` (兜底兜成垃圾桶)
2. **重叠语义**: `family_visit` 和 `festival` 互相重叠 (家庭节日聚会判哪个?), 实际应统一为 `celebration` (仪式感) + `gathering` (纯聚集)
3. **场景盲区**: 工作 / 学习 / 运动 / 演出观赏 — 这 4 类高频场景在 6 枚举下全部归 `daily_record`
4. **小集级聚合粗暴**: `dominant_event_hint: str` 单值, 用"最高频"判定; 路径 A 匹配只有"一致 → 0.9 / 不一致 → 0.2" 二档, 中间地带 (混合相册) 无法表达

### 引发本 ADR 的具体问题

OQ-008 §8d 原推荐 v0.1 用"最高频 + tie-break 优先非 daily_record"。但**daily_record 占比 30-50% 本身就是问题** — 不应靠 tie-break 绕开, 应该治本: 扩枚举 + 三级分层聚合。

---

## 2 · 决策

### 2.1 · L1 枚举扩充 (6 → 10)

**保留**: `meal` / `outing` / `daily_record` / `unknown`
**删除**: `family_visit` / `festival` (无 fixture 实际使用, 直接删除, 类 ADR-0008 处理方式)
**新增**: `gathering` / `celebration` / `performance` / `sports` / `work` / `study`

完整 10 枚举:

| 枚举 | 核心判别信号 |
|---|---|
| `meal` | 餐桌 / 食物 / 餐具 |
| `outing` | 户外 / 景区 / 街景 / 城市探索 |
| `gathering` | 多人合影/聚集, 无餐桌无仪式感 |
| `celebration` | 蛋糕/蜡烛/横幅/捧花/节日装饰/盛装 |
| `performance` | 舞台/银幕/观众席/演出/赛事/展览 (作为**观众**) |
| `sports` | 运动器材/运动场地/运动姿态/健身房 |
| `work` | 工位/会议室/工作设备/办公环境 |
| `study` | 书本/笔记/试卷/教室/自习室 |
| `daily_record` | 兜底 (有记录价值但都不符合) |
| `unknown` | 拿不准 |

### 2.2 · 互斥优先级 (L1 prompt 层)

L1 单值判定时按以下优先级 (高到低):

```
1. celebration (强符号: 蛋糕/蜡烛/横幅/婚纱)
2. meal
3. study / work
4. performance
5. sports
6. celebration (弱符号: 仅装饰/颜色)
7. outing
8. gathering
9. daily_record
10. unknown
```

⚠ **v0.1 demo 不验证**: L1 用 fixture (手填 JSON), prompt 互斥行为待真 L1 接入时验证 — 转 [OQ-020](../docs/12_open_questions.md#oq-020-event-枚举与聚合调优) 子问题 20e。

### 2.3 · 小集级聚合 — `EventAggregation` 三级分层

```python
class EventAggregation(BaseModel):
    primary: str | None              # 主导事件 (占比 ≥ 60%)
    secondary: list[str]              # 次主导 (占比 ≥ 20%)
    tertiary: list[str]               # 历史稀少 (count ≥ 1 但不达 secondary)
    distribution: dict[str, int]      # 完整分布 {event: count}
    total_events: int                 # 总计 (剔除 unknown)
```

**MiniAlbumFingerprint 变更**:
- **删** `dominant_event_hint: str` (类比 ADR-0008 删 dominant_theme)
- **加** `event_agg: EventAggregation`
- **加** `event_aggregated_at: datetime | None`

### 2.4 · 聚合算法 (Counter + 三级分层)

```
Step 1: 过滤掉 unknown → hints
Step 2: Counter(hints) → distribution
Step 3: primary = sorted_events[0] 占比 ≥ primary_threshold (0.6) ? 该 event : None
Step 4: 剩余每个 event 按占比/count 分配:
  · 占比 ≥ secondary_threshold (0.2) → secondary
  · count ≥ tertiary_min_count (1) → tertiary
Step 5: 返回 EventAggregation
```

### 2.5 · 匹配函数 (1 张新照片 vs 老相册 event_agg)

```python
def match_event(new_event: str, event_agg: EventAggregation) -> EventMatchResult:
    if new_event == "unknown":  band = "none"
    elif new_event == event_agg.primary:  band = "strong"
    elif new_event in event_agg.secondary:  band = "medium"
    elif new_event in event_agg.tertiary:  band = "weak"
    else:  band = "none"
```

返回 `EventMatchResult` (band + matched_tier + diagnostics), 由 `compute_growth_bands` 直接消费 (类 ADR-0005 / ADR-0008 直出模式)。

### 2.6 · 仅升级路径 A (Q1 决策)

路径 B (`src/features/event.py::compute_event_score`) **不动**, 继续用 "0.9 / 0.6 / 0.2 / 0.0" 分段。

**理由**:
- spec §五 5.2/5.3 明说"新照片 vs 小集分布", 是路径 A 1-vs-aggregated 场景
- 路径 B 是"N 张照片自比", 用 EventAggregation 不合理 (没有"老相册分布"概念)
- OQ-009 §9b 在跟踪路径 B event 严格全员一致问题, 不混入本 ADR

### 2.7 · 配置

```yaml
event_aggregation:
  primary_threshold: 0.6
  secondary_threshold: 0.2
  tertiary_min_count: 1
```

调优转 [OQ-020](../docs/12_open_questions.md#oq-020-event-枚举与聚合调优) 子问题 20a-c (P0.5 真数据上线后)。

---

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| **A. 字面单值 `dominant_event_hint` (v0.1 当前)** | 二档判定 (一致/不一致), 中间地带无法表达; 混合相册被错判 |
| **B. 仅扩 L1 枚举不动聚合** | daily_record 比例降不下来 (聚合仍是单值最高频, 一张主导照片就盖过全相册) |
| **C. embedding 聚类 (类 ADR-0008)** | event 是封闭枚举 (10 个), embedding overkill; 枚举本身已是离散语义, Counter + 占比足够 |
| **D. 仅 primary + secondary 两级** | 长尾历史 event 完全丢失; spec §六 Case 1 (历史出现过 meal) 无法表达 weak 命中 |
| **E. 三级分层 + 互斥优先级 (本 ADR 采用)** | 表达力足 (4 档输出 strong/medium/weak/none); 性能极低 (~1ms); 与 ADR-0005/0008 路径 A 直出模式对齐 |

---

## 4 · 影响范围

### 契约变更

**修改** `src/contracts/l1_output.py::EventHint`:
```python
# 旧:
EventHint = Literal["meal", "outing", "family_visit", "festival", "daily_record", "unknown"]
# 新:
EventHint = Literal[
    "meal", "outing", "gathering", "celebration",
    "performance", "sports", "work", "study",
    "daily_record", "unknown",
]
```

**新增** `src/contracts/event.py`:
- `EventAggregation` (primary / secondary / tertiary / distribution / total_events)
- `EventMatchResult` (band / matched_tier / diagnostics / reason)

**修改** `src/contracts/growth.py::MiniAlbumFingerprint`:
- **删** `dominant_event_hint: str`
- **加** `event_agg: EventAggregation`
- **加** `event_aggregated_at: datetime | None`

**修改** `src/contracts/growth.py::GrowthFeatures`:
- **加** `event_match: EventMatchResult | None`

### 新增算法模块 `src/mini_album/event_aggregation.py`

纯 Python 实现, **零外部依赖**:
- `aggregate_event(members, cfg)` — spec §五 5.2
- `match_event(new_event, event_agg, cfg)` — spec §五 5.3
- `build_event_aggregation(photos, cfg)` — 高层入口

### 配置 `config/event_aggregation.yaml` (新增)

```yaml
event_aggregation:
  primary_threshold: 0.6
  secondary_threshold: 0.2
  tertiary_min_count: 1
```

### `src/features/growth_features.py::_compute_event_similarity` 重写

旧:
```python
return 0.9 if same else 0.2
```

新 (类 ADR-0005 / ADR-0008 直出 band 模式):
```python
return match_event(new.event_hint, album.event_agg, cfg)
```

返回类型从 `float` 改为 `EventMatchResult`, `compute_growth_bands` 直接读 `.band`。

### `src/policy/truth_table_growth.py::compute_growth_bands`

event 优先用 `features.event_match.band`, 缺失时 fallback 旧 score → 阈值。

### 测试

- **新建** `tests/unit/test_event_aggregation.py` (spec §六 Case 1-5 + 边界)
- **改** `tests/fixtures/albums/lakeside_album.json` (删 `dominant_event_hint`, 加 `event_agg` + `event_aggregated_at`)
- **改** `tests/unit/test_growth_features.py` (TestEventSimilarity 重写为 TestEventMatch)
- **不改** photo fixtures (现有都用 `meal/outing/daily_record`, 仍在 10 枚举集合内)
- **重生** 10 golden

---

## 5 · 决策回滚条件

| 回滚条件 | 动作 |
|---|---|
| L1 prompt 改造后 unknown 占比 > 20% (spec OQ-EV-4) | 回滚到 6 枚举 + 重训 L1 prompt |
| daily_record 占比降不下来 (仍 > 25%) | 增加更细粒度枚举或重审优先级表 |
| 路径 A 命中率因 primary_threshold=0.6 偏严下降 > 15% | 调参 (转 OQ-020 子问题 20a) |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-008 §8d (dominant_event_hint 计算) | 待决, 推荐"最高频 + tie-break 优先非 daily_record" | **被本 ADR 关闭** — 字段删除, 升级为 EventAggregation 三级分层 |
| OQ-020 (新增) | — | event 枚举与聚合调优 (含 spec §十 6 个 OQ-EV) |
| OQ-009 §9b (路径 B event 严格一致) | 仍待决 | **不变** — 本 ADR 不动路径 B |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完
2. ✅ `docs/15_event_aggregation.md` 完整算法规范
3. ✅ `docs/02/04/07/10/00/01/11/12` 同步
4. ✅ `config/event_aggregation.yaml` 新建
5. ✅ `src/contracts/event.py` 新建; `l1_output.py::EventHint` 扩 10 枚举; `growth.py` 字段调整
6. ✅ `src/mini_album/event_aggregation.py` 实现
7. ✅ `src/features/growth_features.py::_compute_event_match` + `truth_table_growth.py::compute_growth_bands` 重写
8. ✅ 单测 + fixture + golden 重生
9. ✅ spec 归档 `archive/specs/Event_Field_And_Aggregation_Spec.md`
10. ⏳ v0.2: OQ-020 真 L1 接入 + 100 case 基准 (unknown 占比验证)
11. ⏳ v0.5: OQ-020 子问题 20a-c 阈值调优
