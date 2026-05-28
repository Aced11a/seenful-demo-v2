# ADR-0023 · path B theme/subject MAX-OR + 泛词 stoplist

**状态**: accepted
**日期**: 2026-05-20
**修订**: [ADR-0013](./0013-path-b-theme-two-tier-cluster.md) (path B theme 双层字段判定)
**相关**: [ADR-0022](./0022-th0-multi-parallel-clusters-medium.md)

---

## 一、问题

ADR-0013 的双层字段算法是**主优先, 次救档**: 主字段 (`theme_tags`) 先判 band, 仅在主 medium (TH.2/TH.3) 段时才查次字段 (`main_subjects`) 做升降档. 主 weak (TH.4) 直接判完, 次字段废.

### 暴露问题: A6 牡丹 30 天生长 8 张

- `theme_tags` 词汇纵向散布: `bud / pink_petal / peony / wilting / fallen_petals / new_growth / foliage` — Qwen embedding cluster 0.75 下散成 18 个簇, primary_coverage=0.0 → **TH.4 weak**
- `main_subjects` 词汇横向稳定: `bud / leaf / branch / flower / petal / soil` — Qwen 聚成 2 簇 `[branch,leaf]` (hit=5/8=0.625) + `[flower,petal,foliage]` (hit=4/8=0.5), coverage=1.0 → **若单跑能 strong**
- 但 ADR-0013 主弱时不查次 → 用户拍 8 张同一株牡丹的不同阶段, 算法识别不出. 这是相册核心场景之一.

### 根因

theme_tags vs main_subjects **语义颗粒度不可比**:
- theme_tags 是"主题/氛围词" (lakeside / sunset / pink_petal / wilting), 语义粗细随用户场景变化大
- main_subjects 是"主体物词" (flower / leaf / car / person), 颗粒度稳但易出泛词

"主优先" 的设计预设 theme_tags 永远更可信, 但实测两个字段**没有先后之分**, 应平起平坐取更强者. 同时 main_subjects 出泛词 (person/car) 时易假阳.

---

## 二、决策

**MAX-OR + 泛词 stoplist + 保留老 Phase 3 升降档**

### 2.1 · 算法变更

| 阶段 | 老 (ADR-0013) | 新 (本 ADR) |
|---|---|---|
| Phase 1 | 主字段聚类 | 不变 |
| Phase 2 | 主 band (TH.0~TH.5 6 行 grid) | 不变 |
| Phase 3 | 仅 TH.2/TH.3 触发, 次字段升降档 | **保留**, 输出 `theme_band` |
| Phase 4 (新) | — | **subject single-layer 跑出 subject_band** (TH.1~TH.5 5 行, **subject 不启 TH.0**) |
| Phase 5 (新) | — | **stoplist cap**: subject 主簇任一成员命中泛词 → subject_band cap 至 medium |
| Phase 6 (新) | — | **MAX 取**: `final_band = max(theme_band, subject_band)` (band 序数, 同档取 theme) |

### 2.2 · rule_fired 命名 (后缀)

| 哪个字段赢 | rule_fired |
|---|---|
| theme 赢或同档 | `TH.x` 或 `TH.x+secondary_boost/demote` (老格式, **不变**) |
| subject 单跑赢 | **`TH.x.subject`** — 新后缀标记 subject 主导 (`x` 是 subject 跑出的 rule 编号) |
| subject 被 stoplist cap | `TH.x.subject+stopword_cap` |

例:
- A6 实测: theme=weak(TH.4), subject=strong(TH.1) → final=strong, rule_fired=**`TH.1.subject`**
- 上海开会 + 苏州游 (B5): theme=TH.0 medium, subject 也类似 → final=medium, rule_fired=`TH.0` (theme 主导 + medium 同档时取 theme)

### 2.3 · 泛词 stoplist (config 化)

`config/path_b_theme.yaml::subject_stopword_blocklist`:

```yaml
subject_stopword_blocklist:
  - person
  - people
  - food
  - car
  - vehicle
  - table
  - building
  - animal
  - object
  - thing
  - item
  - room
```

**触发规则**: subject 主簇 (`subject_theme_clusters` 任一) 若**任一成员词**命中 stoplist → subject_band cap 至 medium (不能 strong).

**理由**: 泛词高频出现于不同场景, 5 张完全无关照片都可能有 `person` / `car` → main_subjects coverage 假阳. cap medium 让"主+次都强"才能升 strong, 单泛词不够.

### 2.4 · 设计选择记录

| 选 | 决定 | 备选 (放弃理由) |
|---|---|---|
| A1 | rule_fired 后缀 `.subject` | A3 新字段 `dominant_field` (rule_fired 不破但看板要双读) |
| B1 | band 序数 MAX, 同档取 theme | B2 coverage 数值 MAX (跨字段语义粒度不可比) |
| C2 | 保留老 Phase 3 + 再 MAX | C1 替换 Phase 3 (老升降档对主 medium 有用, 删了浪费证据) |
| D | stoplist cap medium | 无 cap (放任泛词假阳) / IDF 权重 (复杂度高, demo 阶段不引入) |
| E2 | subject 不启 TH.0 | E1 subject 启 TH.0 (A6 拿不到 strong, 跟用户意图冲突) |

### 2.5 · 不变性

