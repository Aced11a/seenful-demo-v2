# Event 字段扩充与小集聚合规范

> **版本**: v0.2
> **日期**: 2026-05-12
> **适用**: 登场识图知意 PRD v1.1：3.4.1 小集event字段方案

---

## 一、背景

### 1.1 event_hint 当前定义

L1 当前的 `event_hint` 字段在 PRD §3.1.7 定义为 6 个枚举:

```
meal | outing | family_visit | festival | daily_record | unknown
```

**约 30-50% 的真实事件被挤到 daily_record**,导致 event 维度信号失真。

### 1.2 为什么 event_hint 必须是封闭枚举

**关键判断**: 根据L1输出 event_hint 仅有一个tag，产品语义是"粗粒度分类",不是"细粒度描述"。细节(主体、场景、氛围)由 main_subjects / scene_type / theme_tags 等字段承担,**event 只做粗分类**。


### 1.3 本规范要做的事

1. **L1 字段**:把 event_hint 扩充为 10 个枚举值,加明确边界 + 互斥优先级
2. **小集聚合**:基于扩充后的 event_hint,定义小集级 event 指纹的聚合与匹配算法

**核心约束**:
- event_hint 是**单值枚举**,每张照片 L1 只输出 1 个值
- 所有枚举值必须能从**单张照片**判定,无法判定 → unknown
- 多事件叠加场景 (如"朋友万圣节餐厅聚会") 通过**互斥优先级**裁决

---

## 二、枚举值定义

10 个值 (9 个事件 + 1 个 unknown):

| 枚举值 | 中文名 | 核心判别信号 |
|---|---|---|
| `meal` | 用餐 | 餐桌、食物、餐具 |
| `outing` | 户外活动 | 户外、景区、街景、城市探索 |
| `gathering` | 聚会 | 多人合影/聚集,无餐桌无仪式感 |
| `celebration` | 仪式感时刻 | 蛋糕、蜡烛、横幅、捧花、节日装饰、盛装 |
| `performance` | 观赏文化活动 | 舞台、银幕、观众席、演出/电影/赛事/展览场景 |
| `sports` | 运动健身 | 运动器材、运动场地、运动姿态、健身房 |
| `work` | 工作场景 | 工位、会议室、工作设备、办公环境 |
| `study` | 学习场景 | 书本、笔记、试卷、教室、自习室 |
| `daily_record` | 日常记录 | 兜底,以上均不符合但有记录价值 |
| `unknown` | 拿不准 | L1 实在判不出 |

---

## 三、互斥优先级规则

多个信号同时存在时,L1 按以下优先级判定 (高到低):

```
1. celebration (强符号: 蛋糕/蜡烛/横幅/婚纱) ← 覆盖性信号
2. meal                                       ← 用餐场景压倒一切
3. study / work                               ← 学习/工作的强场景信号
4. performance                                ← 舞台/银幕场景
5. sports                                     ← 运动姿态/器材
6. celebration (弱符号: 仅装饰/颜色)
7. outing                                     ← 户外活动
8. gathering                                  ← 多人聚集 (无餐桌/无仪式/无具体活动场景)
9. daily_record                               ← 有记录价值但都不符合
10. unknown                                   ← 实在判不出
```

## 四、关键边界说明

### 4.1 meal 的边界

- ✓ 任何有食物 + 餐具的场景,无论独自/家人/朋友
- ✓ 户外野餐、餐厅、家里厨房,只要在吃饭就是 meal
- ✗ 没在吃,只是合影 → 看其他信号

### 4.2 outing 的边界

- ✓ 任何外出活动 (单日/跨日不区分,因 L1 单张无法判跨日)
- ✓ 景区、街景、城市探索、户外散步
- ✗ 出门买菜、外卖 → daily_record (没有"游玩"性质)

**注**: 跨日识别交给 L2 通过照片时间跨度推断,**不在 event_hint 层区分**。

### 4.3 gathering 的边界

