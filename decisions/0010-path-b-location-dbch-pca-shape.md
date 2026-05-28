# ADR-0010 · 路径 B location 维度: 分级 DBSCAN + PCA OBB + 形状校正

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-15 |
| 决策人 | Ace (产品/增长) — 与 Claude Code 联合设计, 经 4 轮迭代 (PCA 引入 → 长宽边界 → 形状校正 → 4 档 strength 终值) |
| 影响范围 | 重写 `src/features/location.py` + 升级 `src/contracts/features.py::LocationFeature` + 新增 `config/path_b_location.yaml` + 新增 `docs/16_path_b_location.md`; 改 `docs/{00,01,02,07,11,12}` + 根目录 `Seenful_L1_L2_Full_Decision_Flow.md` / `Seenful_L2_Project_Structure.md` (如有引用) + 新增 fixtures + 单测 + 重生 golden |
| 相关文档 | `docs/16_path_b_location.md` (本算法主规范) |
| 关联 OQ | **不关闭**任何 OQ-009 子问题 (§9a-§9g 涵盖 theme/event/people/anchor 严格度, 不含 location); **新增** [OQ-021](../docs/12_open_questions.md#oq-021-adr-0010-接受边界的真实数据验证) 跟踪 ADR-0010 接受/不修边界 (市内 chain / 沿江长条 / U 形栈道) 的 v0.2 真实数据验证 |
| 关联 ADR | supersede [ADR-0004](./0004-feature-assembler-revision.md) §3.2.1 location_score 段 (max 距离 + 分段函数 + LocationContext 三档); 与 [ADR-0005](./0005-place-anchor-dbch.md) (路径 A DBCH) 算法范式同源但**目标不同** — 路径 A 是"1 张 vs anchor 匹配", 本 ADR 是"N 张自身判形状" |

---

## 1 · 背景

### 1.1 · 路径 B location 现状

`src/features/location.py::compute_location_score` 算法:
- 两两 haversine 取**最大成对距离** (max_distance_m)
- 查 `config/dimension_thresholds.yaml::location_distance_bands` 单一档位表 → score
- v0.1 测试期 (ADR-0007) 三 context 表塌缩为单一表 (strong/medium/weak = 500m/1000m/2000m)

### 1.2 · 失败模式 (Ace 2026-05-15 提出)

max 距离丢了空间分布形状, 至少在 4 类常见场景下判错:

| 场景 | max 距离 | 老判 | 应该 | 原因 |
|---|---|---|---|---|
| 步行街 (沿街 1.2km) | 1.2km | medium | strong | 线状, 跨度大但是同一活动 |
| 西湖大景区 (一日游 3.2km) | 3.2km | none | medium/strong | 面状, 跨度大但是同一活动 |
| 千岛湖湖边 (沿湖 2.5km) | 2.5km | none | strong | 线状, 跨度大但是同一活动 |
| 跨城驾车顺手拍 (800m) | 800m | medium | none | 假同点, 是路过 |

根因: **max 距离丢了 2 层信息** — 空间分布形状 (线/带/面/团) + 时间停留密度 (路过 vs 游玩)。

### 1.3 · 引发本 ADR 的具体问题

OQ-009 §9a 跟踪"路径 B 多维度匹配严格度", v1.3.2 (ADR-0004) 重写 location_score 但仍是 max 距离 + 分段函数路线, 无法解上述失败模式。 必须改算法范式: **不再算 score, 直出 band**, 与 ADR-0005/0008/0009 路径 A 直出模式对齐。

---

## 2 · 决策

### 2.1 · 算法范式

**路径 B location 不再算 score, 直出 4 档 band (strong/medium/weak/none) 为终值**, 真值表 28 条结构不变, 只读 `LocationFeature.band`。

跨维度组合的歧义 (chain + bimodal) 通过 **location 维度内部保守化**消化, 不引入 HR-POST 兜底, 与真值表 + hard rule 分工保持原样。

### 2.2 · 三层判定流水线 (K_outer = 1 路径)

```
照片 GPS + 时间
    │
    ▼
分级 DBSCAN (外层 eps=1500m / 内层 eps=500m)
    │
    ├─ K_outer = 0       → none
    ├─ K_outer = 1       → 路径 A (Step A1 → A2 → A3)
    ├─ K_outer = 2       → 路径 B (单步双簇判定)
    └─ K_outer ≥ 3       → none
    │
    ▼
Step A1 · PCA 基础 band (用 L / W / R / K_inner) — 9 行网格
    │
    ▼
Step A2 · 形状校正 (用 τ = T / D) — 2 条补丁
    │
    ▼
Step A3 · transit 降档 (transit ≥ 30 kmh → 降一档)
    │
    ▼
LocationFeature.band (4 档终值)
```

### 2.3 · 核心变量定义

| 变量 | 定义 | 计算时机 |
|---|---|---|
| **K_outer** | DBSCAN(eps=1500m, min_samples=2) 簇数 (不含 outlier) | 任何时候 |
| **K_inner** | DBSCAN(eps=500m, min_samples=2) 簇数 | 仅 K_outer = 1 |
| **L** | 外层那唯一簇 GPS 做 PCA, 主轴投影跨度 (km) | 仅 K_outer = 1 |
| **W** | PCA 次轴投影跨度 (km) | 仅 K_outer = 1 |
| **R** | L / W (长宽比) | 仅 K_outer = 1 |
| **D** | 外层那唯一簇 GPS 凸包直径 = 最远两点距离 (km) | 仅 K_outer = 1 |
| **T** | 按 timestamp 排序后, 相邻点折线累加总长 (km) | 仅 K_outer = 1 |
| **τ** | T / D (曲折度) | 仅 K_outer = 1 |
| **gap** | K_outer 簇凸包间最小距离 (km) | 仅 K_outer ≥ 2 |
| **transit** | 时序相邻照片对 (Δt ≥ 20 min) 的距离 / 时间最大值 (kmh); 若全部相邻对 Δt < 20 min → null | 任何时候 |

⚠ T 用 timestamp 排序但**不参与判定**, 只用做"画折线"。 跟 time 维度的双峰检测 / 跨度判定**不冲突** — time 维度看时间跨度, location 维度只看空间几何 (轨迹长度是空间属性, 时间只是排序索引)。

### 2.4 · Step A1 · PCA 基础 band (9 行网格, 按行顺序匹配)

| # | L (km) | W (km) | R | K_inner | 基础 band | shape |
|---|---|---|---|---|---|---|
| A1.1 | > 5 | — | — | — | **none** | oversized |
| A1.2 | — | > 1.5 且 L > W | — | — | **none** | oversized |
| A1.3 | — | ≥ 1.5 | > 5 | — | **none** | oversized |
| A1.4 | ≤ 0.5 | — | — | — | **strong** | compact |
| A1.5 | ≤ 5 | < 0.5 | > 5 | = 1 | **strong** | linear |
| A1.6 | ≤ 1.5 | — | ≤ 5 | — | **strong** | compact |
| A1.7 | ≤ 3 | ≤ 1.5 | — | — | **medium** | stretched |
| A1.8 | > 3 且 ≤ 5 | ≤ 1.5 | — | — | **medium** | extended |
| A1.9 | 其他 | — | — | — | **weak** | irregular |

**A1.5 的 K_inner = 1 限制**: 只有内层也只有一簇时, PCA 的"窄长条"才可信为真步行街/湖边。 K_inner ≥ 2 表示长条是**退化形状** (例: A 拍 2 张 + B 拍 2 张 GPS 集中在两端连成线), 不当 linear strong, 顺延到 A1.6~A1.9 判定。

### 2.5 · Step A2 · 形状校正 (2 条补丁, 用 τ)

| # | A1 输出 | τ 条件 | 几何兜底 | 校正后 band | 新 shape |
|---|---|---|---|---|---|
| A2.1 | **none** (从 A1.1 或 A1.2 来) | τ > 2 | L ≤ 8 且 W ≤ 3 | **medium** | loop / u_shape |
| A2.2 | **strong** (从 A1.5 linear 来) | τ > 1.5 | — | **medium** | linear_curved |
| A2.3 | 其他 (含 A1.3 oversized) | — | — | 不变 | 沿用 A1 |

**A2.1 解读**: A1 把环湖 / U 形误杀成 none (因 W > 1.5), 但 τ > 2 说明实际是绕路 + 跨度合理 (L ≤ 8km, W ≤ 3km) → 平反到 medium。

**A2.2 解读**: A1.5 认为窄长条 = 真步行街 = strong, 但 τ > 1.5 说明它弯曲, 不是真直线 → 降到 medium。

⚠ **不做 τ > 4 穿梭降档** (2026-05-15 Ace 决定): τ 大不一定是"反例", 可能是用户在同一店来回拍照, 误杀概率高。

### 2.6 · Step A3 · transit 降档

```
若 transit ≥ 30 kmh 且 当前 band ∈ {strong, medium}:
    band ← 降一档 (strong → medium, medium → weak)
否则 (transit < 30 或 null):
    不降档
```

20 min 间隔过滤是核心: 防止 GPS 漂移导致瞬时速度膨胀 (例: 两张连拍间隔 30s, 漂移 200m, 老算法会算出 24 kmh 误判)。 过滤后所有相邻对 Δt < 20 min → transit = null, 不降档。

### 2.7 · 路径 B · K_outer = 2 (双簇, 单步判定)

| # | gap (km) | transit (kmh) | band | shape |
|---|---|---|---|---|
| B.1 | ≤ 0.5 | — | **strong** | multi_close |
| B.2 | ≤ 2 | < 20 或 null | **medium** | multi_walk |
| B.3 | ≤ 2 | ≥ 20 | **weak** | multi_drive |
| B.4 | > 2 | — | **none** | multi_far |

双簇场景 τ 含义不直观 (T 跨簇时穿越 gap 反复无意义), 不引入 D/T/τ; gap + transit 已足够判定。

### 2.8 · 市内 chain 接受策略

**接受 DBSCAN 单链可达带来的"路上点把两簇连成 K_outer=1"** — 产品语义上"上午 A + 中午路上 + 下午 B (同城)" 是一次出游故事, 该判合。 真正该判散的是"跨城 25km 中间无点", 这种 chain 触发不了。

落痕 `shape = stretched` + `max_transit_kmh` 保留逃生口给 LLM / 后置审计。

### 2.9 · 暂不修复的边界场景 (Ace 2026-05-15 明示)

| 场景 | 老判 | 新判 (本 ADR) | 处理 |
|---|---|---|---|
| 沿江步道 5.5km (直线, τ ≈ 1) | none (max > 2km) | **none** (A1.1, τ ≈ 1 救不了) | 接受, 5km 是硬边界 |
| U 形栈道 (1km × 0.5km 范围, 走 4km, τ = 4) | strong | **strong** (A1.6, τ > 4 不降档) | 接受, U 形仍在合理跨度内 |

OQ-017 (POI 城市判定接入) 完成后, eps / gap 阈值可按 context 弹性 (home_city 1km / cross_province 2km / cross_country 3km), 届时这两个边界场景可重新评估。

### 2.10 · 配置

```yaml
# config/path_b_location.yaml
dbscan:
  eps_outer_m: 1500
  eps_inner_m: 500
  min_samples: 2

a1_grid:
  l_oversized_km: 5.0     # A1.1 L 上限
  w_oversized_km: 1.5     # A1.2 W 边界
  r_oversized: 5.0        # A1.3 R 边界
  l_compact_km: 0.5       # A1.4 紧凑上限
  l_linear_max_km: 5.0    # A1.5 linear L 上限
  w_linear_max_km: 0.5    # A1.5 linear W 上限
  r_linear_min: 5.0       # A1.5 linear R 下限
  l_compact_max_km: 1.5   # A1.6 上限
  r_compact_max: 5.0      # A1.6 R
  l_stretched_max_km: 3.0 # A1.7 L 上限
  w_stretched_max_km: 1.5 # A1.7 W 上限
  l_extended_max_km: 5.0  # A1.8 L 上限

a2_correction:
  tortuosity_loop_threshold: 2.0     # A2.1 τ 边界
  l_loop_max_km: 8.0                 # A2.1 L 兜底
  w_loop_max_km: 3.0                 # A2.1 W 兜底
  tortuosity_curved_threshold: 1.5   # A2.2 τ 边界

a3_transit:
  transit_demote_kmh: 30.0       # A3 降档阈值
  min_interval_minutes: 20       # transit 计算最小间隔过滤

path_b_dual:
  gap_close_km: 0.5      # B.1
  gap_walk_max_km: 2.0   # B.2/B.3 共用
  transit_walk_kmh: 20.0 # B.2/B.3 分界
```

---

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| **A. 仅 max 距离 + 单一档位表 (v0.1 现状)** | 失败模式见 §1.2, 4 类常见场景判错 |
| **B. max 距离 + 凸包面积 + 停留时长辅助信号** | 真值表里"location strong/medium/light"含义被污染, HR-PRE 又多一层修订, 越看越乱; 不解决根本问题 — 仍是 score 驱动 |
| **C. 接 POI / AOI 边界判定** | 中国 POI 数据准确度不够 + 语义混乱 (Ace 2026-05-15 明示排除); v0.1 demo 无 POI 数据源, 与 OQ-010 user_home_city stub 同卡点 |
| **D. PCA OBB 单算法 (不加 D/T/τ)** | PCA 对环形 / U 形 / 圈形点云失效 (Ace 2026-05-15 提出): 西湖环湖游 (3×2km) 触发 A1.2 W > 1.5 误杀 none。 必须叠加凸包直径 + 轨迹长度 + 曲折度 τ |
| **E. PCA + 凸包 + 轨迹 + τ + 穿梭降档 (τ > 4 降一档)** | τ > 4 误杀概率高 (用户在同一店来回拍照 T 膨胀但实际同点), Ace 2026-05-15 决定不做 |
| **F. PCA + 凸包 + 轨迹 + τ + HR-POST-LOC-01 跨维度兜底** | 让真值表读单一 band 即可, 不再外挂 hard rule (Ace 2026-05-15 明示 "4 档 strength 终值"); 跨维度歧义改用 location 内部保守化消化 |
| **G. 本 ADR — 三层流水线 (PCA 基础 + 形状校正 + transit 降档)** | 修了 §1.2 的 4 类失败 + 修了环湖 / 步行街 / 千岛湖湖边; 接受沿江长条 / U 形栈道两个边界 (待 OQ-017 真实数据后评估); 与路径 A 直出 band 范式对齐; 真值表 28 条结构不动 |

---

## 4 · 影响范围

### 4.1 · 契约变更

**修改** `src/contracts/features.py::LocationFeature`:

```python
# 旧 (v1.3.2 ADR-0004 引入, 现 supersede):
class LocationFeature(BaseModel):
    score: float
    confidence: float
    max_distance_m: float
    is_high_frequency_place: bool
    context: LocationContext            # ← 删
    threshold_table_used: str           # ← 删
    primary_signal: str = "exif_location"

# 新 (本 ADR):
class LocationFeature(BaseModel):
    band: BandLevel                                    # ← 新, 终值 (4 档)
    score: float = Field(ge=0.0, le=1.0)               # 派生展示, 真值表不读
    cluster_count_outer: int                           # ← 新 (K_outer)
    cluster_count_inner: int | None                    # ← 新 (K_inner, 仅 K_outer=1)
    outer_length_km: float | None                      # ← 新 (L)
    outer_width_km: float | None                       # ← 新 (W)
    outer_ratio: float | None                          # ← 新 (R)
    convex_hull_diameter_km: float | None              # ← 新 (D)
    trace_length_km: float | None                      # ← 新 (T)
    tortuosity: float | None                           # ← 新 (τ)
    inter_outer_gap_km: float | None                   # ← 新 (gap)
    max_transit_kmh: float | None                      # ← 新 (transit)
    outlier_count: int                                 # ← 新
    shape: LocationShape                               # ← 新 (枚举)
    rule_fired: str                                    # ← 新 ("A1.7" / "A2.1" / "B.2" 等)
    is_high_frequency_place: bool = False              # 保留
    primary_signal: str = "exif_location"              # 保留
```

⚠ **Ace 偏好: 老方案直接删, 不留 deprecated 兼容** (memory `delete-old-no-compat`)。 `LocationContext` 枚举若无其他引用, 一并删 (跟 ADR-0007 临时塌缩状态对齐 — context 字段早已不参与判定, 仅落痕)。

**修改** `FeaturePackage.location_score` 字段:
- 保留为 backward-compat scalar, 但 truth_table.py 已通过 `Bands.location` 间接消费, 不再有真值表直读 `location_score` 的代码
- 由 `LocationFeature.score` 派生填充 (展示值, 非判定输入)

### 4.2 · 新增算法模块

**重写** `src/features/location.py`:
- `build_location_feature(photos, cfg) -> LocationFeature` 高层入口
- 内部子函数:
  - `_haversine_km(p1, p2)` (复用)
  - `_to_local_meters(gps_list, anchor)` 经纬度 → 局部平面米制坐标
  - `_dbscan(points_xy, eps_m, min_samples)` 手撸 DBSCAN, 不引 sklearn
  - `_pca_obb(cluster_xy)` numpy SVD 算主次轴 + 投影跨度 → (L, W, R)
  - `_convex_hull(cluster_xy)` 凸包顶点 + 直径
  - `_trace_length(photos_sorted_by_ts)` 时序折线累加
  - `_max_transit_kmh(photos_sorted_by_ts, min_interval_min)` 速率最大值 (过滤短间隔)
  - `_step_a1_pca_grid(L, W, R, K_inner) -> (band, shape, rule_fired)`
  - `_step_a2_shape_correction(band, shape, rule_fired, tortuosity, L, W) -> (band, shape, rule_fired)`
  - `_step_a3_transit_demote(band, rule_fired, transit) -> (band, rule_fired)`
  - `_step_b_dual_cluster(gap, transit) -> (band, shape, rule_fired)`

纯 Python, **零额外依赖** — 2D PCA 用 2×2 协方差矩阵闭式解, DBSCAN / 凸包 / haversine 手撸 (numpy 不在项目依赖)。

### 4.3 · 配置

新增 `config/path_b_location.yaml` (见 §2.10)。

`config/dimension_thresholds.yaml::location_distance_bands` 与 `location_distance_thresholds_unified` 段**保留**为派生 score 计算用 (LocationFeature.score 仍输出), 但**不再参与 band 判定** — band 来自 `path_b_location.yaml`。

### 4.4 · 调用方

**修改** `src/features/assemble.py`:
- 调 `build_location_feature(photos, cfg)` 替代 `compute_location_score`
- `FeaturePackage.location` 填新 `LocationFeature`
- `FeaturePackage.location_score` 由 `feature.score` 派生 (维持 v0.1 字段语义)
- `FeaturePackage.is_high_frequency_place` 仍来自 LocationFeature

**修改** `src/policy/bands.py` (若有):
- `Bands.location` 直接读 `LocationFeature.band`, 不再走 `score → 阈值查表`
- 高频地点降一档逻辑保留 (来自 `is_high_frequency_place`)

### 4.5 · 测试

**新建** `tests/fixtures/photos/`:
- `westlake_5_walking.json` (西湖一日游, A1.8 medium)
- `walking_street_4.json` (步行街, A1.5 linear strong)
- `qiandaohu_6_lakeside.json` (千岛湖湖边, A1.5 linear strong)
- `cross_city_2plus2.json` (杭州 + 临安, B.4 none)
- `degenerate_2plus2.json` (A 2 张 + B 2 张, A1.7 medium, 验证 K_inner=2 退化路径)
- `loop_around_lake.json` (3×2km 环湖, A2.1 平反 medium, 验证 τ 形状校正)
- `same_city_chain.json` (上午 A + 路上 1 张 + 下午 B, K_outer=1 + stretched, transit 走 / 车两版)

**新建** `tests/unit/features/test_location.py`:
- A1.1~A1.9 每行 ≥ 1 正例 + 1 边界
- A2.1 / A2.2 形状校正各 ≥ 2 例
- A3 transit 降档 ≥ 2 例 (transit 高 / 低 / null)
- B.1~B.4 每行 ≥ 1 例
- 边界: 全 outlier / 单簇退化 K_inner ≥ 2 / 凸包退化 (3 点共线)
- 工具函数单测: `_pca_obb` / `_dbscan` / `_convex_hull` / `_trace_length` / `_max_transit_kmh`

**重生** golden:
- `tests/scenarios/batch_*.yaml` 所有涉及 location 的 golden (估 ~10 个) 重跑 `scripts/generate_golden.py`
- 人工 diff 审 location 字段从 score-driven 到 band-driven 的变化

---

## 5 · 决策回滚条件

| 回滚条件 | 动作 |
|---|---|
| 真实数据上路径 B 命中率因严格度调整下降 > 20% | 调 A1 网格阈值 (L/W/R 边界), 写新 ADR 记录 |
| 市内 chain 误合并率 > 真实路过率 (Ace 验证后判定) | 加 HR-POST-LOC-01 跨维度兜底 (location.shape=stretched + time.is_bimodal → 降一档) |
| τ 计算因 timestamp 漂移误差 > 30% | 改 T 用 MST 长度替代时序折线长度 (脱离 timestamp 依赖) |
| 国外 / 大景区场景 eps=1500m 不够大 | OQ-017 触发, eps 按 context 弹性 (home_city 1km / cross_province 2km / cross_country 3km) |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-009 §9a (theme jaccard_multi 严格交集) | 待决 | **不变** — §9a 是 theme 字段, 本 ADR 不动 theme |
| OQ-009 §9b-§9f (event/people/anchor/路径 A) | 待决 | **不变** — 本 ADR 不动这些维度 |
| OQ-009 §9g (各路径分档阈值是否独立) | 待决 | **部分关闭** — 路径 B location 现独立于 `dimension_bands.location` 阈值表 (band 直出, 不读阈值) |
| OQ-017 (POI 城市判定后 location 档位回切) | 待 OQ-010 触发 | **不变** — 本 ADR 只动路径 B, ADR-0007 路径 A 的 unified 档位继续待 OQ-017 回切 |
| **OQ-021 (新增)** | — | ADR-0010 接受边界的真实数据验证 — 市内 chain 接受度 / 沿江长条 5.5km / U 形栈道 τ>4 三个边界 v0.2 验证 |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完 (Step 1)
2. ⏳ `docs/16_path_b_location.md` 完整算法规范 (Step 2)
3. ⏳ `docs/{02,07,00,01,11,12}` 同步 (Step 3-6)
4. ⏳ `config/path_b_location.yaml` 新建 (Step 7)
5. ⏳ `src/contracts/features.py::LocationFeature` 升级 + `__init__.py` 导出 (Step 8-9)
6. ⏳ `src/features/location.py` 重写 + `assemble.py` 适配 (Step 10-11)
7. ⏳ Fixtures + 单测 + golden 重生 + grep 自检 (Step 12)
8. ⏳ Spec 归档 — 本 ADR 自身就是设计来源, 无独立 spec 文件可归 (与 ADR-0007 同, 不进 `archive/specs/`)
9. ⏳ v0.2: OQ-021 (市内 chain 接受度) 验证 + OQ-017 触发后 eps 弹性
