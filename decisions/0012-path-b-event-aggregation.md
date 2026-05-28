# ADR-0012 · 路径 B event 维度: event primary_share + activity 二次门槛

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-18 |
| 决策人 | Ace (产品/增长) — 与 Claude Code 联合设计, 经 4 轮迭代 (event 单独 strong 范式 → activity 字段考虑 → A3 真值表约束 → Y/A/2/3 拍板) |
| 影响范围 | 重写 `src/features/event.py` + 升级 `src/contracts/features.py::EventFeature + EventShape` + 新增 `config/path_b_event.yaml` + 新增 `docs/18_path_b_event.md`; 改 `docs/{00,01,02,07,11,12}`; 新增 fixtures + 单测 + 重生 golden |
| 相关文档 | `docs/18_path_b_event.md` (本算法主规范), `Path_B_Event_Aggregation_Spec.md` v0.2 (设计来源, 实施完后归档 `archive/specs/`) |
| 关联 OQ | **关闭** OQ-009 §9b (path B event 严格度); **新增** [OQ-023](../docs/12_open_questions.md#oq-023-adr-0012-接受边界的真实数据验证) 跟踪 6 子问题 (23a~f: band_thresholds / activity 2/3 / 兜底范围 / 兜底上限 / sports 子类接受 / B 系列兼容性) |
| 关联 ADR | supersede 老 `src/features/event.py` (26 行严格全员一致); **复用** [ADR-0009](./0009-event-aggregation.md) `aggregate_event` 函数 (path A path B 共享 distribution 算法); 输出范式同 [ADR-0010](./0010-path-b-location-dbch-pca-shape.md) / [ADR-0011](./0011-time-natural-day-event-clustering.md) (直出 band + rule_fired + shape) |

---

## 1 · 背景

### 1.1 · 路径 B event 现状

`src/features/event.py` 当前 26 行算法 (严格全员一致):
- 全部 hint 相同 → 0.9 (strong)
- 全部 unknown + activity 全一致 → 0.6 (medium)
- 否则 → 0.2 (none)

### 1.2 · 失败模式

**1 张离群即降到 0.2 (none)** 导致大量误判:

| 场景 | 老 score | 应该 | 失败根因 |
|---|---|---|---|
| 4 张 meal + 1 张 gathering | 0.2 → none | medium | 1 张离群把 strong 拉到 none |
| 3 张 meal + 2 张 gathering | 0.2 → none | medium | 多数派应识别 |
| 2 张 meal + 0 张其他 | 0.9 → strong | strong | OK (没问题) |
| 2 张 meal + 1 张 gathering + 2 张 unknown | 0.2 → none | weak | 有信号但弱 |
| 5 张 outing + activity=[walk × 2, sightseeing × 2, gathering × 1] | 0.9 → strong | medium | event 一致但 activity 散, 不该 strong |

### 1.3 · A3 真值表的约束

真值表 A3: `event = 强 → bounds=[medium, strong], type=event` — **event 单独 strong 直接出 type="event" 小集**, 不需要其他维度配合.

→ event=strong 判定必须严格. 若像 ADR-0010/0011 的 path B 那样"primary_share ≥ 0.8 = strong" 过松, 4:1 一致就单独成集, 1 张离群也成集. **Ace 2026-05-18 明示否决 v0.1 spec 的 0.8 阈值**.

### 1.4 · 引发本 ADR 的具体问题

OQ-009 §9b ("event 严格全员一致 → 多数派 ② 推荐方案 ~30min 改动") 长期未关闭. 现在时机成熟:
- ADR-0010 / ADR-0011 已落地 path B 2/7 维直出 band
- ADR-0009 `aggregate_event` 已落地, 算法范式 + 代码可复用
- A3 真值表约束要求 event=strong 严格 → 必须设计**双重门槛** (event + activity)

---

## 2 · 决策

### 2.1 · 算法范式

**路径 B event 不再算 score, 直出 4 档 band**, 真值表 28 条结构不变, 只读 `EventFeature.band`.

**核心算法**: 复用 ADR-0009 `aggregate_event(photos)` 算 distribution → event_primary_share (基于 N) → **+ activity_primary_share 二次门槛** → 8 行 grid 判定 band.

### 2.2 · 三阶段判定流水线

```
photos
   │
   ▼
ADR-0009 aggregate_event(photos)  ← 共享 distribution 算法
   │
   ▼
event_primary_share = agg.primary_count / N  (基于总数 N)
activity_primary_share = activity_counter.most_common(1) / N  (排除 unknown)
   │
   ├─ event_share = 1.0
   │   ├─ activity_share ≥ 2/3 → E.1 strong  (unanimous_event_activity)
   │   └─ activity_share < 2/3 → E.2 medium  (unanimous_event_mixed_activity)
   │
   ├─ 0.8 ≤ event_share < 1.0 → E.3 medium  (dominant_event)
   ├─ 0.6 ≤ event_share < 0.8 → E.4 medium  (mixed_event)
   ├─ 0.4 ≤ event_share < 0.6 → E.5 weak    (scattered_event)
   ├─ event_share < 0.4 + N_valid ≥ 2 → E.6 weak  (fragmented_event)
   │
   └─ N_valid ≤ 1 (event 缺位)
       ├─ activity_share ≥ 2/3 → E.7 weak  (activity_fallback)
       └─ activity_share < 2/3 → E.8 none  (no_event_signal)
```

### 2.3 · 核心变量定义

| 变量 | 定义 |
|---|---|
| **N** | 总照片数 |
| **N_valid** | event_hint != "unknown" 数量 |
| **agg** | ADR-0009 `aggregate_event(photos)` 输出 (EventAggregation) |
| **event_primary_share** | agg.distribution[agg.primary] / **N** (基于总数, 不是 N_valid) |
| **activity_primary_share** | activity 多数派 count / **N** (排除 unknown 算多数派) |

⚠ 都基于 **N (总数)** 不是 N_valid — unknown 是衰减因子, 不是无效因子. 避免 [unknown × 3, meal × 2] 误判 strong (N_valid 小但 share=1.0).

### 2.4 · 8 行 grid (E.1~E.8)

| # | event_share | activity_share | N_valid | band | shape |
|---|---|---|---|---|---|
| E.1 | **= 1.0** | **≥ 2/3** | — | **strong** | unanimous_event_activity |
| E.2 | = 1.0 | < 2/3 | — | **medium** | unanimous_event_mixed_activity |
| E.3 | 0.8 ≤ < 1.0 | — | — | **medium** | dominant_event |
| E.4 | 0.6 ≤ < 0.8 | — | — | **medium** | mixed_event |
| E.5 | 0.4 ≤ < 0.6 | — | — | **weak** | scattered_event |
| E.6 | < 0.4 | — | ≥ 2 | **weak** | fragmented_event |
| E.7 | — (兜底) | ≥ 2/3 | ≤ 1 | **weak** | activity_fallback |
| E.8 | — (兜底) | < 2/3 | ≤ 1 | **none** | no_event_signal |

### 2.5 · A3 风险接受边界 (方案 a)

**篮球/足球场景** ([sports × 5] + [activity=gathering × 5], 内容混了篮球+足球):
- L1 activity 7 枚举不区分 sports 子类
- E.1 双重门槛仍判 strong → A3 触发 → 单独成集
- Ace 2026-05-18 明示**接受**: sports 大类成集语义合理 ("运动相册")
- 子类区分由 theme 维度 + 真值表 B 系列承担 (theme=弱 通过 B 系列降档)
- v0.2 真实数据验证 OQ-023e

### 2.6 · 配置

```yaml
# config/path_b_event.yaml
path_b_event:
  band_thresholds:
    strong_share: 1.0
    medium_dominant_share: 0.8
    medium_mixed_share: 0.6
    weak_scattered_share: 0.4

  activity_gate:
    min_consensus_ratio: 0.667     # 2/3 (Ace 2026-05-18 选定)

  activity_fallback:
    min_consensus_ratio: 0.667     # 共享 2/3
    max_valid_event_for_fallback: 1
    fallback_band: "weak"
```

---

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| **A. 严格全员一致 (v0.1 现状)** | 1 张离群即降 0.2 none, 失败模式见 §1.2 |
| **B. primary_share 单门槛 ≥ 0.8 = strong (v0.1 spec 初版)** | A3 让 event-only 单独成集, 4:1 也 strong 太松, Ace 2026-05-18 明示否决 |
| **C. event + activity 映射融合 (ACTIVITY_TO_EVENT mapping)** | Ace 否决: activity 信息不应污染 event distribution; 映射经验值不稳 |
| **D. 加权融合 (0.7 × event + 0.3 × activity)** | 双标无主载体, 加权值难调 |
| **E. event + activity 取 max** | 同 D, 主载体不清, activity 反客为主时怪 |
| **F. 扩 activity 枚举 (加 basketball/football/...)** | 工程大 (改 L1 prompt + 字段类型 + fixture); 开放分类闭枚举永远列不全 |
| **G. 本 ADR — event 优先 + activity 二次门槛 (Y/A/2/3)** | 修了 §1.2 5 类失败 + 收紧 strong 双重门槛 + 接受 sports 大类边界 + 跟 ADR-0010/0011 输出范式对齐 + 复用 ADR-0009 aggregate_event |

---

## 4 · 影响范围

### 4.1 · 契约变更

**修改** `src/contracts/features.py::EventFeature` (新增, 老 v0.1 只有 event_score 字段):

```python
class EventShape(str, Enum):
    UNANIMOUS_EVENT_ACTIVITY = "unanimous_event_activity"           # E.1
    UNANIMOUS_EVENT_MIXED_ACTIVITY = "unanimous_event_mixed_activity"  # E.2
    DOMINANT_EVENT = "dominant_event"                               # E.3
    MIXED_EVENT = "mixed_event"                                     # E.4
    SCATTERED_EVENT = "scattered_event"                             # E.5
    FRAGMENTED_EVENT = "fragmented_event"                           # E.6
    ACTIVITY_FALLBACK = "activity_fallback"                         # E.7
    NO_EVENT_SIGNAL = "no_event_signal"                             # E.8


class EventFeature(BaseModel):
    band: BandLevel
    rule_fired: str
    score: float                                  # 派生展示

    total_photos: int
    valid_event_count: int
    unknown_share: float
    primary_event: str | None
    primary_count: int
    event_primary_share: float                    # 基于 N
    secondary_events: list[str]
    tertiary_events: list[str]
    distinct_events: int

    activity_primary: str | None
    activity_primary_count: int
    activity_primary_share: float                 # 基于 N
    used_activity_gate: bool                      # E.1 二次门槛
    used_activity_fallback: bool                  # E.7 兜底

    shape: EventShape
    primary_signal: str = "event_hint"
```

**修改** `FeaturePackage.event` 字段新增 (类比 location / time):
```python
class FeaturePackage(BaseModel):
    ...
    location: LocationFeature | None    # ADR-0010
    time: TimeFeature | None             # ADR-0011
    event: EventFeature | None           # ADR-0012 新增
    theme: ThemeFeature | None
```

⚠ **Ace 偏好: 老方案直接删, 不留 deprecated**. 老的 `compute_event_score(photos) -> float` 删除, assemble.py 改调 `build_event_feature(photos) -> EventFeature`.

### 4.2 · 新增算法模块

**重写** `src/features/event.py`:
- `build_event_feature(photos, cfg) -> EventFeature` 高层入口
- 内部:
  - `_compute_activity_distribution(photos)` 算 activity counter (排除 unknown)
  - `_compute_grid(event_share, activity_share, n_valid, cfg)` E.1~E.8 grid 判定
  - 派生 `_band_to_score(band)` (跟 ADR-0010/0011 一致)

复用:
- `from src.mini_album.event_aggregation import aggregate_event` (ADR-0009)
- 配置 `config/event_aggregation.yaml::event_aggregation` (primary_threshold=0.6 等)

纯 Python, 零额外依赖.

### 4.3 · 配置

新增 `config/path_b_event.yaml` (见 §2.6).

`config/dimension_thresholds.yaml::dimension_bands.event` 段**保留**为派生 score 计算用 (EventFeature.score 仍输出), 但**不参与 band 判定** — band 来自 `path_b_event.yaml`.

`config/event_aggregation.yaml::event_aggregation` (primary_threshold=0.6 等) **共享给 path A 和 path B**, ADR-0012 不动它.

### 4.4 · 调用方

**修改** `src/features/assemble.py`:
- 调 `build_event_feature(photos)` 替代 `compute_event_score(photos)`
- `FeaturePackage.event` 填新 EventFeature
- `FeaturePackage.event_score` 由 `feature.score` 派生

**修改** `src/policy/bands.py`:
- `Bands.event` 直接读 `EventFeature.band`, 不再走 `score → 阈值`
- 兜底: `features.event is None` 回退老 `_classify(event_score, db["event"])`

### 4.5 · 测试

**新建** `tests/unit/test_features_event.py`:
- E.1~E.8 每行 ≥ 1 正例 + 1 边界
- Spec §五 14 个 Case 全跑
- activity 二次门槛 (event=1.0 + 2/3 临界 边界)
- activity 兜底 (N_valid ≤ 1 边界)
- 边界: N=0 / N=1 / 全 unknown 全 fallback

**重生** golden:
- `tests/scenarios/*` 涉及 event 的 golden 重跑 `scripts/generate_golden.py`
- 预期 ~ 5-10 个 golden 需重生
- 人工 diff 审 event 字段从 score-driven 到 band-driven 的变化

---

## 5 · 决策回滚条件

| 回滚条件 | 动作 |
|---|---|
| v0.2 真实数据上 E.1 strong 误判率 > 20% (人工 review "不该单独成集") | 提高 activity_gate.min_consensus_ratio 到 0.75 或 0.8 |
| sports 子类 (篮球/足球) "希望细分" 用户占比 > 30% | 触发 ADR-0012-补丁 (改 A3 / 扩 activity 枚举 / event 维度引入 main_subjects) |
| medium 大量出现导致 B 系列命中率激增 → 用户感觉 album 太碎 | 收紧 medium 阈值 (medium_dominant 提到 0.85, medium_mixed 提到 0.7) |
| activity 兜底 (E.7) 误判率高 (event 全 unknown 但 activity 一致 ≠ 同活动) | 收紧 activity_fallback.fallback_band 到 "none" |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| **OQ-009 §9b (event 严格度)** | 待决, "推荐多数派 ②" | **关闭** — ADR-0012 实现的不是"多数派 ②", 是"event 优先 + activity 二次门槛", 但解决了同一痛点 |
| OQ-009 §9c (people 严格度) | 待决 | 不变 — 本 ADR 不动 people |
| **OQ-023 (新增)** | — | ADR-0012 接受边界 v0.2 真实数据验证, 6 子问题 23a~f (band_thresholds / activity 2/3 / 兜底范围 / 兜底上限 / sports 子类接受 / B 系列兼容性) |
| docs/07 §3.2.4 (event_score 旧描述) | 已跟代码一致 (严格全员一致) | **关闭漂移** — 描述指向 docs/18, 旧设计 supersede |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完 (Step 1)
2. ⏳ `docs/18_path_b_event.md` 完整算法规范 (Step 2)
3. ⏳ `config/path_b_event.yaml` 新建 (Step 3)
4. ⏳ `src/contracts/features.py::EventFeature` 升级 + `EventShape` 枚举 + `__init__.py` 导出 (Step 4-5)
5. ⏳ `src/features/event.py` 重写 + `assemble.py` 适配 + `bands.py` 直读 (Step 6-8)
6. ⏳ `docs/{02,07,00,01,11,12}` 同步 (Step 9)
7. ⏳ Fixtures + 单测 + golden 重生 + grep 自检 (Step 10-11)
8. ⏳ Spec 归档 — `Path_B_Event_Aggregation_Spec.md` v0.2 → `archive/specs/` + `archive/specs/README.md` 加索引 + `docs/00_index.md` 已归档段更新 (Step 12)
9. ⏳ v0.2: OQ-023 真实数据验证 (尤其 23e sports 子类边界)