- ✓ 多人聚集场景,**且无更具体信号**
- ✗ 餐桌上的合影 → meal
- ✗ 健身房合影 → sports
- ✗ 演唱会自拍 → performance
- ✗ 生日合照 → celebration

**gathering 是"剥离掉所有具体活动后的纯聚集"**。

### 4.4 celebration 的边界

- ✓ 节日 (春节/中秋/圣诞/万圣)
- ✓ 个人庆祝 (生日/纪念日/婚礼/求婚/订婚/毕业)
- ✓ 关键信号: 蛋糕、蜡烛、横幅、捧花、特定颜色 (红/白婚纱)、盛装
- ✗ 没有仪式感符号的普通聚会 → gathering

### 4.5 performance 的边界

- ✓ 用户作为**观众**的场景: 演唱会/话剧/电影院/体育赛事/展览
- ✓ 关键信号: 舞台、银幕、观众席、票根
- ✗ 用户作为**表演者**的场景 → 看具体内容,通常归 sports (运动表演) 或 daily_record

### 4.6 sports 的边界

- ✓ 健身/瑜伽/跑步/游泳/球类运动
- ✓ 用户作为参与者,不是观众
- ✗ 在体育场看球 → performance

### 4.7 work / study 的边界

- ✓ 明确的工作/学习场景信号 (工位/会议室/书本/试卷)
- ✓ 居家办公 (笔记本 + 文档界面) → work
- ✓ 自习室/图书馆/教室 → study
- ✗ 仅有"电脑"但场景模糊 → daily_record

### 4.8 daily_record 的边界

- ✓ 静物/小物记录 (一杯咖啡/一朵花/天空/桌面)
- ✓ 长期状态记录 (养宠物日常/装修期/植物生长)
- ✓ 通勤路上/独自走路/随手记录
- ✓ 自拍 (无具体场景)
- ✗ 任何能归到具体枚举的场景

### 4.9 unknown 的边界

- ✓ 信息量极少 (纯黑/全白/严重模糊)
- ✓ 纯文字截图、表情包、网图
- ✓ L1 拿不准时

---

## 五、小集级 event 聚合

### 5.1 数据结构

```python
@dataclass
class EventAggregation:
    primary: Optional[str]              # 主导事件
    secondary: list[str]                # 次主导事件 (可多个)
    tertiary: list[str]                 # 历史出现过但稀少
    distribution: dict[str, int]        # 完整分布 (诊断用)
    total_events: int                   # 总事件数 (剔除 unknown 后)


class MiniAlbum:
    # ... 原有字段
    event_agg: EventAggregation
    event_aggregated_at: datetime
```

### 5.2 聚合算法

```python
from collections import Counter

def aggregate_event(
    members: list[L1Output],
    config
) -> EventAggregation:
    """
    输入: 小集成员照片的 L1 输出
    输出: 三级 event 分布 (primary / secondary / tertiary)
    """
    hints = [
        p.semantic_facts.event_hint
        for p in members
        if p.semantic_facts.event_hint != "unknown"
    ]
    
    if not hints:
        return EventAggregation(
            primary=None,
            secondary=[],
            tertiary=[],
            distribution={},
            total_events=0
        )
    
    counter = Counter(hints)
    total = len(hints)
    sorted_events = counter.most_common()
    
    primary = None
    secondary = []
    tertiary = []
    
    # 主 event: 占比 ≥ primary_threshold
    if sorted_events[0][1] / total >= config.primary_threshold:
        primary = sorted_events[0][0]
    
    # 次/三级 event 分层
    for event, count in sorted_events:
        if event == primary:
            continue
        ratio = count / total
        if ratio >= config.secondary_threshold:
            secondary.append(event)
        elif count >= config.tertiary_min_count:
            tertiary.append(event)
    
    return EventAggregation(
        primary=primary,
        secondary=secondary,
        tertiary=tertiary,
        distribution=dict(counter),
        total_events=total
    )
```

### 5.3 匹配函数

