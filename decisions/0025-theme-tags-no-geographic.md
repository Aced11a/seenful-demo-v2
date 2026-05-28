# ADR-0025 · theme_tags 禁地名 + 地标 (维度边界澄清)

**状态**: accepted
**日期**: 2026-05-21
**关联**: [ADR-0021](./0021-llm-label-realism.md) LLM 标签真实性, [ADR-0016](./0016-location-geocoder-4tier.md) Location Geocoder

---

## 一、问题

实测 persona 数据里 theme_tags **大量混入地名 + 地标建筑**:

| 词 | 出现次数 | persona |
|---|---|---|
| xihu (西湖) | **24** | 李叔 |
| pearl_tower, gugong, great_wall, bund, bird_nest | 各 2 | 李叔 |
| yuyuan_garden, xintiandi, tianzifang, lujiazui, shanghai_tower, leifeng, suzhou | 各 1 | 李叔 |
| west_lake_hangzhou, bund_shanghai, shenzhen_bay, beihai_park, yuexiu_park | 各 1 | zhang FP_* |
| beijing, guangzhou | 各 2 | zhang FP_* |

**共 23 种地名/地标词**, 主要是 li (旅游 persona).

### 为什么是 bug

1. **维度边界混淆**: 地理信息归 **location 维度** (GPS + Geocoder ADR-0016), 不该污染 theme
2. **LLM 幻觉**: 真 LLM 看普通湖照片倾向编 "西湖" / "杭州" 等热门地名 → 跨用户跨地点污染 cluster
3. **跨地同主题被拆**: "外滩" 跟 "上海" 跟 "黄浦江" 是 3 个粒度, Qwen cluster 会拆成 3 簇, 但语义都是一个地点
4. **真实数据风险**: 真 LLM 输出 50%+ 会含地名, 主题 cluster 几乎全部退化为地名 cluster

### 红线背景

CLAUDE.md 红线 #8 "L1 落库即权威" — 但 L1 prompt 必须明确字段语义边界. theme_tags 是**主题/氛围/活动**, 不是地点.

---

## 二、决策

### 2.1 · theme_tags 禁词分类

**完全禁止**:

| 类型 | 例 |
|---|---|
| 城市名 (中外) | 北京 / 上海 / 杭州 / 苏州 / 广州 / 深圳 / Beijing / Shanghai / Hangzhou / Tokyo / Paris |
| 省份名 | 浙江 / 江苏 / 广东 / Zhejiang |
| 国家名 | 中国 / 日本 / 法国 / China / Japan / France |
| 地标建筑专名 | 故宫 / 长城 / 外滩 / 西湖 / 东方明珠 / 鸟巢 / 雷峰塔 / 上海中心 / gugong / great_wall / bund / xihu / pearl_tower / bird_nest / shanghai_tower / leifeng |
| 公园/景区专名 | 豫园 / 新天地 / 田子坊 / 陆家嘴 / 北海公园 / 越秀公园 / yuyuan_garden / xintiandi / tianzifang / lujiazui / beihai_park / yuexiu_park / west_lake / shenzhen_bay |
| 街道/区域专名 | 南京路 / 王府井 / 大栅栏 / nanjing_road |
| 组合词 | west_lake_hangzhou / bund_shanghai / pearl_tower_distant (含地名) |

**允许 (抽象化通用景观词)**:

| 类型 | 例 |
|---|---|
| 自然景观 | lake / waterfront / lakeside / river / mountain / forest / beach / pond |
| 城市景观 | skyline / skyscraper / colonial_buildings / cobblestone_street / alley / boutique |
| 建筑类型 | palace / temple / pagoda / ancient_architecture / traditional_building / stadium |
| 场景属性 | promenade / plaza / cafe_district / waterfront_park / financial_district |
| 氛围/质感 | morning_haze / golden_hour / neon_lights / serene / vibrant |

### 2.2 · LLM prompt 规则 (扩 ADR-0021)

在 LLM prompt 里加明确指令:

```
theme_tags 字段规则:
  ✓ 主题/氛围/活动词 (lake / morning / serene / hiking)
  ✓ 通用景观/建筑类型词 (skyline / palace / promenade)
  ✗ 城市名 (北京/上海/杭州 / Beijing 等)
  ✗ 地标专名 (故宫/长城/西湖/外滩/东方明珠 等)
  ✗ 景区/公园专名 (豫园/北海公园 等)
  ✗ 含地名组合词 (west_lake_hangzhou 等)
  
理由: 地理信息由 GPS + Geocoder 单独处理 (location 维度).
     theme_tags 描述照片语义内容, 不是地理位置.
```

