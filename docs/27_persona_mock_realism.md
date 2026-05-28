# 27 · Persona Mock 数据真实多样性规范

> 算法依据: [ADR-0021](../decisions/0021-llm-label-realism.md).

---

## 一、GPS 跨度参考表

中国 30-40°N (杭州/上海/苏州):

| 场所类型 | 真实跨度 | 经纬度差 |
|---|---|---|
| 同一物体 (一盆花) | < 10m | < 0.0001° |
| 同一房间 (餐厅) | 10-30m | 0.0001-0.0003° |
| **小区花园** | 200-400m | 0.002-0.004° |
| 城市公园 (拙政园) | 500m-1km | 0.005-0.01° |
| 大景区 (西湖整圈) | 3-10km | 0.03-0.1° |
| 城内多景点 (北京一日游) | 30-50km | 0.3-0.5° |
| 跨城 (上海-杭州) | 150km+ | 1°+ |

⚠ 不能把 0.001° 当作"小漂移", 那是 **100m** (一个庭院).

---

## 二、event_hint 混标分布 (LLM 真实行为)

L1 event_hint 单值枚举, 但 LLM 在边界场景应混标.

### 典型分布参考

| 场景 | 张数 | 主导 event | 次要 event |
|---|---|---|---|
| 公园散步 | 8 | outing 50% | daily_record 30%, gathering 15%, sports 5% |
| 聚餐 | 4 | meal 80% | gathering 20% (合影) |
| 生日 | 6 | celebration 70% | meal 20%, gathering 10% |
| 旅游 1 日 | 10 | outing 60% | meal 10%, daily_record 10%, performance 10%, gathering 10% |
| 居家做饭 | 5 | daily_record 60% | meal 40% |
| 演唱会 | 25 | performance 90% | gathering 10% |
| 健身房 | 5 | sports 80% | daily_record 20% |
| 工作 | 6 | work 70% | meal 15%, gathering 15% |

### 不应该的模式

❌ 8 张都同一个 event (除非高纯度活动: 全程吃饭 / 全程打篮球)
❌ 边界活动 (散步/休息/聊天) 全部归 daily_record 单值

---

## 三、theme 颗粒度多样

同活动 8 张应包含:

| 类型 | 例子 |
|---|---|
| 抽象大词 | lake / garden / temple |
| 具体物象 | ripple / lotus / pavilion |
| 视角差异 | closeup / panorama / detail |
| 时段差异 | morning / dusk / sunset |
| 主体切换 | flower / friend / sky |

**8 张不应都用同 3 个词** 如 `[garden, walk, morning]`.

---

## 四、不变量

1. 同一物体多张 → GPS 几乎一致 (相机不动)
2. 同一房间 → GPS ≤ 30m 差
3. 公园/景点散步 → GPS 200-1km 散布
4. event_hint 边界场景必须 2-3 个混标
5. theme 8+ 张同活动至少 5+ unique 词

---

## 五、关联

- [ADR-0021](../decisions/0021-llm-label-realism.md)
- [ADR-0019](../decisions/0019-persona-based-e2e-testing.md)
- 跑批量修复: `tests/personas/_fix_realism.py` (一次性脚本)

---

## 六、ADR-0025 扩展: theme_tags 禁地名 + 地标 (2026-05-21)

theme_tags 字段是**主题/氛围/活动**, 不是地理位置. 地理信息由 location 维度 (GPS + Geocoder ADR-0016) 承载.

### 禁词类型

| 类型 | 例 |
|---|---|
| 城市名 | 北京 / 上海 / 杭州 / 苏州 / Beijing / Shanghai 等 |
| 国家/省份名 | 中国 / 浙江 / China / Zhejiang |
| 地标专名 | 故宫 / 长城 / 外滩 / 西湖 / 东方明珠 / 鸟巢 / 雷峰塔 / gugong / great_wall / bund / xihu / pearl_tower / bird_nest / leifeng |
| 景区/公园专名 | 豫园 / 新天地 / 田子坊 / 陆家嘴 / yuyuan_garden / xintiandi / tianzifang / lujiazui |
| 含地名组合词 | west_lake_hangzhou / pearl_tower_distant 等 |

### 允许 (抽象化)

| 类型 | 例 |
|---|---|
| 自然景观 | lake / waterfront / lakeside / river / mountain / forest / beach / pond |
| 城市景观 | skyline / skyscraper / colonial_buildings / cobblestone_street / alley |
| 建筑类型 | palace / temple / pagoda / ancient_architecture / stadium |
| 场景属性 | promenade / plaza / cafe_district / financial_district |
| 氛围/质感 | morning_haze / golden_hour / neon_lights / serene / vibrant |

### 影响范围

- L1 prompt 加禁地名指令 (扩 ADR-0021)
- persona 数据清洗 (~40 处 li/zhang 替换, 抽象化 mapping 见 ADR-0025 §2.4)
- 自动检测 (可选): `tests/personas/_check_geographic_taint.py`

⚠ narrative (个人理解) + group (测试 metadata) + yaml 注释 **不动**, 只清 `theme: [...]` 和 `subjects: [...]` 字段.

详见 [ADR-0025](../decisions/0025-theme-tags-no-geographic.md).
