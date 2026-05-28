# ADR-0021 · LLM 标签真实多样性原则 (Persona Mock 数据)

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-20 |
| 决策人 | Ace — 戳出 A2 (周期性散步 8 张) GPS 完全一致 + event 全 outing 失真 |
| 影响范围 | 改 `tests/personas/{laoqi_zhang,laoli_youke,xiaowang}.yaml` 所有 group 的 GPS 散布 / event 混标 / theme 颗粒度; 新增 `docs/27_persona_mock_realism.md` |
| 相关文档 | `docs/27_persona_mock_realism.md`; 跟 ADR-0019 v0.2~v0.7 联动 |
| 关联 OQ | OQ-030 (Persona 真实数据扩展) |
| 关联 ADR | 不 supersede 任何; 是 ADR-0019 persona 设计的**真实多样性补充原则** |

---

## 1 · 背景

ADR-0019 v0.2 强调"每张照片 unique 标签", 但 Ace 2026-05-20 抽查 A2 (周期性散步 8 张) 戳出:
1. **GPS 8 张完全一样** `[31.302, 120.593]` — 不真实 (公园不同位置应有 100-400m 漂移)
2. **event 8 张里 7 张 `outing`** — LLM 在边界场景应有混标 (休息→daily_record, 聊天→gathering)
3. **theme 太一致** — 每张应有不同侧重 (颗粒度 + 视角 + 时间)

这违反 ADR-0019 v0.2 "用户行为驱动 + 真实多样性" 初衷.

---

## 2 · 真实尺度参考表 (LLM mock 数据设计准则)

### 2.1 GPS 跨度对照

经纬度差 ↔ 真实距离 (在中国 30-40°N):
- **0.0001° ≈ 10m** (一栋楼 / 一个亭子内)
- **0.001° ≈ 100m** (一个小庭院)
- **0.005° ≈ 500m** (一个公园角)
- **0.01° ≈ 1km** (一个街区 / 小景区)
- **0.05° ≈ 5km** (城市核心区)
- **0.5° ≈ 50km** (跨城)
- **5° ≈ 500km** (跨省)

| 场所类型 | 真实跨度 | 应有 GPS 差 |
|---|---|---|
| **同一物体** (一盆花 / 一桌菜) | < 10m | < 0.0001° |
| **同一房间内** (餐厅 / 客厅) | 10-30m | 0.0001-0.0003° |
| **小区花园** | 200-400m | 0.002-0.004° |
| **城市公园** (玉皇山 / 拙政园) | 500m-1km | 0.005-0.01° |
| **大景区** (西湖整圈) | 3-10km | 0.03-0.1° |
| **城内多景点** (北京一日游) | 30-50km | 0.3-0.5° |
| **跨城** (上海-杭州) | 150km+ | 1°+ |

⚠ **不能想当然写 0.001 当作小漂移** — 那是 100m, 同一个公园都说不清.

### 2.2 event_hint 混标原则

L1 LLM 输出 event_hint 是单值枚举 (10 个), 真实场景中:
- **同一活动多次** LLM 应在 2-3 个相关 event 间纠结
- **行为模糊场景** (休息/散步/聊天) 应混标
- **不应** 8 张照片 8 个完全一致的 event_hint (除非高纯度活动如纯吃饭)

典型混标分布:
- **公园散步** 8 张: outing 50% / daily_record 30% / gathering 15% / sports 5% (跑步/打太极)
- **聚餐** 4 张: meal 80% / gathering 20% (合影时段)
- **生日** 6 张: celebration 70% / meal 20% / gathering 10%
- **旅游** 10 张: outing 60% / meal 10% / daily_record 10% / performance 10% / gathering 10%
- **居家做饭** 5 张: daily_record 60% / meal 40%

### 2.3 theme 颗粒度差异

同一活动不同照片, theme 标签应有:
- **不同抽象级** (粗: lake / 细: ripple, splash)
- **不同视角** (近距 closeup / 全景 panorama)
- **不同时段** (morning, dusk, evening)
- **不同要素** (subject 切换: 人 / 物 / 景)

避免: 8 张都用相同 3 个词 `[garden, walk, morning]`.

---

## 3 · 修复行动 (本次)

按 §2 真实尺度表批量修改 3 persona 所有 group:

### 3.1 张奶奶 (laoqi_zhang)

| Group | 现状 | 修复 |
|---|---|---|
| balcony_flowers (12 张) | 都同 GPS / 都 daily_record | GPS 不变 (阳台 ≤10m 合理) / theme 颗粒度增多 |
| weekly_park_walk (8 张) | 8 张同 GPS / 7 张 outing | **GPS 散 200m × 300m + event 混 outing/daily/gathering** |
| 其他 group | 各自审视 | 按 §2 表 |

### 3.2 李叔叔 + 小王

类似全审视, 重点修旅游/景区类 GPS 跨度.

### 3.3 校准阈值

GPS 真实化后, 单测/scenarios 可能因 location band 变化重新校准.

---

## 4 · 不变量

1. 同一物体多张 → GPS 几乎一致 (相机不动)
2. 同一房间 → GPS ≤ 30m 差
3. 公园/景点散步 → GPS 200-1km 散布
4. event_hint 边界场景必须有 2-3 个混标
5. theme 8+ 张同活动至少含 5+ unique 词 (不全相同)

---

## 5 · 关联

- [ADR-0019](./0019-persona-based-e2e-testing.md) v0.2~v0.7 (persona 设计基础)
- [docs/27_persona_mock_realism.md](../docs/27_persona_mock_realism.md) (本规范的实施细则)
- OQ-030 (持续扩展 persona)