### 2.3 · 测试期自动检测

加 `tests/personas/_check_geographic_taint.py` (新, 可选): 加载所有 persona/scenarios yaml, 扫描 theme_tags 含 stoplist 词 → 报告.

stoplist 维护在 `config/llm_settings.yaml::theme_tags_geographic_blocklist`.

### 2.4 · 数据清洗范围

li persona (24 处 xihu + 10+ 处其他) + zhang FP_* (5 处城市名). 共 ~40 处替换. 抽象化 mapping:

| 老 | 新 |
|---|---|
| xihu | lake / waterfront / lakeside |
| gugong | palace / ancient_architecture / traditional |
| great_wall | wall / stone_path / fortress |
| bund | riverbank / colonial_buildings / waterfront |
| pearl_tower (含 _distant) | skyscraper / tower |
| bird_nest | stadium / arena |
| shanghai_tower | tower / skyscraper |
| lujiazui | financial_district / skyline |
| leifeng | pagoda / temple |
| tianzifang | alley / lane / boutique |
| yuyuan_garden | garden / rockery |
| xintiandi | plaza / cafe_district |
| beihai_park | park / pavilion / lake |
| yuexiu_park | park / banyan |
| shenzhen_bay | bay / promenade / coast |
| west_lake_hangzhou, bund_shanghai 等组合 | 拆抽象化 |
| 城市名 (单独出现) | 删除 |

### 2.5 · 不变性

- 地名信息仍由 location 维度承载 (GPS + Geocoder 4 档 ADR-0016)
- narrative 字段 (个人理解) 仍允许地名 (那是文学化, 不入 cluster)
- group 字段 (eg. `xihu_overnight`) 是测试 metadata, 不入 L1Output theme_tags, 不动
- yaml 注释里的"西湖"等中文不动 (人类阅读用)
- main_subjects (subject 字段) 同样禁地名

### 2.6 · 设计选择

| 选 | 决定 | 备选 |
|---|---|---|
| 禁词级别 | **prompt 指令 + persona 清洗 + 测试期检测 (3 层)** | 仅 prompt (不防真 LLM 漂移) / 算法 stoplist 过滤 (硬过太黑盒) |
| stoplist 配置 | 配置化 yaml (易扩) | 硬编码 |
| 清洗策略 | 抽象化替换 (保留语义) | 全删 (失主题信息) |

---

## 三、影响

### 3.1 · 测试期望变化

- li xihu 系列 scenarios (B2/T1/CB_07 等) theme 词从"xihu" 改"lake/waterfront" 后, Qwen embedding 簇可能略变
- 预期: 之前 24 处 xihu 聚成 1 个超大簇, 现散成 [lake, waterfront, lakeside] 3 个簇 — coverage 可能略降
- 跑测试看哪些 case 受影响, 不破坏 invariant 即可

### 3.2 · 跨文档矩阵 (CLAUDE.md 第 2 条)

- ✅ `decisions/0025-*.md` (本)
- ✅ `docs/27_persona_mock_realism.md` 加禁地名段
- ✅ `docs/00_index.md` 加 ADR-0025
- ✅ `config/llm_settings.yaml` 加 `theme_tags_geographic_blocklist`
- ⏳ `tests/personas/*.yaml` 数据清洗 (~40 处)
- ⏳ `tests/personas/_check_geographic_taint.py` 自动检测 (可选)

---

## 四、Open Questions

- **OQ-036**: 抽象化 mapping 表是否合理? 真实数据上线后看用户拍照 vs 算法判断匹配度
- **OQ-037**: 真 LLM 在 prompt 加禁地名指令后, 是否仍 hallucinate? (跟 OQ-031 真实 LLM 行为基线关联)

---

## 五、不做

- 不动 location 维度 (Geocoder ADR-0016 仍管地理)
- 不删 narrative 里的地名 (那是文学化, 不入 cluster)
- 不引入 NER (Named Entity Recognition) 自动剥离地名 (复杂度高, 用 stoplist 够)
