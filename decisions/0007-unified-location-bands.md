# ADR-0007 · Location 距离档位测试期统一化 (临时塌缩三 context 至单一档)

| 字段 | 值 |
|---|---|
| 状态 | **superseded by [ADR-0016](./0016-location-geocoder-4tier.md)** (2026-05-18 完成 4 档回切; OQ-017 关闭) |
| 决策日期 | 2026-05-14 |
| 决策人 | Ace (产品/增长) |
| 影响范围 | `config/place_anchor.yaml` + `config/dimension_thresholds.yaml` + `src/mini_album/place_anchor.py` (`distance_to_band` + `match_against_cluster` buffer) + `docs/{00,01,06,07,10}` + tests |
| 相关文档 | `docs/10_mini_album_schema.md` §2.3/§2.4/§2.8 (主), `docs/07_dimension_thresholds.md` §3.2.1 (location_score 档位) |
| 修订 (Supersedes 部分) | [ADR-0004](./0004-feature-assembler-revision.md) §2.1 location_score 三档阈值 + [ADR-0005](./0005-place-anchor-dbch.md) §2.3 距离档位 + §2.4 buffer base |
| 关联 OQ | 新增 [OQ-017](../docs/12_open_questions.md#oq-017-poi-城市判定接入后-location-档位回切计划) (POI 接入后回切计划) |
| 不修订 | DBCH 算法本身 (DBSCAN / hull / buffer 公式) + ADR-0006 低质量降档 + ADR-0004 time/theme 部分 |

---

## 1 · 背景

[ADR-0004](./0004-feature-assembler-revision.md) §2.1 + [ADR-0005](./0005-place-anchor-dbch.md) §2.3 给出按 `LocationContext` 三档分级的距离阈值:

| context | strong | medium | weak |
|---|---|---|---|
| home_city | 100m | 300m | 800m |
| cross_province | 500m | 1500m | 5000m |
| cross_country | 2000m | 5000m | 15000m |

这套设计的前提是 **`user_home_city`** 模块可靠 — 而该模块当前 ([OQ-010](../docs/12_open_questions.md#oq-010-user_home_city-推断模块实现)) 仅为硬编码 stub, 真正版本依赖 **POI 城市判定** (CLGeocoder / 行政区聚类) 接入。

### 引发本 ADR 的具体问题 (v0.1 demo 期)

在 demo 阶段同时跑三套距离阈值表会引入**多个不可分离的失败维度**:

1. **断电源不清**: 一个 location band=none 的结果, 既可能因 (a) `home_city` 表 800m 上限 + 实际距离 900m, 也可能因 (b) `cross_country` 表 15000m 上限 + 距离 20000m。但 demo 的 stub 又把所有照片都判为 `home_city`, 所以**外地照片实际跑的是错误档位** — 失败时无法在"档位错"和"距离错"之间归因。
2. **回归保护脆**: 任意一次 stub 数据微调 (例如 `radius_km: 30` → `25`) 会让 home_city 边缘照片跨表抖动, 真值表测试不稳。
3. **测试用例爆炸**: 每个场景都要乘以 3 个 context, 而当前 fixtures 缺乏外地 / 跨国数据, 三档阈值的 cross_province / cross_country 段从未被真实验证。

### 决策窗口

POI 城市判定模块属于 [OQ-010 子问题 10a-10d](../docs/12_open_questions.md#oq-010-user_home_city-推断模块实现) 范畴, **v0.2 才会真正实现**。在此之前继续保留三档既无价值(stub 把所有 context 强行设为 home_city), 又增加调试成本。

---

## 2 · 决策

### 2.1 · 距离档位塌缩为单一表

```yaml
unified_band_thresholds:
  strong_m: 500
  medium_m: 1000
  weak_m: 2000
```

`d ≤ 500 → strong / d ≤ 1000 → medium / d ≤ 2000 → weak / d > 2000 → none`

**新旧档位对照** (距离 d=300m 例):

| 旧 home_city 表 | 旧 cross_country 表 | 新 unified 表 |
|---|---|---|
| medium (300 > 100, ≤ 300) | strong (300 ≤ 2000) | strong (300 ≤ 500) |

⚠ **意识层副作用**:
- home_city 场景**变松** (原 home_city strong 上限 100m → 现 500m)
- cross_country 场景**变严** (原 country strong 上限 2000m → 现 500m)
- 这是测试期可接受的简化, **绝非永久方案**

### 2.2 · Buffer base 统一为 250m

```yaml
unified_buffer:
  alpha: 0.6
  base_m: 250    # = strong_m / 2 = 500 / 2
```

衰减表:

| n | buffer |
|---|---|
| 1 | 250m |
| 3 | 151m |
| 5 | 127m |
| 10 | 105m |
| 30 | 82m |

公式 `buffer = base / (1 + 0.6·ln(n))` 不变, 仅 base 从三档 (50 / 250 / 1000) 塌缩为 250。

### 2.3 · context 推断函数保留

`infer_context(photo, user_home_city)` 仍调用、仍写进 `MatchResult.diagnostics.context` (便于将来回切 + 落痕诊断), **但 `distance_to_band` 内部不再读取 per-context 阈值**。

这保证:
- 代码改动**最小**, 函数签名不变
- diag log 仍能看到 `context: home_city`(以备 v0.2 回切验证)
- 三 context yaml 段保留但 comment 注释, 一行 feature flag 即可回切 (`use_unified_bands: false`)

### 2.4 · 三 context yaml 段保留为注释

`config/place_anchor.yaml` + `config/dimension_thresholds.yaml` 原三档段**全部注释保留**, 不删:

```yaml
# ─── COMMENTED-OUT in v0.1 (see ADR-0007). 待 POI 城市判定接入后回切. ───
# band_thresholds:
#   home_city:      { strong_m: 100,  ... }
#   cross_province: { strong_m: 500,  ... }
#   cross_country:  { strong_m: 2000, ... }
```

---

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| **A. 保留三档 (现状, ADR-0005)** | OQ-010 stub 把所有 context 都判 home_city, 三档实际只跑一档, 但调试归因复杂 |
| **B. 删掉三档代码, 只留单档** | 违背 Ace 明确指示("不需要删除现在的按城市/省/国家的分级, 只需注释"), 且不利于 v0.2 回切 |
| **C. 塌缩为单一表 + 注释保留三档 (采用)** | 测试期简化归因 + 回切代价 = 改一行 feature flag |
| **D. 三档但全部用 home_city 值** | 等价于 (C) 但 yaml 表达更绕, 不直观 |

---

## 4 · 影响范围

### 配置 (`config/`)

- `config/place_anchor.yaml`:
  - `band_thresholds.{home_city,cross_province,cross_country}` → 全部 comment
  - `buffer.base_m.{home_city,cross_province,cross_country}` → 全部 comment
  - 新增 `unified_band_thresholds.{strong_m,medium_m,weak_m}`
  - 新增 `unified_buffer.{alpha,base_m}`
- `config/dimension_thresholds.yaml`:
  - `location_distance_thresholds.{home_city,cross_province,cross_country}` → 全部 comment (与本 ADR 同步, 即使 v0.1 demo 代码不读这个段)
  - 新增 `location_distance_thresholds_unified.{strong_m,medium_m,weak_m}`

### 代码 (`src/mini_album/place_anchor.py`)

- `distance_to_band(d_m, context, cfg)` → 改为读 `cfg["unified_band_thresholds"]`, **不再下钻 context**
- `match_against_cluster` 的 `base = cfg["buffer"]["base_m"][context]` → 改为 `base = cfg["unified_buffer"]["base_m"]`
- `match_against_cluster` 的 diag 新增 `band_table_used: "unified"` 字段 (将来回切时此字段会变成 "home_city" / "cross_province" / "cross_country")
- 函数签名**不变**, context 参数仍传入, 仅写进 diag

### 文档 (按 CLAUDE.md 第 2 条矩阵)

| 改了什么 | 同步改的 doc |
|---|---|
| 修改字段语义 / 阈值配置 | `docs/07_dimension_thresholds.md` §3.2.1 |
| 修改算法 | `docs/10_mini_album_schema.md` §2.3 §2.4 §2.8 |
| 新增 ADR | `docs/12_open_questions.md` OQ-017 + `docs/00_index.md` 决策记录段 |
| 总览同步 | `docs/01_architecture.md` (location 段提到三 context 处) + `docs/06_hard_rules.md` HR-BANDS-01 引用 |
| Spec 反向 (ADR 不可变) | [ADR-0004](./0004-feature-assembler-revision.md) + [ADR-0005](./0005-place-anchor-dbch.md) 顶部加 supersede 注释 |

### 测试

- `tests/unit/test_place_anchor.py`: 距离档位映射期望值更新, buffer 计算期望值更新
- `tests/fixtures/albums/*.json`: 不变 (DBCH 结构无关)
- `tests/scenarios/`: 涉及 location band 的场景重生 golden

---

## 5 · 决策回滚条件

本 ADR 是**临时性**决策, 触发回切而非回滚:

| 回切条件 | 动作 |
|---|---|
| OQ-010 user_home_city 模块 v0.2 实现完成 + POI 城市判定接入 | yaml 取消注释, 恢复三档; 删 `unified_*` 段; 代码 `distance_to_band` 恢复 `cfg[context]` |
| 真实数据 (≥ 100 用户) 上观察 unified 单档**误聚集率 > 20%** (单档把不同 context 的场景错判同档) | 提前回切 (即使 POI 未接入), 临时用 stub 改进 home_city 推断 |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-017 (新增) | — | POI 城市判定接入后 location 档位回切计划 (本 ADR 触发) |
| OQ-010 (user_home_city 推断模块) | P0 临时 stub | 不变 — 但本 ADR 让"stub 阶段三档错误归因"问题消失, 降低 OQ-010 紧迫度 |
| OQ-005 (home_city 缺失默认) | 临时决策 home_city 保守 | 本 ADR 期间**失效** — 不再读 context 阈值, fallback_context 配置无效 (v0.2 回切后重新生效) |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完
2. ✅ `docs/10_mini_album_schema.md` §2.3 §2.4 §2.8 改写
3. ✅ `docs/06/07/00/01` 同步
4. ✅ `docs/12` 新增 OQ-017
5. ✅ ADR-0004 + ADR-0005 顶部加 supersede 注释
6. ✅ `config/{place_anchor,dimension_thresholds}.yaml` 改写
7. ✅ `src/mini_album/place_anchor.py` 改写 + docstring 引 ADR-0007
8. ✅ 单测 + golden 重生
9. ⏳ v0.2: OQ-010 完成后, 触发回切 (一行 feature flag)
