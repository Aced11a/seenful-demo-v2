# ADR-0014 · 路径 B anchor 维度: 双层字段判定 (主 + 次 + 升降档)

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-18 |
| 决策人 | Ace |
| 影响范围 | 新增 `src/features/anchor.py::build_anchor_feature` + 新增 `src/contracts/features.py::AnchorFeature + AnchorShape + FeaturePackage.anchor` + 新增 `config/path_b_anchor.yaml` + 新增 `docs/20_path_b_anchor.md` |
| 相关文档 | `docs/20_path_b_anchor.md`; `Path_B_Anchor_Aggregation_Spec.md` v0.3 |
| 关联 OQ | **关闭** OQ-009 §9d; **修订** OQ-008 §8e (合并 → 分层); **新增** [OQ-025](../docs/12_open_questions.md#oq-025-adr-0014-接受边界的真实数据验证) (5 子问题) |
| 关联 ADR | **依赖** [ADR-0013](./0013-path-b-theme-two-tier-cluster.md) (复用 `_two_tier_cluster.py` 通用工具); supersede 老 `src/features/anchor.py` (Jaccard 取 max); 修订 OQ-008 §8e (合并 set → 主次分层) |

---

## 1 · 背景

### 1.1 · 现状

`src/features/anchor.py` v0.1 17 行: `max(jaccard(meaning_anchors), jaccard(object_anchors))`. 严格交集 1 张离群 → 0; 子字段独立 jaccard 取 max 丢分层信息.

### 1.2 · 失败模式

- 1 张离群 → max=0
- meaning 弱 + object 弱 各自 → 老 max=0 (但合并语义实际强)
- 字面不识同义
- OQ-008 §8e 老推荐"合并 set" v0.3 否决 (重要性混合)

### 1.3 · 引发本 ADR

跟 ADR-0013 theme 同源问题. anchor 是辅证 (C/E 系列降档信号), 但走 score → 阈值不一致. 改 band 直出.

### 1.4 · 修订 OQ-008 §8e

**老推荐**: meaning + object 合并成单 set, 不频次过滤
**v0.3 修订**: 主次分层. meaning 是相册"灵魂"层级 (天光/树影/慢下来), object 是"物体"层级 (扶梯/楼). 二者重要性显然不同, 不该混合.

---

## 2 · 决策

### 2.1 · 算法范式

**同 ADR-0013 双层判定**, 仅字段名换:
- primary = `meaning_anchors`
- secondary = `semantic_facts.object_anchors`

### 2.2 · 5 行主 grid (AN.1~AN.5)

| # | primary_coverage | primary_band | 触发次? |
|---|---|---|---|
| AN.1 | = 1.0 | strong | ❌ |
| AN.2 | 0.8 ≤ < 1.0 | medium-high | ✅ |
| AN.3 | 0.5 ≤ < 0.8 | medium-low | ✅ |
| AN.4 | < 0.5 OR cluster_count=0 | weak | ❌ |
| AN.5 | N_valid ≤ 1 | none | ❌ |

### 2.3 · 升降档 (Phase 3, 仅 AN.2/AN.3)

| secondary_coverage | 调整 | 最终 |
|---|---|---|
| ≥ 2/3 | 升 1 档 | strong (`+secondary_boost`) |
| 1/3 ≤ < 2/3 | 不动 | medium |
| < 1/3 | 降 1 档 | weak (`+secondary_demote`) |

### 2.4 · 配置

```yaml
# config/path_b_anchor.yaml
path_b_anchor:
  primary_field: "meaning_anchors"
  primary_hit_rate_threshold: 0.5
  min_hit_count: 2

  primary_band_thresholds:
    strong_coverage: 1.0
    medium_high: 0.8
    medium_low: 0.5

  secondary_field: "object_anchors"
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
| A. 老 max(meaning_j, object_j) | 严格交集 + 分立 jaccard 丢分层信号 |
| B. 合并 set (OQ-008 §8e 老推荐) | 主次重要性混合, Ace v0.3 否决 |
| **C. 本 ADR 双层分层 (meaning 主 + object 次)** | 跟 ADR-0013 范式同源; 共享通用工具; 跟 Ace 直觉一致 |

---

## 4 · 影响范围

### 4.1 · 契约变更

新增 (老 anchor 仅 anchor_score 字段, 无 AnchorFeature):

```python
class AnchorShape(str, Enum):
    FULL_COVERAGE_ANCHORED / DOMINANT_ANCHORED / PARTIAL_ANCHORED / NO_DOMINANT_ANCHOR / NO_ANCHOR_SIGNAL


class AnchorFeature(BaseModel):
    band: BandLevel
    rule_fired: str
    score: float
    # 主字段诊断 / 次字段诊断 / shape / 升降档动作
    ...
```

`FeaturePackage.anchor: AnchorFeature | None` 字段新增.

### 4.2 · 新增算法模块

**重写** `src/features/anchor.py`:
- `build_anchor_feature(photos)` 调 ADR-0013 `_two_tier_cluster.build_two_tier_feature` 工具
- primary_extractor = `p.meaning_anchors`, secondary_extractor = `p.semantic_facts.object_anchors`
- shape_mapper = AnchorShape (跟 ThemeShape 对称)

零额外代码, 几乎全是工具调用.

### 4.3 · 配置

新增 `config/path_b_anchor.yaml`.

### 4.4 · 调用方

- `assemble.py` 调 `build_anchor_feature(photos)` 替代 `compute_anchor_score`
- `bands.py::compute_bands` 中 `Bands.anchor` 直读 `AnchorFeature.band`

### 4.5 · 测试

`tests/unit/test_features_anchor.py` 新建, 8 个 Case 跟 theme 对称.

---

## 5 · 回滚条件

跟 ADR-0013 §5 同, anchor 阈值独立调.

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-008 §8e (合并 set 推荐) | 老推荐 | **修订**: 改为分层 (meaning 主 + object 次) |
| OQ-009 §9d | 待决 | **关闭** (ADR-0014 实现分层 cluster + 升降档) |
| **OQ-025 (新增)** | — | ADR-0014 接受边界 v0.2 真实数据验证 (5 子问题) |

---

## 7 · 后续动作

跟 ADR-0013 同节奏, anchor 在 theme 提取 `_two_tier_cluster.py` 通用工具后实施.
