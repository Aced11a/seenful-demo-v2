# 19 · 路径 B Theme 维度: 双层字段判定 (主 + 次 + 升降档)

> 路径 B (L2 主路径) theme 维度的算法规范.
> 算法依据: [ADR-0013](../decisions/0013-path-b-theme-two-tier-cluster.md).
> 仅覆盖路径 B. 路径 A theme (ADR-0008) 见 [docs/14](./14_theme_aggregation.md).
>
> ⚠ path A vs path B theme:
> - path A: 1 张新 vs 老相册指纹匹配 → ThemeMatchResult
> - path B: N 张照片自身内聚度 → ThemeFeature.band
> - 共享 MockEmbedder + `agglomerative_cluster_cosine` (ADR-0008), band 判定独立
>
> ⚠ **双层字段**: theme_tags 是主, main_subjects 是次. **仅主 medium 段触发次字段升降档**. scene_type 不入聚类.

---

## 一、变量定义

### 1.1 · 主字段 (theme_tags)

| 变量 | 定义 |
|---|---|
| N | 总照片数 |
| N_valid | 有 ≥ 1 个 theme_tag 的 photo 数 |
| tag_pool_primary | ⋃ p.theme_tags 跨 photos 去重 |
| primary_clusters | `agglomerative_cluster_cosine(vectors, 0.75)` 输出 |
| cluster.hit_rate | 命中该簇的 photo 数 / N |
| **theme_clusters** | **Top-K (K=3) by hit_count, 限 hit_count ≥ 2** (ADR-0024, 2026-05-21) |
| primary_coverage | ⋃ theme_clusters.member_photos / N |
| primary_outliers | 未命中 theme_cluster 的 photo |

⚠ **ADR-0024 v0.11 修订 (2026-05-21)**: 主簇过滤从 `hit_rate ≥ 0.5` 改为 **Top-K by hit_count (K=3)**, 修复 C8 复合场景天生输 (8 张 3 主题 hit=3,2,2 老 cov=0 新 cov=0.625). 详见 [ADR-0024](../decisions/0024-theme-topk-coverage.md).

### 1.2 · 次字段 (main_subjects, 仅 TH.2/TH.3 计算)

| 变量 | 定义 |
|---|---|
| tag_pool_secondary | ⋃ p.semantic_facts.main_subjects 跨 photos 去重 |
| secondary_clusters | 同主字段聚类算法 |
| secondary_theme_clusters | **Top-K (K=3) by hit_count, 限 hit_count ≥ 2** (ADR-0024) |
| secondary_coverage | ⋃ secondary_theme_clusters.photos / N |
| secondary_action | "none" / "boost" / "demote" |

---

## 二、算法步骤

⚠ **ADR-0023 v0.11 修订** (2026-05-20): Phase 3 老升降档**保留**, 新加 Phase 4-6: subject 字段 single-layer 跑 + 泛词 stoplist cap medium + MAX(theme_band, subject_band) 取最终. rule_fired 后缀 `.subject` 标记 subject 主导. 详见 [ADR-0023](../decisions/0023-theme-subject-max-or.md) + §2.5/§2.6.

### 2.1 · 整体流水线 (ADR-0023 升级)

```text
photos
  │
  ▼
┌────────────────────────────────────────────┐
│ Phase 1 · 主字段聚类                          │
│  · tag_pool = ⋃ p.theme_tags                │
│  · MockEmbedder + agglomerative_cluster 0.75 │
│  · 算 cluster.hit_rate                       │
│  · theme_clusters = ≥0.5 AND ≥2 张           │
│  · primary_coverage                          │
└────────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────────┐
│ Phase 2 · 主 band 判定 (6 行 grid)           │
└────────────────────────────────────────────┘
  │
  ├─ coverage=1.0 → TH.1 strong ✓
  ├─ 0.8 ≤ <1.0 → TH.2 medium-high ↓ Phase 3
  ├─ 0.5 ≤ <0.8 → TH.3 medium-low  ↓ Phase 3
  ├─ <0.5 → TH.4 weak ✓
  └─ N_valid ≤ 1 → TH.5 none ✓
  │
  ▼ (TH.2 / TH.3 才进)
┌────────────────────────────────────────────┐
│ Phase 3 · 次字段升降档 (老逻辑保留)            │
│  · tag_pool = ⋃ p.main_subjects             │
│  · 算 secondary_coverage (排除 stoplist 主簇) │
│  · ≥ 2/3 → 升 strong (+secondary_boost)     │
│  · < 1/3 → 降 weak  (+secondary_demote)     │
│  · 中间 → 不动                              │
│  · 输出 → theme_band                         │
└────────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────────┐
│ Phase 4 · subject single-layer (ADR-0023)   │
│  · 同算法跑 main_subjects → 5 行 grid       │
│  · TH.1~TH.5 (subject 不启 TH.0)            │
│  · 输出 subject_band                        │
└────────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────────┐
│ Phase 5 · 泛词 stoplist cap (ADR-0023)      │
│  · subject 主簇任一成员命中 stoplist        │
│  · subject_band cap 至 medium               │
│  · 落痕 subject_stoplist_hits               │
└────────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────────┐
│ Phase 6 · MAX-OR (ADR-0023)                 │
│  · final_band = max(theme_band, subject_band)│
│  · 序数: strong > medium > weak > none      │
│  · 同档取 theme (dominant_field=theme)      │
│  · subject 赢: rule_fired 加 `.subject`     │
└────────────────────────────────────────────┘
  │
  ▼
ThemeFeature.band (4 档终值) + dominant_field
```