```python
def match_event(new_event: str, event_agg: EventAggregation) -> str:
    """
    新照片 event vs 小集 event 分布 → 四档
    
    strong  = 命中主导 (primary)
    medium  = 命中次主导 (secondary)
    weak    = 命中历史稀少 (tertiary)
    none    = 完全不沾边
    """
    if new_event == "unknown":
        return "none"
    
    if event_agg.primary and new_event == event_agg.primary:
        return "strong"
    
    if new_event in event_agg.secondary:
        return "medium"
    
    if new_event in event_agg.tertiary:
        return "weak"
    
    return "none"
```

### 5.4 配置

```yaml
event_aggregation:
  primary_threshold: 0.6      # 占比 ≥ 60% 为主 (严格,避免"刚过半"误判)
  secondary_threshold: 0.2    # 占比 ≥ 20% 为次
  tertiary_min_count: 1       # 至少出现 1 次为三级
```

**为什么 primary_threshold 设为 0.6 而不是 0.5**:
0.6 是初值,P0.5 通过场景测试可调到 0.55 或 0.65。

---

## 六、匹配 Case 验证

### Case 1 · 强主导 (杭州一日游,主线 outing)

```
hints = ["outing"]×6 + ["meal"]×1 + ["unknown"]×1
total = 7 (剔除 unknown)
counter = {outing: 6, meal: 1}

primary: outing (6/7 = 86% ≥ 60%) ✓
secondary: 无 (meal 1/7 = 14% < 20%)
tertiary: meal (count=1 ≥ 1) ✓

event_agg = {
  primary: "outing",
  secondary: [],
  tertiary: ["meal"],
  distribution: {outing: 6, meal: 1}
}
```

匹配:
- 新 event="outing" → **strong** ✓
- 新 event="meal" → **weak** ✓ (历史出现)
- 新 event="celebration" → **none** ✓

### Case 2 · 主次混合,但无明显主导 (新阈值 0.6 触发)

```
hints = ["outing"]×4 + ["meal"]×3
counter = {outing: 4, meal: 3}

primary: outing 57% < 60% → None ✗ (新阈值生效)
secondary: outing (57% ≥ 20%) + meal (43% ≥ 20%)
tertiary: []

event_agg = {
  primary: None,
  secondary: ["outing", "meal"],
  tertiary: [],
  distribution: {outing: 4, meal: 3}
}
```

匹配:
- 新 event="outing" → **medium** ✓ (混合小集,任一已有事件都中等关联)
- 新 event="meal" → **medium** ✓
- 新 event="study" → **none** ✓

**关键观察**: 在 0.5 阈值下,outing 会被错误认定为 primary,新照片来命中即 strong;在 0.6 阈值下,小集被正确识别为混合性质,新照片走 secondary 路径返回 medium,**避免了"刚过半就强匹配"的误判**。

### Case 2b · 明显主导 (新阈值 0.6 通过)

```
hints = ["outing"]×6 + ["meal"]×3
counter = {outing: 6, meal: 3}

primary: outing 67% ≥ 60% → outing ✓
secondary: meal (33% ≥ 20%)
tertiary: []

event_agg = {
  primary: "outing",
  secondary: ["meal"],
  tertiary: [],
  distribution: {outing: 6, meal: 3}
}
```

匹配:
- 新 event="outing" → **strong** ✓
- 新 event="meal" → **medium** ✓
- 新 event="study" → **none** ✓

### Case 3 · 完全分散 (无主导)

```
hints = ["outing"]×2 + ["meal"]×2 + ["gathering"]×2 + ["celebration"]×2
counter = {outing: 2, meal: 2, gathering: 2, celebration: 2}

primary: None (最高 25% < 60%)
secondary: 所有 ≥ 20% (25% > 20%)
  = [outing, meal, gathering, celebration]
tertiary: []

event_agg = {
  primary: None,
  secondary: [outing, meal, gathering, celebration],
  tertiary: [],
  distribution: {...}
}
```

匹配:
- 新 event="outing" → **medium** ✓ (混合小集任一已有事件都中等关联)
- 新 event="work" → **none** ✓

