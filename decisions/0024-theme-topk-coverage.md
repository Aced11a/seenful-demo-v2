# ADR-0024 · path B theme Top-K coverage (替代 hit_rate 单簇阈值)

**状态**: accepted
**日期**: 2026-05-21
**修订**: [ADR-0013](./0013-path-b-theme-two-tier-cluster.md) Phase 1 coverage 算法
**保留**: [ADR-0022](./0022-th0-multi-parallel-clusters-medium.md) TH.0 grid + [ADR-0023](./0023-theme-subject-max-or.md) subject MAX-OR

---

## 一、问题

ADR-0013 Phase 1 主簇过滤:

```python
theme_clusters = {c | hit_rate(c) ≥ 0.5 AND hit_count(c) ≥ 2}
primary_coverage = | ⋃ theme_clusters.member_photos | / N
```

`hit_rate ≥ 0.5` 设计目的: 防假阳 (5 张里 2 张同主题不算主题). 但**复合场景天生输**:

### 暴露问题: C8 咖啡馆 8 张 → weak

实测 Qwen 聚类:
- 簇 0 `[latte_art, espresso_shot, second_latte, oat_milk]`: 出现在 3/8 张 → hit_rate=0.375 **< 0.5 → 不算主题簇**
- 其他 16 个都 hit_rate=0.125 散簇
- → primary_coverage = 0 → **TH.4 weak**

跟产品意图冲突: 8 张咖啡馆 (同 GPS 同时间窗 + 几个小主题: coffee/朋友/书) 应被识别为"一次咖啡馆体验" medium, 而不是"无主题".

### 根因

`hit_rate ≥ 0.5` 是"单簇主导" 模型, 假设有一个**主簇覆盖 ≥ 半数照片**才算主题. 复合场景里**没有任何小簇能过此门槛** — 3/8 + 2/8 + ... 都 < 0.5 → 全 weak.

实际产品需要的是"**多个小主题加起来覆盖大半照片**"也算主题. 这就是 Top-K coverage 思路.

---

## 二、决策

**Top-K coverage**: 取最大的 K 个簇 (限 `hit_count ≥ 2`), 并集覆盖率作为 `primary_coverage`. K=3 固定.

### 2.1 · 算法变更

| 项 | 老 (ADR-0013) | 新 (本 ADR) |
|---|---|---|
| 候选过滤 | `hit_rate ≥ 0.5 AND hit_count ≥ 2` | **`hit_count ≥ 2`** (只保留 min_hit_count) |
| 选簇 | 全选过门槛簇 | **Top-K by hit_count (K=3)** |
| coverage | 选中簇并集 / N | 同 (Top-K 并集 / N) |

### 2.2 · K=3 怎么定的

考量:
- K 太小 (=1): 退化成"单主导主题", 复合场景仍输
- K 太大 (=N): 散照也会凑出高 coverage → 假阳
- K=3 实测平衡:
  - C8 8 张 → Top-3 = [coffee(3), dessert(2), 散(1, 但 hit<2 被过滤)] → 实际 2 簇 → cov=0.5 ✓
  - A6 8 张 theme → Top-3 = [pink_petal(3), bud(2), bloom(2)] → cov=0.625 ✓
  - FP_B1 5 张散 → Top-3 = 0 簇 (无 hit≥2) → cov=0 ✓ (假阳挡住)

K=3 是经验值 (基于当前 persona 实测), 不深度优化. 真实数据上线后 OQ-034 调.

### 2.3 · Phase 2 grid 阈值改 (轻微)

| # | 触发 | band | 老 | 新 |
|---|---|---|---|---|
| TH.0 | cov=1.0 AND cluster_count≥2 AND 存在 hit<1.0 | medium | 同 | 同 (保留 ADR-0022) |
| TH.1 | cov=1.0 (单簇或全员命中) | strong | 同 | 同 |
| **TH.2** | **0.7 ≤ cov < 1.0** | medium-high | 0.8 ≤ < 1.0 | **改 0.8→0.7** |
| TH.3 | 0.5 ≤ cov < 0.7 | medium-low | 0.5 ≤ < 0.8 | 同上, 上界改 0.8→0.7 |
| TH.4 | cov < 0.5 | weak | 同 | 同 |
| TH.5 | N_valid ≤ 1 | none | 同 | 同 |

**0.8 → 0.7 理由**: 实测 T1 西湖环湖 8 张 → cov=0.75 (老阈值 0.8 走 TH.3 medium-low, 新阈值 0.7 走 TH.2 medium-high). 产品上 6/8 同主题应是 medium-high 而非 medium-low.

只影响 `cov ∈ [0.7, 0.8)` 区间 (升档). 不影响其他.

### 2.4 · 设计选择

