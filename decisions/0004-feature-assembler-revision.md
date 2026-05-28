# ADR-0004 · Feature Assembler 三维度算法替换 (v1.3.1 → v1.3.2)

> ⚠ **部分修订 (v0.1 测试期)**: 本 ADR §2.1 `location_score` 的三档距离阈值 (home_city / cross_province / cross_country) 在 v0.1 测试期已被 [ADR-0007](./0007-unified-location-bands.md) 临时塌缩为单一表 (500/1000/2000m). 原因: `user_home_city` 模块仅 stub (OQ-010). POI 城市判定接入后回切, 见 [OQ-017](../docs/12_open_questions.md#oq-017-poi-城市判定接入后-location-档位回切计划). 本 ADR 其余部分 (time_score 双峰 + theme_overlap embedding 池化 + OQ-005/006/007 + §5.5 OQ-009 覆盖范围) **不受影响**.

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-12 |
| 决策人 | Ace (产品/增长) + KY (工程) 联合评审 |
| 影响范围 | `src/features/{location,time,theme}.py` + `src/contracts/features.py` + `config/dimension_thresholds.yaml` + `docs/07_dimension_thresholds.md` |
| 相关文档 | `docs/07_dimension_thresholds.md` §3.2.1 / §3.2.2 / §3.2.3 (v1.3.2) |
| 替代 | v1.3.1 老方案 (已从 docs 删除) |

---

## 1 · 背景

v1.3.1 的 Feature Assembler 在 v0.1 demo 阶段实际跑通后,发现三个维度的算法存在明显的**产品语义偏差**,在常见用户路径上会产出反直觉的判定。

### 失败模式 (来自 fixture + 内测照片回放)

**location_score (老 §3.2.1)**: 固定阈值不分用户所在城市
- 用户在常驻杭州,1 公里内的两次出门被判为同一段记忆(语义上其实是两个不同区域,例如"西湖" vs "武林广场")
- 用户在意大利旅游,500m 跨度可能是同一景区(例如威尼斯一个岛上的不同点),老方案直接判散

**time_score (老 §3.2.2)**: 只看首尾跨度,忽略中间分布
- 同日多事件被错连: 9 点早餐 / 12 点午餐 / 18 点晚餐 → 跨度 9h 落入 "<12h → 0.7" 中档,但语义上是三件独立事件
- 多日旅游被判散: Day1 上午景点 / Day2 中午景点 / Day3 下午景点 → 跨度 ~50h 落入 ">48h → 0.2" 弱档,语义上是一段连续旅程

**theme_overlap_score (老 §3.2.3)**: Jaccard 字面匹配丢失语义相近
- `["夕阳"]` vs `["晚霞"]` → 重合 0
- `["湖边"]` vs `["水边"]` → 重合 0
- `["饭菜"]` vs `["晚餐"]` → 重合 0
- L1 输出的 theme_tags 来自不同生成时机,词形不统一是常态,Jaccard 几乎不可用

---

## 2 · 决策

### 2.1 · location_score → 地理上下文感知

引入 `LocationContext` (home_city / cross_province / cross_country / mixed / unknown),不同上下文用不同距离阈值表:

- `home_city`: 强 < 100m / 中 < 300m / 弱 < 800m
- `cross_province`: 强 < 500m / 中 < 1500m / 弱 < 5000m
- `cross_country`: 强 < 2000m / 中 < 5000m / 弱 < 15000m

`mixed` (一组照片跨上下文) 强制取最严的 `home_city` 表,作为"刚好出市又回市"的反例兜底。

`home_city` 来自 `user_profile.home_city` (30 天内 GPS 频次最高的市级行政区,缓存),数据不足时 `context=unknown`,按配置 `fallback_context` (默认 `home_city` 保守) 处理。

### 2.2 · time_score → 双峰检测 + 旅游放宽

**双峰检测**: 用照片间隔的**中位数** vs **总跨度比例**判断是否多事件:
```
is_bimodal = median_gap > time_span * 0.3 AND len(photos) >= 4
```
命中即视为多次独立活动,`score = 0.30` (弱档),不再叠加旅游放宽。

`≥ 4 张` 门槛: 3 张只有 2 个 gap,中位数不稳定,统计意义不足。

**旅游放宽**: 当 `location.context ∈ {cross_province, cross_country}` 时,启用宽时窗分档:
- < 72h → 1.00
- < 168h (1 周) → 0.85
- < 336h (2 周) → 0.60
- 否则 → 0.30

常驻档保持原 v1.3.1 的分档逻辑 (< 0.5h / 2h / 12h / 48h),但归入 `home_city_brackets` 配置项。

### 2.3 · theme_overlap_score → embedding 双向最大池化

字面 Jaccard 替换为语义 embedding 余弦相似度:

1. 模型二选一 (配置切换): **BGE-M3** (推荐起步) / Qwen3-Embedding-0.6B
2. 每个 tag 单独 embed → 双向最大池化:
   ```
   a_to_b = mean(max over each row of cos_matrix)
   b_to_a = mean(max over each column of cos_matrix)
   sim = (a_to_b + b_to_a) / 2
   ```
3. 分档: 0.85 / 0.70 / 0.55 / 其余 → strong / medium / weak / none
4. 与原 `main_subjects` Jaccard + `scene_type` 一致性按 0.6 / 0.3 / 0.1 融合

`main_subjects` 的 Jaccard 故意保留 — 作为**字面强证据补丁**:当 embedding 给出中等相似但 main_subjects 高度重合时,融合分仍能拉到 medium。

---

## 3 · 评估过的备选项与拒绝理由

### location_score 备选

| 方案 | 拒绝理由 |
|---|---|
| **单一固定阈值表 (v1.3.1)** | 已确认产品偏差,见 §1 |
| 用户自定义阈值 | 增加配置复杂度;用户无法准确表达"100m vs 500m"的差异 |
| GeoCluster + DBSCAN | 同城噪声多,聚类不稳;且无法区分"常驻 vs 旅游"语义 |
| 行政区 ID 匹配 (city_id) | 反例:北京二环跟五环虽在同市但语义差异巨大;粒度不对 |
| **地理上下文 + 阈值表 (采用)** | 既利用 home_city 这一稳定信号,又保留距离的连续性 |

### time_score 备选

| 方案 | 拒绝理由 |
|---|---|
| **首尾跨度 (v1.3.1)** | 已确认 §1 中的失败 1+失败 2 |
| 高斯混合模型 (GMM) 检测多峰 | overkill, P0 阶段 ≤9 张照片样本不足以拟合 GMM |
| 平均间隔 (mean gap) | 被极端 outlier 拉偏,例:3 张前 5 分钟 + 1 张 9h 后 |
| **中位间隔 + 30% 比例 (采用)** | 中位数对 outlier 稳健;30% 是经验比例,可配置热更 |

### theme_overlap_score 备选

| 方案 | 拒绝理由 |
|---|---|
| **Jaccard (v1.3.1)** | 已确认 §1 中的字面匹配失败 |
| 同义词词典扩展 | 维护成本极高,长尾覆盖不全 |
| 单向最大池化 (mean of max axis=1) | tag 数量稀疏一方会拉高均值,失真 |
| LLM Judge 直接判主题相似 | 调用频次太高,P0 成本不可控;且 theme_score 是给 LLM 之前的客观信号 |
| **双向最大池化 (采用)** | 鲁棒;tag 级 embedding 可缓存,运行成本低 |

---

## 4 · 影响范围

### 契约变更 (`src/contracts/features.py`)

新增子模型:
- `LocationContext` (StrEnum)
- `LocationFeature` (含 `context` / `threshold_table_used` / `max_distance_m`)
- `TimeFeature` (含 `median_gap_hours` / `is_bimodal` / `is_travel_relaxed`)
- `ThemeFeature` (含 `tag_embedding_similarity` / `embedding_model_used` / `degraded`)

为保持 v0.1 demo (路径 B) 可继续跑通,旧的 scalar 字段 (`location_score` / `time_score` / `theme_score`) 在 `FeaturePackage` 上**暂时保留**,标记 deprecated,等下一轮算法实现完成后再裁剪。

### 配置新增 (`config/dimension_thresholds.yaml`)

- `location_distance_thresholds.{home_city,cross_province,cross_country}`
- `home_city_detection.{lookback_days,min_uploads_required,fallback_context}`
- `time_score.{bimodal_detection,home_city_brackets,travel_brackets,fallback_confidence_multiplier}`
- `theme_overlap.{embedding_model,embedding_dim,fusion_weights,similarity_to_band}`

顶层 `dimension_bands` (用于真值表分档) 保持不变。

### 代码 (`src/features/{location,time,theme}.py`)

**本 ADR 不动代码**。等用户审完文档+契约+配置,再开下一轮实现指令。

### 新增待决策项 (`docs/12_open_questions.md`)

- OQ-005: `home_city` 数据缺失时的默认上下文
- OQ-006: embedding 模型在生产环境的部署形态 (本地 vs API)
- OQ-007: embedding 缓存的失效策略

---

## 5 · 后续动作

1. (已完成) 重写 `docs/07_dimension_thresholds.md` §3.2.1 / §3.2.2 / §3.2.3
2. (已完成) 删除老方案文档段(产品判断:语义偏差大,无追溯价值)
3. (本 ADR) 记录决策链
4. 更新 `src/contracts/features.py` (新增子模型)
5. 更新 `config/dimension_thresholds.yaml`
6. 更新 `docs/12_open_questions.md`
7. 等用户审,下一轮做代码实现 + 单测重写 + 场景测试新例(双峰 / 旅游 / 同义 tag)

## 5.5 · 本 ADR 覆盖范围 vs 不覆盖

⚠ 本 ADR **不是** v0.1 → v1.3.2 全部问题的解决方案. 与 [OQ-009 多维度匹配分档](../docs/12_open_questions.md#oq-009-多维度匹配分档-multi-cross-算法严格度) 的关系:

**本 ADR 覆盖** (v1.3.2 落地后自动修):
- OQ-009 §9a — theme jaccard_multi 严格交集 → v1.3.2 用 embedding 双向最大池化, 本质 multi-cross
- OQ-009 §9d — anchor jaccard_multi 严格交集 → (P1 人脸 embedding 一并改)
- OQ-009 §9g — 各路径同名维度阈值统一性 → v1.3.2 全维阈值重校

**本 ADR 不覆盖** (留 OQ-009 独立处理):
- OQ-009 §9b — event 严格全员一致 → 仍存在, 需独立改成多数派
- OQ-009 §9c — people 严格全员一致 → 仍存在, 需独立改成多数派
- OQ-009 §9e — 路径 A 1 vs 聚合指纹 → 仍存在, 依赖 OQ-008 落地后做 1-vs-each-old
- OQ-009 §9f — 各路径同名维度算法不同 → 等 v1.3.2 接入 embedding 后自然统一

---

## 6 · 回滚条件

如果新方案在 v0.2 真实数据回放中表现明显劣于 v1.3.1,触发以下任一条件即回滚:

- 双峰检测**误报率 > 10%** (本是连续记忆被强判为多事件)
- embedding 服务 P99 延迟 > 800ms (影响整体 SLA)
- 跨上下文 mixed 兜底导致**漏聚集率上升 > 20%** (相对 v1.3.1)

回滚动作:`config/dimension_thresholds.yaml` 改一行 feature flag,代码层支持双轨。
