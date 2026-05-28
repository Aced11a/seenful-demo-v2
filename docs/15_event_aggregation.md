# 15 · Event 字段扩充 + 路径 A event 维度聚合规范

> 路径 A (动态生长) **event 维度** 的小集级指纹生成 + 1 张新照片匹配算法.
> 算法依据: [ADR-0009](../decisions/0009-event-aggregation.md), 原始 spec 见 [archive/specs/Event_Field_And_Aggregation_Spec.md](../archive/specs/Event_Field_And_Aggregation_Spec.md).
> 仅覆盖路径 A. 路径 B event 维度走 [ADR-0012](../decisions/0012-path-b-event-aggregation.md) (`src/features/event.py::build_event_feature`, 复用 path A `aggregate_event`).

---

## 一、L1 字段: event_hint

### 1.1 · 10 个枚举值

| 枚举 | 中文 | 核心判别信号 |
|---|---|---|
| `meal` | 用餐 | 餐桌/食物/餐具 |
| `outing` | 户外活动 | 户外/景区/街景/城市探索 |
| `gathering` | 聚会 | 多人合影/聚集, 无餐桌无仪式感 |
| `celebration` | 仪式感时刻 | 蛋糕/蜡烛/横幅/捧花/节日装饰/盛装 |
| `performance` | 观赏文化活动 | 舞台/银幕/观众席/演出/赛事/展览 (作为**观众**) |
| `sports` | 运动健身 | 运动器材/运动场地/运动姿态/健身房 |
| `work` | 工作场景 | 工位/会议室/工作设备/办公环境 |
| `study` | 学习场景 | 书本/笔记/试卷/教室/自习室 |
| `daily_record` | 日常记录 | 兜底, 以上均不符合但有记录价值 |
| `unknown` | 拿不准 | L1 实在判不出 |

### 1.2 · 删除的旧枚举 (ADR-0009)

- `family_visit` — 被 `gathering` (纯聚集) + `celebration` (仪式感) 覆盖
- `festival` — 被 `celebration` 覆盖

⚠ ADR-0009 决策: **直接删除, 不留 deprecated 别名** (fixture 无实际使用)。

### 1.3 · 互斥优先级 (L1 prompt 层)

多信号同时存在时, L1 按以下优先级判定:

```
1. celebration (强符号: 蛋糕/蜡烛/横幅/婚纱) ← 覆盖性信号
2. meal                                       ← 用餐场景压倒一切
3. study / work                               ← 学习/工作的强场景信号
4. performance                                ← 舞台/银幕场景
5. sports                                     ← 运动姿态/器材
6. celebration (弱符号: 仅装饰/颜色)
7. outing                                     ← 户外活动
8. gathering                                  ← 多人聚集 (无餐桌/无仪式/无活动场景)
9. daily_record                               ← 有记录价值但都不符合
10. unknown                                   ← 实在判不出
```