### Case 4 · 全 unknown 小集

```
hints = []  (剔除 unknown 后)

event_agg = {
  primary: None,
  secondary: [],
  tertiary: [],
  distribution: {},
  total_events: 0
}
```

匹配:任何 event → **none** ✓

### Case 5 · 单 event 主导但稀疏

```
hints = ["work"]×8 + ["meal"]×1
counter = {work: 8, meal: 1}

primary: work (89% ≥ 60%) ✓
secondary: 无 (meal 11% < 20%)
tertiary: meal (count=1 ≥ 1) ✓

event_agg = {
  primary: "work",
  secondary: [],
  tertiary: ["meal"],
  distribution: {work: 8, meal: 1}
}
```

匹配:
- 新 event="work" → **strong** ✓
- 新 event="meal" → **weak** ✓

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

event 维度延迟极低,纯枚举 + 计数器,无 embedding 调用。

---

## 八、增量更新

新照片加入小集后,**全量重算 event 指纹** (代价小):

```python
def on_photo_added(album, new_photo, config):
    album.member_photo_ids.append(new_photo.photo_id)
    
    # 重新聚合
    members = load_l1(album.member_photo_ids)
    album.event_agg = aggregate_event(members, config)
    album.event_aggregated_at = datetime.now()
```

---

## 九、与现有规范的关系

| 字段 (工程规范 v1.3) | 本规范升级 |
|---|---|
| `event_hint` (照片级,6 枚举) | 🔄 扩到 10 个枚举,加边界 + 互斥优先级 |
| 小集级 event 字段 | ➕ 新增 `EventAggregation` (primary + secondary + tertiary + distribution) |
| `daily_record` | 🔄 从"垃圾桶"变成兜底,使用率预期从 30-50% 降到 10-15% |


## 十、待补 OQ

| OQ | 问题 | 优先级 |
|---|---|---|
| OQ-EV-1 | primary_threshold = 0.6 是否合理 (调到 0.55 或 0.65?) | P0.5 调优 |
| OQ-EV-2 | secondary_threshold = 0.2 是否合理 | P0.5 调优 |
| OQ-EV-3 | tertiary_min_count = 1 是否会让单次 LLM 噪点变成 weak | P0.5 调优 |
| OQ-EV-4 | L1 prompt 改造后 unknown 比例是否能控制在 10% 以内 | P0 (上线前验证) |
| OQ-EV-5 | celebration 的"强符号优先"互斥规则在 L1 上是否稳定 | P0 (测试集验证) |
| OQ-EV-6 | daily_record 实际占比是否符合预期 (10-15%) | P0 (上线后监控) |

---

## 十一、核心不变性

1. **event_hint 是单值枚举**,每张照片 1 个值
2. **10 个枚举值固定**,L1 无法选时归 unknown,不自创新值
3. **互斥优先级裁决多事件叠加场景**,celebration 强符号是覆盖性信号
4. **小集级用三级分层** (primary/secondary/tertiary) 把二元判断扩展为四档
5. **匹配不持久化,实时计算**,新照片加入即触发重算
6. **跨日识别交给 L2,event_hint 不区分单日/跨日**

---

## 十二、实施清单

L1 层:
- [ ] 更新 PRD §3.1.7,枚举从 6 改到 10
- [ ] 更新 PRD §6.2 L1 prompt,加 10 个枚举边界 + 互斥优先级 + few-shot
- [ ] L1 输出 schema 加枚举校验,非合法值自动归 daily_record
- [ ] 重跑 L1 测试集,覆盖率达标 (unknown < 10%)

L2 层:
- [ ] 实现 `EventAggregation` 数据结构
- [ ] 实现 `aggregate_event()` 函数
- [ ] 实现 `match_event()` 函数
- [ ] 添加配置项到 yaml
- [ ] 写单元测试覆盖 §六的 case + §十 OQ 涉及边界

---

*v0.2 · 2026-05-12 · 10 个枚举 + 三级分层聚合 + 互斥优先级 + 严格 primary 阈值 (0.6)*