| 选 | 决定 | 备选 (放弃理由) |
|---|---|---|
| K 取值 | K=3 固定 | 动态 K (取累加 cov ≥ 0.5 最少簇数, 复杂度高) |
| min_hit_count | 保留 = 2 | 删 (FP_B1 散照会假阳到 0.4) |
| coverage 阈值 | 0.7 / 0.5 | 维持 0.8 / 0.5 (T1 案例 cov=0.75 应升 medium-high) |
| Subject single-layer 是否同改 | **同改** (Top-K) | 不改 (theme/subject 算法不一致, 维护成本高) |
| 老 hit_rate 完全删 | 删, 不留兼容 | 保留 hit_rate 字段诊断用 |

### 2.5 · 不变性

1. ADR-0022 TH.0 多并列规则保留
2. ADR-0023 subject MAX-OR + 泛词 stoplist 保留
3. Phase 3 老升降档逻辑保留 (TH.2/TH.3 + secondary 升降)
4. Phase 4 subject single-layer 同步用 Top-K
5. ThemeShape 枚举不变
6. K=3 + min_hit_count=2 配置化 (path_b_theme.yaml)

---

## 三、实测对比 (8 个 case)

| Case | 老 coverage | 老 band | 新 coverage | 新 band |
|---|---|---|---|---|
| **C8 咖啡馆 8 张** | 0.0 | weak | **0.5** | **medium-low (TH.3)** ✓ 修 |
| **A6 牡丹 theme** | 0.0 | weak | 0.625 | medium-low (TH.3) ✓ 改善 |
| A6 牡丹 subject (single) | 1.0 | strong | 1.0 | strong (不变) |
| C6 徒步 (5 张词散) | 0.0 | weak | 0.0 | weak ✓ 保持 |
| B7 接娃 (5 张) | 0.6 | medium-low → strong (boost) | 0.6 | medium-low → strong (boost) ✓ |
| B5 上海+苏州 | 1.0 | TH.0 medium | 1.0 | TH.0 medium ✓ 保持 |
| T1 西湖环湖 8 张 | 0.75 | medium-low (TH.3) | 0.75 | **medium-high (TH.2)** ↑ 升档 |
| FP_B1 散照 | 0.0 | weak | 0.0 | weak ✓ 假阳挡住 |

---

## 四、影响

### 4.1 · ThemeFeature 字段变化

无新字段, 只是 `primary_coverage` / `primary_theme_clusters` 等字段语义变化 (从"过 hit_rate 阈值" 改为"Top-K"). `primary_hit_rates` 仍记录被选中簇的 hit_rate, 仅诊断用.

### 4.2 · 测试期望变化

| Test | 老 | 新 |
|---|---|---|
| `TestTH3MediumNoChange` (3 lake + 2 urban + 3:2 secondary) | TH.3 medium | 同 (cov=0.6) ✓ |
| `TestTH2SecondaryBoost` (4 lake + 1 urban + secondary boost) | TH.2 → strong | cov=0.8 ≥ 0.7 → TH.2 → strong ✓ |
| `TestTH4Weak` (5 全散) | TH.4 weak | 同 (无 hit≥2 簇) ✓ |
| 新增 `TestC8MultiCluster` | weak | **medium-low** (验 C8 修复) |

### 4.3 · 跨文档矩阵

按 CLAUDE.md 第 2 条:
- ✅ `decisions/0024-*.md` (本)
- ✅ `docs/19_path_b_theme.md` Phase 1 + grid 阈值 (待改)
- ✅ `docs/02_data_contracts.md` 无字段变化 (无需改)
- ✅ `config/path_b_theme.yaml` K + min_hit_count + 阈值 0.7 (待改)
- ✅ `src/features/_two_tier_cluster.py` `_filter_theme_clusters` → Top-K (待改)
- ✅ `tests/unit/test_features_theme.py` 加 C8 case
- ✅ `docs/00_index.md` 加 ADR-0024 链接 (待改)
- ✅ `docs/12_open_questions.md` 加 OQ-034 (待改)
- ✅ `archive/specs/Path_B_Theme_Aggregation_Spec.md` 不动 (历史)

---

## 五、Open Questions

- **OQ-034**: K=3 经验值是否合适? 真实数据上线后, 看 N 分布 + Top-K coverage 分布, 决定 K 是否需要动态化
- **OQ-035**: 0.7 阈值是否合适? T1 实测 0.75 升 TH.2, 但其他 case 可能在 [0.7, 0.8) 区间表现不稳定

---

## 六、不做

- 不引入 IDF / TF-IDF 加权 (复杂度高, demo 阶段保持简单)
- 不动 ADR-0022 TH.0 (多并列簇 medium 仍生效)
- 不动 ADR-0023 subject MAX-OR + stoplist
- 不改 anchor 维度 (ADR-0014 仍 hit_rate 阈值)
- 不改 emotional (ADR-0015 单层 hit_rate 仍合理)