⚠ **v0.1 demo 不验证 L1 prompt 行为** — fixture 是手填 JSON, prompt 互斥逻辑待真 L1 接入 (转 [OQ-020 §20e](./12_open_questions.md#oq-020-event-枚举与聚合调优))。

### 1.4 · 关键边界

#### meal
- ✓ 任何有食物 + 餐具的场景 (独自/家人/朋友均可)
- ✓ 户外野餐 / 餐厅 / 家里厨房, 在吃饭就是 meal
- ✗ 没在吃, 只是合影 → 看其他信号

#### outing
- ✓ 任何外出活动 (单日/跨日不区分, L1 单张无法判)
- ✓ 景区 / 街景 / 城市探索 / 户外散步
- ✗ 出门买菜 / 外卖 → daily_record

跨日识别交给 L2 通过时间跨度推断, **不在 event_hint 层区分**。

#### gathering
- ✓ 多人聚集场景, **且无更具体信号**
- ✗ 餐桌合影 → meal; 健身房合影 → sports; 演唱会自拍 → performance; 生日合照 → celebration

#### celebration
- ✓ 节日 (春节 / 中秋 / 圣诞 / 万圣)
- ✓ 个人庆祝 (生日 / 纪念日 / 婚礼 / 求婚 / 订婚 / 毕业)
- ✓ 关键信号: 蛋糕、蜡烛、横幅、捧花、特定颜色 (红/白婚纱)、盛装
- ✗ 没仪式感符号的普通聚会 → gathering

#### performance
- ✓ 用户作为**观众**: 演唱会 / 话剧 / 电影院 / 体育赛事 / 展览
- ✓ 关键信号: 舞台 / 银幕 / 观众席 / 票根
- ✗ 用户作为**表演者** → 看具体内容, 通常归 sports 或 daily_record

#### sports
- ✓ 健身 / 瑜伽 / 跑步 / 游泳 / 球类 (作为**参与者**)
- ✗ 在体育场看球 → performance

#### work / study
- ✓ 明确场景信号 (工位 / 会议室 / 书本 / 试卷)
- ✓ 居家办公 (笔记本 + 文档界面) → work
- ✓ 自习室 / 图书馆 / 教室 → study
- ✗ 仅有电脑但场景模糊 → daily_record

#### daily_record (兜底)
- ✓ 静物 / 小物记录 (一杯咖啡 / 一朵花 / 天空)
- ✓ 长期状态记录 (养宠物日常 / 装修期 / 植物生长)
- ✓ 通勤路上 / 独自走路 / 随手记录
- ✓ 自拍 (无具体场景)
- ✗ 任何能归到具体枚举的场景

#### unknown
- ✓ 信息量极少 (纯黑 / 全白 / 严重模糊)
- ✓ 纯文字截图 / 表情包 / 网图
- ✓ L1 拿不准时

---

## 二、小集级 EventAggregation

### 2.1 · 数据结构

```python
class EventAggregation(BaseModel):
    primary: str | None              # 主导事件 (占比 ≥ primary_threshold)
    secondary: list[str]              # 次主导 (占比 ≥ secondary_threshold)
    tertiary: list[str]               # 历史稀少 (count ≥ tertiary_min_count, 不达 secondary)
    distribution: dict[str, int]      # {event: count} 完整分布
    total_events: int                 # 剔除 unknown 后的总计

class MiniAlbumFingerprint(BaseModel):
    # ... 其他字段
    event_agg: EventAggregation
    event_aggregated_at: datetime | None
```

⚠ ADR-0009 字段变更:
- **删** `dominant_event_hint: str` (字面单值, 类比 ADR-0008 删 `dominant_theme`)
- **加** `event_agg` + `event_aggregated_at`

### 2.2 · 匹配输出: `EventMatchResult`

```python
class EventMatchResult(BaseModel):
    band: Literal["strong", "medium", "weak", "none"]
    matched_tier: Literal["primary", "secondary", "tertiary", "none"] | None
    diagnostics: dict[str, Any]      # new_event / primary / secondary / tertiary
    reason: str = ""                  # "unknown_event" / "empty_aggregation" / ""
```

---

## 三、聚合算法 (build_event_aggregation)

### 3.1 · 流程

```
所有照片的 event_hint
    ↓
Step 1: 过滤 unknown → hints
    ↓
Step 2: Counter(hints) → distribution
    ↓
Step 3: 三级分层
  · primary = sorted_events[0] 占比 ≥ primary_threshold (0.6) 吗? 该 event : None
  · 剩余 event 按占比/count 分配:
      - 占比 ≥ secondary_threshold (0.2) → secondary
      - count ≥ tertiary_min_count (1) → tertiary
    ↓
EventAggregation(primary, secondary, tertiary, distribution, total_events)
```

### 3.2 · 边界

- **空 hints** (全 unknown 或无照片) → `EventAggregation(primary=None, secondary=[], tertiary=[], distribution={}, total_events=0)`
- **完全分散** (无 event 达 primary_threshold) → `primary=None`, 多个 event 进 `secondary`
- **单 event 主导稀疏** (work×8 + meal×1) → primary=work, secondary=[], tertiary=[meal]

---

## 四、匹配算法 (match_event · 1 张新照片 vs 老相册 event_agg)

### 4.1 · 核心规则 (四档)

```python
def match_event(new_event, event_agg) -> EventMatchResult:
    if new_event == "unknown":     return band="none"
    if new_event == primary:       return band="strong",  matched_tier="primary"
    if new_event in secondary:     return band="medium",  matched_tier="secondary"
    if new_event in tertiary:      return band="weak",    matched_tier="tertiary"
    return band="none"
```

### 4.2 · 核心设计

1. **完全枚举驱动** — 不用 embedding (event 是封闭 10 枚举, 离散语义直接 == 比较)
2. **三级分层把二元判断扩展为四档** — strong (主导) / medium (次主导) / weak (历史稀少) / none
3. **unknown 一律 none** — 不参与匹配
4. **指纹实时重算** — 每次加照片重算, 性能 ~1ms

### 4.3 · 最简可执行 demo (stdlib only)

> 用途: 给协作者快速验证语义理解, 无任何外部依赖, 直接 `python demo.py`.
> 真实代码: `src/mini_album/event_aggregation.py` (Pydantic 契约 + 配置加载, 阈值走 `config/event_aggregation.yaml`).

```python
"""L2.5 event 评档最简 demo · 三级分层聚合 + 四档单张匹配."""
from collections import Counter

# 阈值 (实际代码走 config/event_aggregation.yaml, demo 简化硬编码)
PRIMARY_THRESHOLD = 0.6
SECONDARY_THRESHOLD = 0.2
TERTIARY_MIN_COUNT = 1


def aggregate(hints: list[str]) -> dict:
    """老相册成员 event_hint 列表 → {primary, secondary, tertiary}."""
    valid = [h for h in hints if h != "unknown"]
    if not valid:
        return {"primary": None, "secondary": [], "tertiary": []}

    counter = Counter(valid)
    total = len(valid)
    primary, secondary, tertiary = None, [], []

    top_event, top_count = counter.most_common(1)[0]
    if top_count / total >= PRIMARY_THRESHOLD:
        primary = top_event

    for event, count in counter.most_common():
        if event == primary:
            continue
        if count / total >= SECONDARY_THRESHOLD:
            secondary.append(event)
        elif count >= TERTIARY_MIN_COUNT:
            tertiary.append(event)

    return {"primary": primary, "secondary": secondary, "tertiary": tertiary}


def match(new_event: str, agg: dict) -> str:
    """单张新照片 event_hint vs 老相册 agg → strong / medium / weak / none."""
    if new_event == "unknown":
        return "none"
    if not agg["primary"] and not agg["secondary"] and not agg["tertiary"]:
        return "none"
    if new_event == agg["primary"]:
        return "strong"
    if new_event in agg["secondary"]:
        return "medium"
    if new_event in agg["tertiary"]:
        return "weak"
    return "none"


if __name__ == "__main__":
    # Case 1 · 杭州一日游 (强主导)
    hints = ["outing"] * 6 + ["meal"] * 1 + ["unknown"] * 1
    agg = aggregate(hints)
    print(agg)
    # {'primary': 'outing', 'secondary': [], 'tertiary': ['meal']}

    print(match("outing", agg))       # strong  (primary 命中)
    print(match("meal", agg))          # weak    (tertiary 命中)
    print(match("celebration", agg))   # none

    # Case 2 · 主次混合无主导 (0.6 阈值生效)
    hints = ["outing"] * 4 + ["meal"] * 3
    agg = aggregate(hints)
    print(agg)
    # {'primary': None, 'secondary': ['outing', 'meal'], 'tertiary': []}

    print(match("outing", agg))        # medium
    print(match("study", agg))         # none
```

---

## 五、Case 验证 (spec §六)

### Case 1 · 强主导 (杭州一日游)

```
hints = ["outing"]×6 + ["meal"]×1 + ["unknown"]×1
total = 7 (剔除 unknown)
counter = {outing: 6, meal: 1}

primary = outing (6/7 = 86% ≥ 60%) ✓
secondary = []
tertiary = [meal] (count=1 ≥ 1) ✓

匹配:
  new="outing"  → strong (primary 命中)
  new="meal"    → weak   (tertiary 命中)
  new="celebration" → none
```

### Case 2 · 主次混合无主导 (0.6 阈值生效)

```
hints = ["outing"]×4 + ["meal"]×3
counter = {outing: 4, meal: 3}

primary = None (outing 57% < 60%) ✗
secondary = [outing, meal] (都 ≥ 20%)
tertiary = []

匹配:
  new="outing" → medium (secondary)
  new="meal"   → medium (secondary)
  new="study"  → none
```

**关键**: 0.6 阈值避免"刚过半就强匹配"误判。

### Case 2b · 主导明显 (0.6 通过)

```
hints = ["outing"]×6 + ["meal"]×3
counter = {outing: 6, meal: 3}

primary = outing (67% ≥ 60%) ✓
secondary = [meal] (33% ≥ 20%)
tertiary = []

匹配:
  new="outing" → strong
  new="meal"   → medium
  new="study"  → none
```

### Case 3 · 完全分散

```
hints = ["outing"]×2 + ["meal"]×2 + ["gathering"]×2 + ["celebration"]×2

primary = None (最高 25% < 60%)
secondary = [outing, meal, gathering, celebration] (都 ≥ 20%)
tertiary = []

匹配:
  new="outing" → medium
  new="work"   → none
```

### Case 4 · 全 unknown 小集

```
hints = []  (剔除 unknown 后空)

EventAggregation(primary=None, secondary=[], tertiary=[], distribution={}, total_events=0)

匹配: 任何 event → none (reason="empty_aggregation")
```

### Case 5 · 单 event 主导但稀疏

```
hints = ["work"]×8 + ["meal"]×1

primary = work (89% ≥ 60%) ✓
secondary = []
tertiary = [meal] (count=1 ≥ 1)

匹配:
  new="work" → strong
  new="meal" → weak
```

---

## 六、增量更新策略

新照片加入小集后, **全量重算 event 指纹** (~1ms, 代价极低):

```python
def on_photo_added(album, new_photo, cfg):
    album.member_photo_ids.append(new_photo.photo_id)
    members = load_l1(album.member_photo_ids)
    album.event_agg = aggregate_event(members, cfg)
    album.event_aggregated_at = datetime.now()
```

---

## 七、性能预算

```
聚合 (30 张照片):
  · Counter 统计: <1ms
  · 三级分层: <1ms
  总: <2ms

匹配 (新照片 vs 小集):
  · 查 primary/secondary/tertiary: <0.1ms
  总: <1ms
```

event 维度延迟极低, 纯枚举 + 计数器, 无 embedding 调用。

---

## 八、配置 (`config/event_aggregation.yaml`)

```yaml
event_aggregation:
  primary_threshold: 0.6      # 占比 ≥ 60% 为主
  secondary_threshold: 0.2    # 占比 ≥ 20% 为次
  tertiary_min_count: 1       # 至少出现 1 次为三级
```

调优转 [OQ-020 §20a-c](./12_open_questions.md#oq-020-event-枚举与聚合调优).

---

## 九、核心不变性

1. **event_hint 是单值枚举**, 每张照片 1 个值
2. **10 个枚举值固定**, L1 无法选时归 unknown, 不自创新值
3. **互斥优先级裁决多事件叠加场景**, celebration 强符号是覆盖性信号
4. **小集级用三级分层** (primary/secondary/tertiary) 把二元判断扩展为四档
5. **匹配不持久化, 实时计算**, 新照片加入即触发重算
6. **跨日识别交给 L2**, event_hint 不区分单日/跨日
7. **仅升级路径 A 范围**; path B `build_event_feature` 复用 `aggregate_event` (ADR-0012)

---

## 十、关联

**ADR**:
- [ADR-0009](../decisions/0009-event-aggregation.md) (本算法决策依据)
- [ADR-0008](../decisions/0008-theme-semantic-clustering.md) (类比的路径 A theme 算法, 同 1-vs-aggregated 模式)

**docs**:
- [docs/10_mini_album_schema.md](./10_mini_album_schema.md) §四 (指纹总览引用本文档)
- [docs/04_truth_table_growth.md](./04_truth_table_growth.md) event 维度
- [docs/02_data_contracts.md](./02_data_contracts.md) (EventAggregation / EventMatchResult / MiniAlbumFingerprint)
- [docs/07_dimension_thresholds.md](./07_dimension_thresholds.md) (event_score path B, 不动)

**代码**:
- `src/contracts/l1_output.py::EventHint` (10 枚举, ADR-0009 扩展)
- `src/contracts/event.py::EventAggregation / EventMatchResult`
- `src/contracts/growth.py::MiniAlbumFingerprint.event_agg`
- `src/mini_album/event_aggregation.py` (算法)
- `src/features/growth_features.py::_compute_event_match` (调用方)
- `src/policy/truth_table_growth.py::compute_growth_bands` (event 直出 band)

**OQ**:
- [OQ-020](./12_open_questions.md#oq-020-event-枚举与聚合调优) (枚举调优 + 阈值调优 + L1 prompt 互斥验证)

**原始 spec** (归档):
- [archive/specs/Event_Field_And_Aggregation_Spec.md](../archive/specs/Event_Field_And_Aggregation_Spec.md) v0.2 (2026-05-12)
