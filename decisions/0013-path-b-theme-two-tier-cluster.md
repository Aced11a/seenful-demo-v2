# ADR-0013 · 路径 B theme 维度: 双层字段判定 (主 + 次 + 升降档)

| 字段 | 值 |
|---|---|
| 状态 | accepted (**多处修订**: Phase 1 → [ADR-0024](./0024-theme-topk-coverage.md) Top-K; Phase 2 加 TH.0 → [ADR-0022](./0022-th0-multi-parallel-clusters-medium.md); 加 Phase 4-6 subject MAX-OR + stoplist → [ADR-0023](./0023-theme-subject-max-or.md)) |
| 决策日期 | 2026-05-18 |
| 决策人 | Ace (产品/增长) — 经多轮迭代 (v0.1 单一主簇 → v0.2 cluster-centric → v0.3 双层字段) |
| 影响范围 | 重写 `src/features/theme.py` + 新增 `src/features/_two_tier_cluster.py` 通用工具 + 升级 `src/contracts/features.py::ThemeFeature + ThemeShape` + 新增 `config/path_b_theme.yaml` + 新增 `docs/19_path_b_theme.md`; 改 `docs/{00,01,02,07,11,12}` |
| 相关文档 | `docs/19_path_b_theme.md`; `Path_B_Theme_Aggregation_Spec.md` v0.3 (设计来源, 实施完后归档) |
| 关联 OQ | **关闭** OQ-009 §9a; **新增** [OQ-024](../docs/12_open_questions.md#oq-024-adr-0013-接受边界的真实数据验证) (5 子问题 a-e: 阈值校准 / min_hit_count / 次字段聚类阈值 / mock 局限 / 升降档幅度) |
| 关联 ADR | supersede 老 `src/features/theme.py` (字面 Jaccard 三路加权); **复用** [ADR-0008](./0008-theme-semantic-clustering.md) `MockEmbedder` + `agglomerative_cluster_cosine`; 范式同 [ADR-0012](./0012-path-b-event-aggregation.md) (双门槛), 触发条件相反 (event 严档双门槛 / theme 模糊段双门槛) |

---

## 1 · 背景

### 1.1 · 现状

`src/features/theme.py` v0.1: `0.5 × jaccard(theme_tags) + 0.4 × jaccard(main_subjects) + 0.1 × scene_consistency`. 严格交集 1 张离群 → 0, 无语义识别, 跟 path A (ADR-0008 语义簇) 不一致.

### 1.2 · 失败模式

| 场景 | 老 score |
|---|---|
| 1 张离群 | ≈ 0 (严格交集) |
| 同义不同字 (lakeside/湖边/water) | ≈ 0 (字面 Jaccard) |
| 混合多主题 (湖+夕阳+慢生活) | medium (ties 错判) |
| 主+次字段重要性不同 | 0.5/0.4 权重混合丢分层信号 |

### 1.3 · A2 真值表约束

A2: `theme=强 → bounds=[medium, strong], type=thematic` — **单独 strong 直接成集**. v0.3 strong 唯一通道: 主字段 coverage=1.0 OR 主字段 medium + 次字段 ≥ 2/3.

### 1.4 · 引发本 ADR 的具体问题

OQ-009 §9a (theme 严格度) 长期未关闭. ADR-0010/0011/0012 已落 path B 3/7 维直出 band. theme 是最后一个主载体未升级.

必须改算法: **直出 band + 双层字段判定 + cluster hit_rate + coverage + outlier 标记**.

---

## 2 · 决策

### 2.1 · 算法范式

**直出 4 档 band**, 真值表 28 条不变, 只读 `ThemeFeature.band`.

**双层字段判定**:
- 主字段 (theme_tags) → cluster 聚类 → coverage → primary_band
- 仅 primary_band ∈ {TH.2, TH.3} → 次字段 (main_subjects) → secondary_coverage → 升降档

### 2.2 · 三阶段流水线

```
Phase 1 · 主字段聚类
  tag_pool_primary = ⋃ p.theme_tags
  agglomerative_cluster_cosine(vectors, 0.75) → primary_clusters
  cluster.hit_rate = hit_count / N
  theme_clusters = hit_rate ≥ 0.5 AND hit_count ≥ 2
  primary_coverage = ⋃ theme_clusters.photos / N

Phase 2 · 主 band 判定 (5 行 grid)
  1.0          → TH.1 strong
  0.8 ≤ < 1.0  → TH.2 medium-high  ← 触发次
  0.5 ≤ < 0.8  → TH.3 medium-low   ← 触发次
  < 0.5        → TH.4 weak
  N_valid ≤ 1  → TH.5 none

Phase 3 · 次字段升降档 (仅 TH.2/TH.3)
  tag_pool_secondary = ⋃ p.main_subjects
  同 Phase 1 聚类 → secondary_coverage
  ≥ 2/3 → 升 strong (rule_fired +secondary_boost)
  1/3 ≤ < 2/3 → 不动 medium
  < 1/3 → 降 weak (rule_fired +secondary_demote)
```

### 2.3 · 核心变量

| 变量 | 定义 |
|---|---|
| N | 总照片数 |
| N_valid | 有 ≥ 1 个 theme_tag 的 photo 数 |
| primary_clusters / theme_clusters | 主字段聚类结果 / 过阈值簇 |
| primary_coverage | ⋃ theme_clusters.photos / N |
| primary_outliers | 未命中 theme_cluster 的 photo |
| secondary_coverage | 次字段 ⋃ secondary_theme_clusters.photos / N (仅 TH.2/TH.3 计算) |
| secondary_action | "none" / "boost" / "demote" |

### 2.4 · 5 行主 grid

| # | primary_coverage | primary_band | 触发次? |
|---|---|---|---|
| TH.1 | = 1.0 | strong | ❌ |
| TH.2 | 0.8 ≤ < 1.0 | medium-high | ✅ |
| TH.3 | 0.5 ≤ < 0.8 | medium-low | ✅ |
| TH.4 | < 0.5 OR cluster_count=0 | weak | ❌ |
| TH.5 | N_valid ≤ 1 | none | ❌ |

### 2.5 · 配置

```yaml
# config/path_b_theme.yaml
path_b_theme:
  primary_field: "theme_tags"
  primary_hit_rate_threshold: 0.5
  min_hit_count: 2

  primary_band_thresholds:
    strong_coverage: 1.0
    medium_high: 0.8
    medium_low: 0.5

  secondary_field: "main_subjects"
  secondary_band_adjust:
    boost_threshold: 0.667
    demote_threshold: 0.333

  fallback:
    n_valid_min: 1
```

---

## 3 · 评估过的备选项

| 方案 | 拒绝理由 |
|---|---|
| A. 字面 Jaccard (v0.1 现状) | 严格交集 1 张离群 → 0, 失败模式见 §1.2 |
| B. v0.2 单层 cluster (合并 theme_tags + main_subjects) | 丢失主次字段重要性差异, Ace 否决 |
| C. ADR-0004 embedding 双向最大池化 | 工程量大, v0.2 OQ-018 才能真接 |
| **D. 本 ADR (双层 cluster + 升降档)** | 修了 §1.2 全部失败 + 跟 ADR-0012 范式同源 + 主次分层 + 复用 ADR-0008 工具 |

---

## 4 · 影响范围

### 4.1 · 契约变更

`ThemeFeature` 升级 (老 v1.3.2 字段 → v0.3 双层字段, 删 score 三路 + tag_embedding_similarity 等老字段):

```python
class ThemeShape(str, Enum):
    FULL_COVERAGE_THEMED / DOMINANT_THEMED / PARTIAL_THEMED / NO_DOMINANT_THEME / NO_THEME_SIGNAL


class ThemeFeature(BaseModel):
    band: BandLevel
    rule_fired: str                      # "TH.1" / "TH.2+secondary_boost" 等
    score: float                          # 派生展示
    # 主字段诊断
    primary_coverage / primary_clusters / primary_outliers / ...
    # 次字段诊断 (仅 TH.2/TH.3 计算, 其他 None)
    secondary_coverage: float | None
    secondary_action: str                # "none"/"boost"/"demote"
    shape: ThemeShape
```

### 4.2 · 新增算法模块

**新增** `src/features/_two_tier_cluster.py` (通用工具, theme + anchor 共享):
- `build_two_tier_feature(photos, primary_extractor, secondary_extractor, cfg)` 通用入口
- 内部调 ADR-0008 `MockEmbedder` + `agglomerative_cluster_cosine`

**重写** `src/features/theme.py`:
- `build_theme_feature(photos)` 调通用工具, primary_extractor = `p.theme_tags`, secondary_extractor = `p.semantic_facts.main_subjects`

### 4.3 · 配置

新增 `config/path_b_theme.yaml`. 不再读 `dimension_thresholds.yaml::theme_overlap` (ADR-0004 v1.3.2 设计未落地, 已过期).

### 4.4 · 调用方

- `src/features/assemble.py` 调 `build_theme_feature(photos)` 替代 `compute_theme_score`
- `src/policy/bands.py::compute_bands` 中 `Bands.theme` 直读 `ThemeFeature.band`

### 4.5 · 测试

- `tests/unit/test_features_theme.py` 重写 (8 个 Case + 双层判定边界)
- 重生 golden

---

## 5 · 回滚条件

| 回滚条件 | 动作 |
|---|---|
| TH.1 strong 误判率 > 20% (人工 review "不该单独成集") | 提高 primary_hit_rate_threshold 0.5 → 0.6 |
| medium 误判率高 (升降档逻辑反例多) | 调 boost/demote 阈值 (0.667 → 0.75 或 0.333 → 0.25) |
| mock 表覆盖小导致真用户场景几乎都 TH.4 | 触发 OQ-018 真 Qwen 接入 |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-009 §9a | 待决 | **关闭** (ADR-0013 实现路径 B theme 语义簇 + 双层判定) |
| **OQ-024 (新增)** | — | ADR-0013 接受边界 v0.2 真实数据验证 (5 子问题) |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完
2. ⏳ `docs/19_path_b_theme.md`
3. ⏳ `config/path_b_theme.yaml`
4. ⏳ contracts 升级
5. ⏳ `src/features/_two_tier_cluster.py` + `theme.py` 重写
6. ⏳ assemble + bands 适配
7. ⏳ 跨 docs 同步
8. ⏳ 单测 + golden + grep + 归档
