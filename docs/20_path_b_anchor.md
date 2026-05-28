# 20 · 路径 B Anchor 维度: 双层字段判定 (主 + 次 + 升降档)

> 路径 B (L2 主路径) anchor 维度的算法规范.
> 算法依据: [ADR-0014](../decisions/0014-path-b-anchor-two-tier-cluster.md).
> 仅覆盖路径 B. 路径 A anchor 待 OQ-008 §8e (修订后 = 分层方案).
>
> ⚠ **跟 ADR-0013 theme 同算法骨架**, 仅字段不同:
> - 主字段 = `meaning_anchors` (中文短语, 抽象意象)
> - 次字段 = `semantic_facts.object_anchors` (具体物体)
> - **修订 OQ-008 §8e 老推荐**: 不再合并 set, 改主次分层
>
> ⚠ anchor 是辅证 (C/E 系列降档), 真值表 A 系列无 anchor=强单独成集. 但仍保留 strong 档以备 E 系列升档逻辑.

---

## 一、变量定义

### 1.1 · 主字段 (meaning_anchors)

| 变量 | 定义 |
|---|---|
| N | 总照片数 |
| N_valid | 有 ≥ 1 个 meaning_anchor 的 photo 数 |
| tag_pool_primary | ⋃ p.meaning_anchors 跨 photos 去重 |
| primary_clusters | `agglomerative_cluster_cosine(vectors, 0.75)` 输出 |
| cluster.hit_rate | 命中该簇的 photo 数 / N |
| anchor_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 的簇 |
| primary_coverage | ⋃ anchor_clusters.member_photos / N |
| primary_outliers | 未命中 anchor_cluster 的 photo |

### 1.2 · 次字段 (object_anchors, 仅 AN.2/AN.3 计算)

| 变量 | 定义 |
|---|---|
| tag_pool_secondary | ⋃ p.semantic_facts.object_anchors 跨 photos 去重 |
| secondary_clusters | 同主字段聚类 |
| secondary_anchor_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 |
| secondary_coverage | ⋃ secondary_anchor_clusters.photos / N |
| secondary_action | "none" / "boost" / "demote" |

---

## 二、算法步骤

### 2.1 · 整体流水线 (同 docs/19 §2.1, 仅字段名换)

```text
Phase 1 · meaning_anchors 聚类 → primary_coverage
Phase 2 · 主 band 判定 (5 行 grid AN.1~AN.5)
Phase 3 · 仅 AN.2/AN.3 → object_anchors 聚类 → secondary_coverage 升降档
```

### 2.2 · 主 grid (5 行)

| # | primary_coverage | primary_band | 触发次? |
|---|---|---|---|
| AN.1 | = 1.0 | **strong** | ❌ |
| AN.2 | 0.8 ≤ < 1.0 | medium-high | ✅ |
| AN.3 | 0.5 ≤ < 0.8 | medium-low | ✅ |
| AN.4 | < 0.5 OR cluster_count=0 | **weak** | ❌ |
| AN.5 | N_valid ≤ 1 | **none** | ❌ |

### 2.3 · 升降档 (Phase 3)

| secondary_coverage | 调整 | 最终 band | rule_fired |
|---|---|---|---|
| ≥ 2/3 | 升 1 档 | strong | `AN.N+secondary_boost` |
| 1/3 ≤ < 2/3 | 不动 | medium | `AN.N` |
| < 1/3 | 降 1 档 | weak | `AN.N+secondary_demote` |

### 2.4 · 完整 band → rule_fired 映射

跟 docs/19 §2.4 同结构, 仅前缀 AN.

---

## 三、AnchorShape 枚举

| 值 | 对应 primary_band |
|---|---|
| `full_coverage_anchored` | AN.1 strong |
| `dominant_anchored` | AN.2 medium-high |
| `partial_anchored` | AN.3 medium-low |
| `no_dominant_anchor` | AN.4 weak |
| `no_anchor_signal` | AN.5 none |

---

## 四、Case 验证

详见 `archive/specs/Path_B_Anchor_Aggregation_Spec.md` v0.3 §五. 摘要:

| Case | meaning | object | primary_cov | second_cov | 最终 |
|---|---|---|---|---|---|
| A 全员同 | [天光 × 5] | (skip) | 1.0 | — | strong |
| **B 主弱+次救** | [天光 × 4, 拥堵 × 1] | [湖面 × 5] | 0.8 | 1.0 ≥ 2/3 | **strong+boost** |
| **C 主弱+次拉降** | [天光 × 4, 拥堵 × 1] | 散 | 0.8 | < 1/3 | **weak+demote** |
| D 主 AN.3 + 次中 | [天光 × 3, 楼影 × 2] | [湖 × 3, 桥 × 2] | 0.6 | 0.6 中间 | medium |
| E 主 AN.3 + 次降 | [天光 × 3, 楼影 × 2] | 散 | 0.6 | 0 | weak+demote |
| F 主 AN.4 weak (不看次) | 全散 | (skip) | 0 | — | weak |
| G N_valid ≤ 1 | 全空 | — | — | — | none |

---

## 五、不变性

1. band 4 档终值
2. 双阈值 (聚类 0.75 + 主题 0.5) + hit_count ≥ 2
3. **strong 唯一通道**: AN.1 或 AN.2/AN.3 + secondary ≥ 2/3
4. **次字段仅 AN.2/AN.3 触发**
5. coverage 基于 N
6. outlier 不影响 band, 仅落痕
7. N < 2 → none (红线 §3)
8. **复用 ADR-0013 `_two_tier_cluster.py` 通用工具** (无重复实现)
9. rule_fired 必填
10. **meaning_anchors 是主, object_anchors 是次** (v0.3 修订 OQ-008 §8e)

---

## 六、配置

完整见 `config/path_b_anchor.yaml`. 关键 (跟 theme 同结构, 字段名换):

| 字段 | 默认 |
|---|---|
| `primary_field` | "meaning_anchors" |
| `primary_hit_rate_threshold` | 0.5 |
| `min_hit_count` | 2 |
| `primary_band_thresholds.strong_coverage` | 1.0 |
| `primary_band_thresholds.medium_high` | 0.8 |
| `primary_band_thresholds.medium_low` | 0.5 |
| `secondary_field` | "object_anchors" |
| `secondary_band_adjust.boost_threshold` | 0.667 |
| `secondary_band_adjust.demote_threshold` | 0.333 |
| `fallback.n_valid_min` | 1 |

---

## 七、与 ADR-0013 关系

| | ADR-0013 theme | **ADR-0014 anchor (本)** |
|---|---|---|
| 主字段 | theme_tags | meaning_anchors |
| 次字段 | main_subjects | object_anchors |
| 算法骨架 | 共享 | **`_two_tier_cluster.build_two_tier_feature` 通用工具** |
| 真值表权重 | 主载体 (A2 单独成集) | 辅证 (C/E 降档) |
| 输出范式 | 同 | 同 |

⚠ 实施依赖: ADR-0013 先落 (提取通用工具), ADR-0014 跟随 (调用工具).