1. 老 TH.0~TH.5 主 grid 不变
2. 老 Phase 3 升降档逻辑不变
3. ThemeShape 枚举不加 (rule_fired 后缀已经标 dominant)
4. subject 不启 TH.0 — subject 多并列簇直接走 TH.1 strong
5. 仅 path B theme 改, anchor/emotional 不动 (anchor 是 meaning + object 双层, 语义关系不同)
6. stoplist 是配置化, 不在代码硬编码 (CLAUDE.md 第 3 条)

---

## 三、Why C2 (保留 Phase 3 + 再 MAX)

老 Phase 3 升降档语义: "主 medium 时, 次字段 ≥2/3 是**共识证据** → 升 strong; 次散是**反证** → 降 weak"

例: theme=4 lakeside + 1 urban (TH.2 medium), main_subjects=[湖面 × 5] (一致) → Phase 3 升 strong.

如果直接 C1 替换为 MAX-OR:
- theme single-layer: 4/5 coverage 0.8 → TH.2 medium
- subject single-layer: [湖面 × 5] coverage 1.0 → TH.1 strong  
- MAX → strong ✓ (结果一致)

但语义不同: 老 Phase 3 表达"主+次共同强 → 升", 而 MAX-OR 表达"任一强即可". 风险:
- theme=[lakeside × 4, urban × 1], subject=[湖面 × 5] → 都升 strong (一致) ✓
- theme=[lakeside × 4, urban × 1], subject=[湖面 × 4, 楼 × 1] (主 + 次都散) → 老 Phase 3 不升 + MAX subject 也 TH.2 medium → 不升 ✓
- theme=[lakeside × 4, urban × 1], subject=[人 × 5] (主散 + 泛词次"强") → 老 Phase 3 不升 (secondary_action=boost 但泛词?) — 老逻辑不识别泛词 → MAX subject 单跑 TH.1 strong **被 stoplist cap medium** → MAX 仍 medium ✓

C2 (保留 Phase 3 再 MAX) 比 C1 (纯 MAX) 多一层"主+次共识" 路径, 让"主散 + 次稳" 仍能升档 (Phase 3 不动), 同时 MAX 救主完全 weak 的场景. 双轨并行, 互不干扰.

---

## 四、ThemeFeature 字段变化

新加 (`src/contracts/features.py`):

```python
class ThemeFeature(BaseModel):
    # ... 老字段全保留 ...
    
    # ADR-0023 新增: subject single-layer 诊断
    subject_band: Optional[BandLevel] = None         # subject 单跑得的 band (TH.1~TH.5)
    subject_coverage: Optional[float] = None         # subject single-layer coverage
    subject_cluster_count: Optional[int] = None
    subject_theme_clusters: list[list[str]] = []
    subject_hit_rates: list[float] = []
    subject_stoplist_capped: bool = False            # 是否被泛词 cap
    subject_stoplist_hits: list[str] = []            # 命中的泛词 (落痕)
    dominant_field: Literal["theme", "subject"] = "theme"  # 哪个赢 (信息字段, 不入 rule_fired)
```

⚠ `dominant_field` 字段化保留 (跟 A3 同思路), 但 **rule_fired 也加后缀** (按 A1) — 双重落痕, 看板 + 真值表两边都能读.

---

## 五、影响

### 5.1 · 测试期望变化

| Case | 老 (ADR-0013) | 新 (本 ADR) |
|---|---|---|
| A6 牡丹 30 天 8 张 | theme=weak | **theme=strong, dominant=subject, rule=TH.1.subject** |
| [lakeside × 4, urban × 1] + [湖面 × 5] (B 主弱+次救) | TH.2+secondary_boost strong | 同 (Phase 3 仍命中) |
| [lakeside × 5] + skip | TH.1 strong | 同 |
| [lakeside × 4, urban × 1] + [人 × 5] (假阳 case) | TH.2+secondary_boost strong (老 bug) | TH.2 medium (subject 被 cap, Phase 3 stoplist 也需要 cap... ⚠ 见下) |

⚠ **Phase 3 升降档也需要应用 stoplist** 否则老 bug: subject=[人 × 5] 仍触发 Phase 3 boost. 修法: Phase 3 算 secondary_coverage 时排除命中 stoplist 的主簇.

### 5.2 · golden / scenarios

跨文档矩阵触发更新:
- docs/19 (theme spec) — Phase 4+5+6 加描述
- docs/02 (data contracts) — ThemeFeature 加字段
- config/path_b_theme.yaml — stoplist + subject_band
- src/contracts/features.py — 字段
- src/features/theme.py — 算法
- tests/unit/test_features_theme.py — A6 + stoplist 假阳 case
- docs/00_index.md — ADR 链接

---

## 六、不做

- 不改 anchor (ADR-0014) — anchor 双层是 meaning + object, 语义关系不同 (meaning 包含 object), 不是平行字段
- 不改 emotional (ADR-0015) — 单层, 无次字段
- 不引入 IDF / 词频权重 (demo 阶段保持简单, 真实数据上线后留 OQ)
- 不动 ThemeShape 枚举 (rule_fired 后缀已够标识)
- stoplist 不接 LLM 动态学习 — 配置化, 上线后人工迭代

---

## 七、Open Questions

- OQ-032: stoplist 词集是否合适? 真实数据上线后, 看 main_subjects top-100 词频, 决定加/删 (有可能 "flower" 在花艺场景也是泛词, 但牡丹 case 又是关键词 — 上下文相关性问题).
- OQ-033: 是否引入"theme+subject 一致性 boost"? 当 dominant_field=subject 且 theme=medium 时, 是否额外+0.1 confidence? 当前 demo 不做.