### 2.2 · 主 grid (6 行, ADR-0022 v0.10 加 TH.0)

| # | 触发条件 | primary_band | type | 触发次? |
|---|---|---|---|---|
| **TH.0** | cluster_count ≥ 2 AND coverage = 1.0 AND **存在簇 hit_rate < 1.0** | **medium** | **mixed** | ❌ |
| TH.1 | coverage = 1.0 AND (cluster_count==1 OR 所有簇 hit_rate=1.0) | **strong** | thematic | ❌ |
| TH.2 | **0.7 ≤ coverage < 1.0** (ADR-0024 改 0.8→0.7) | medium-high | thematic | ✅ |
| TH.3 | 0.5 ≤ coverage < 0.7 | medium-low | thematic | ✅ |
| TH.4 | coverage < 0.5 OR cluster_count=0 | **weak** | thematic | ❌ |
| TH.5 | N_valid ≤ 1 | **none** | weak | ❌ |

⚠ **ADR-0022 v0.10 修订** (2026-05-20): TH.1 加 `primary_cluster_count == 1` 约束. 多并列主簇 (eg. 上海开会 3 张 + 苏州游 3 张) 覆盖 100% 时, 走 TH.0 medium 而非 TH.1 strong, 因为属"mixed" 不是"thematic". 详见 [ADR-0022](../decisions/0022-th0-multi-parallel-clusters-medium.md).

### 2.3 · 次字段升降档 (Phase 3)

| secondary_coverage | 调整 | 最终 band | rule_fired |
|---|---|---|---|
| ≥ 2/3 ≈ 0.667 | 升 1 档 | strong | `TH.N+secondary_boost` |
| 1/3 ≤ < 2/3 | 不动 | medium | `TH.N` |
| < 1/3 ≈ 0.333 | 降 1 档 | weak | `TH.N+secondary_demote` |

### 2.4 · 完整 band → rule_fired 映射 (theme_band 输出, Phase 3 后)

| primary | secondary | theme_band | rule_fired (Phase 3 输出) |
|---|---|---|---|
| **TH.0** | (skip) | **medium** | `TH.0` |
| TH.1 | (skip) | strong | `TH.1` |
| TH.2 | boost | strong | `TH.2+secondary_boost` |
| TH.2 | 不动 | medium | `TH.2` |
| TH.2 | demote | weak | `TH.2+secondary_demote` |
| TH.3 | boost | strong | `TH.3+secondary_boost` |
| TH.3 | 不动 | medium | `TH.3` |
| TH.3 | demote | weak | `TH.3+secondary_demote` |
| TH.4 | (skip) | weak | `TH.4` |
| TH.5 | (skip) | none | `TH.5` |

### 2.5 · subject single-layer + stoplist (Phase 4-5, ADR-0023)

subject single-layer 跑 **5 行 grid** (无 TH.0):

| # | 触发条件 | subject_band |
|---|---|---|
| TH.1 | subject_coverage = 1.0 | **strong** |
| TH.2 | 0.8 ≤ < 1.0 | medium-high |
| TH.3 | 0.5 ≤ < 0.8 | medium-low |
| TH.4 | < 0.5 | **weak** |
| TH.5 | subject N_valid ≤ 1 | **none** |

**Phase 5 stoplist cap**: subject_theme_clusters 任一簇任一成员命中 `subject_stopword_blocklist` → subject_band 强制 cap 至 **medium**, 落痕 `subject_stoplist_hits` 数组.

⚠ Phase 3 老升降档也要排除 stoplist 主簇 (避免 [人 × 5] 误触发 secondary_boost).

### 2.6 · MAX-OR (Phase 6, ADR-0023)

band 序数: `strong=3 > medium=2 > weak=1 > none=0`

```python
final_band = max(theme_band, subject_band)
if theme_band_ord >= subject_band_ord:
    dominant_field = "theme"
    rule_fired = <Phase 3 输出>             # eg. "TH.2+secondary_boost"
else:
    dominant_field = "subject"
    rule_fired = f"{subject_rule}.subject"  # eg. "TH.1.subject"
    if subject_stoplist_capped:
        rule_fired += "+stopword_cap"
```

**完整 rule_fired 词典 (含 ADR-0023)**:

| dominant | 例 | 语义 |
|---|---|---|
| theme | `TH.0` | 多并列主簇 → medium |
| theme | `TH.1` | theme 全员一致 → strong |
| theme | `TH.2+secondary_boost` | theme 主导 + subject 共识 → 升 strong |
| theme | `TH.3+secondary_demote` | theme 弱主导 + subject 散 → 降 weak |
| **subject** | **`TH.1.subject`** | **theme 弱, subject 全员一致 → strong (A6 case)** |
| subject | `TH.2.subject` | theme 弱, subject 80-99% 主导 → medium |
| subject | `TH.1.subject+stopword_cap` | subject 强但泛词 → cap medium |

⚠ subject 赢时 dominant_field=subject **覆盖**老 secondary_action, 不再有 secondary_boost/demote 后缀 (这是 theme 主导时的标记).

---

## 三、ThemeShape 枚举

| 值 | 对应 primary_band | 语义 |
|---|---|---|
| `multi_parallel_clusters` | **TH.0** | 多并列主簇覆盖 100% 但各占不同子集 (mixed, ADR-0022) |
| `full_coverage_themed` | TH.1 | 主字段全员同主题簇 |
| `dominant_themed` | TH.2 | 主字段 80%-99% 主导 |
| `partial_themed` | TH.3 | 主字段 50%-79% 主导 |
| `no_dominant_theme` | TH.4 | 主字段散乱 |
| `no_theme_signal` | TH.5 | 无信号 |

⚠ 升降档不影响 shape, 仅 rule_fired 后缀.

---

## 四、Case 验证

详见 `archive/specs/Path_B_Theme_Aggregation_Spec.md` v0.3 §五. 摘要 (ADR-0023 新增 J/K case):

| Case | theme_tags | main_subjects | theme_band | subject_band | final | rule_fired |
|---|---|---|---|---|---|---|
| A 全员同 | [lake × 5] | — | strong (TH.1) | — | strong | TH.1 |
| B 主弱+次救 | [lake × 4, urban × 1] | [湖面 × 5] | strong (TH.2+boost) | strong (TH.1) | strong | TH.2+secondary_boost |
| C 主弱+次拉降 | [lake × 4, urban × 1] | 散 | weak (TH.2+demote) | weak | weak | TH.2+secondary_demote |
| D 主 TH.3 + 次降 | [lake × 3, urban × 2] | 散 | weak (TH.3+demote) | weak | weak | TH.3+secondary_demote |
| E 主 TH.3 + 次中 | [lake × 3, urban × 2] | [湖面 × 3, 楼 × 2] | medium (TH.3) | medium | medium | TH.3 |
| F 全散 | 5 张各异 | (skip) | weak (TH.4) | — | weak | TH.4 |
| G 2 张二选一 | [lake] [urban] | (skip) | weak (TH.4) | — | weak | TH.4 |
| H 全空 | — | — | none (TH.5) | none | none | TH.5 |
| **J A6 牡丹 30 天** | 18 散簇 (cov=0) | [branch,leaf]+[flower,petal,foliage] cov=1.0 | **weak (TH.4)** | **strong (TH.1)** | **strong** | **TH.1.subject** |
| **K subject 假阳** | [lake × 4, urban × 1] | [person × 5] | medium (TH.2) | medium (TH.1+cap) | medium | TH.2 |

---

## 五、不变性

1. band 4 档终值, 真值表 28 条直读
2. 双阈值 (聚类 0.75 + 主题 0.5) + hit_count ≥ 2
3. **strong 唯一通道**: TH.1 (coverage=1.0) 或 TH.2/TH.3 + secondary ≥ 2/3
4. **次字段仅 TH.2/TH.3 触发** (主 strong/weak/none 不算次)
5. coverage 都基于 N
6. outlier 不影响 band, 仅落痕
7. N < 2 → none (红线 §3)
8. 复用 ADR-0008 cluster_tags + MockEmbedder
9. rule_fired 必填
10. 多主题相册自然存在 (theme_clusters 无上限)

---

## 六、配置

完整见 `config/path_b_theme.yaml`. 关键:

| 字段 | 默认 |
|---|---|
| `primary_field` | "theme_tags" |
| `primary_hit_rate_threshold` | 0.5 |
| `min_hit_count` | 2 |
| `primary_band_thresholds.strong_coverage` | 1.0 |
| `primary_band_thresholds.medium_high` | 0.8 |
| `primary_band_thresholds.medium_low` | 0.5 |
| `secondary_field` | "main_subjects" |
| `secondary_band_adjust.boost_threshold` | 0.667 |
| `secondary_band_adjust.demote_threshold` | 0.333 |
| `fallback.n_valid_min` | 1 |

---

## 七、与 ADR-0008 / ADR-0012 关系

| | ADR-0008 path A | ADR-0012 path B event | **ADR-0013 path B theme (本)** |
|---|---|---|---|
| 算法 | 1 vs N 匹配 | distribution + primary_share | **双层 cluster coverage** |
| 双门槛 | — | event=1.0 + activity≥2/3 (严档) | **主 medium + 次 ≥ 2/3 (模糊段)** |
| 工具复用 | 自实现 | aggregate_event | **MockEmbedder + cluster_tags** |
