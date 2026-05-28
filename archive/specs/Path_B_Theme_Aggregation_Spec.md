# L2 Path B · Theme 维度判断规范

> **版本**: v0.3 (draft, 待 Ace 最终审核)
> **日期**: 2026-05-18
> **适用**: Seenful L2 Engine 路径 B (多张照片自身) theme 维度
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (写 ADR-0013 + 后续 docs/src/config/tests).
> **v0.3 改动**: 引入**双层字段判定** (Ace 2026-05-18). 主字段 (theme_tags) 跑 cluster + coverage 定主 band; **仅 medium 段** (TH.2/TH.3) 用次字段 (main_subjects) coverage ≥ 2/3 升 strong / < 1/3 降 weak. scene_type 不入聚类. 跟 ADR-0012 event-activity 范式神似但触发条件不同 (event 严档双门槛 / theme 模糊段双门槛).

---

## 一、背景

### 1.1 · 现状

`src/features/theme.py` v0.1: 字面 Jaccard 三路加权 (theme 50% + subject 40% + scene 10%), 严格交集 1 张离群 → 0, 无语义识别.

### 1.2 · 失败模式 (v0.1 spec 同)

- 1 张离群 → 严格 Jaccard 归零
- 同义不同字 (lakeside / 湖边 / water) → 无识别
- 单一主题强限制
- 主次字段权重混合 (0.5/0.4/0.1) 不直观

### 1.3 · A2 真值表约束

A2: `theme = 强 → bounds=[medium, strong], type=thematic` — theme 单独 strong 直接出小集. v0.3 strong 唯一通道: **主字段 coverage = 1.0**.

### 1.4 · v0.3 范式核心

```
主字段 (theme_tags) 决定主 band
   │
   ├─ coverage = 1.0          → strong
   ├─ 0.4 ≤ < 1.0             → medium 段 (TH.2/TH.3/TH.4 细分)
   │   └─ TH.2 / TH.3 时    → 次字段 (main_subjects) 升降档
   │       · 次 coverage ≥ 2/3 → 升 strong
   │       · 次 coverage < 1/3 → 降 weak
   │       · 中间                → 不动
   └─ < 0.4                    → weak / none
```

**为什么"仅 medium 段看次字段"**: strong (主 = 1.0) 已硬, 不需要次字段救; weak (主 < 0.4) 已散, 次字段救不动. **medium 是模糊地带, 次字段精调最有价值**.

---

## 二、核心算法范式

### 2.1 · 设计哲学

| 维度 | v0.2 | **v0.3** |
|---|---|---|
| 字段处理 | theme_tags + main_subjects 合并入 tag_pool 平等聚类 | **主 (theme_tags) 定主 band, 次 (main_subjects) 仅在 medium 段升降档** |
| 主次区别 | 隐式合并丢失 | **显式分层** (Ace 直觉: 两层级重要性不同) |
| 双门槛触发 | 不双门槛 | **主 band ∈ {TH.2, TH.3} 时双门槛** |
| 跟 ADR-0012 | 单层 cluster | **同范式 (主 + 次双层), 触发条件不同** |

### 2.2 · 三阶段流水线

```text
N 张照片
   │
   ▼
┌─────────────────────────────────────────────┐
│ Phase 1 · 主字段聚类                          │
│  · tag_pool_primary = ⋃ p.theme_tags        │
│  · 复用 ADR-0008 cluster_tags + 0.75         │
│  · 每 cluster 算 hit_rate                    │
│  · theme_clusters = hit_rate ≥ 0.5            │
│         AND hit_count ≥ 2                    │
│  · primary_coverage = ⋃ theme_cluster        │
│      photo / N                               │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ Phase 2 · 主 band 判定                       │
└─────────────────────────────────────────────┘
   │
   ├─ primary_coverage = 1.0       → strong (TH.1)
   ├─ 0.8 ≤ < 1.0                    → medium-high (TH.2) ←─┐
   ├─ 0.6 ≤ < 0.8                    → medium-low  (TH.3) ←─┤ Phase 3
   ├─ 0.4 ≤ < 0.6                    → weak-high  (TH.4)    │
   ├─ < 0.4 OR no theme_clusters     → weak       (TH.5)    │
   └─ N_valid ≤ 1                    → none       (TH.6)    │
                                                              │
   ▼                                                          ▼
┌─────────────────────────────────────────────┐
│ Phase 3 · 次字段升降档 (仅 TH.2/TH.3 触发) │
│  · tag_pool_secondary = ⋃ p.main_subjects   │
│  · 跑同算法 → secondary_coverage            │
│  · secondary_coverage ≥ 2/3 → 升 strong     │
│  · secondary_coverage < 1/3 → 降 weak       │
│  · 中间 [1/3, 2/3) → 不动 (medium)           │
└─────────────────────────────────────────────┘
```

### 2.3 · 与 ADR-0008 / ADR-0012 关系

| | ADR-0008 path A | ADR-0012 path B event | **ADR-0013 path B theme v0.3** |
|---|---|---|---|
| 算法本质 | 1 张 vs 老相册指纹匹配 | distribution + primary_share | **双层 cluster coverage** |
| 主+次门槛 | 无 | event=1.0 + activity≥2/3 (严档双门槛) | **主 medium + 次 ≥ 2/3 升 / < 1/3 降 (模糊段双门槛)** |
| 共享工具 | 自己写 | 复用 aggregate_event | **复用 cluster_tags + MockEmbedder** |

---

## 三、核心变量定义

### 3.1 · 主字段 (theme_tags)

| 变量 | 定义 |
|---|---|
| N | 总照片数 |
| N_valid | 有 ≥ 1 个 theme_tag 的 photo 数 |
| tag_pool_primary | ⋃ p.theme_tags 跨 photos 去重 |
| primary_clusters | 层次聚类后的簇 (cosine ≥ 0.75) |
| cluster.hit_rate | 命中该簇的 photo 数 / N |
| theme_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 |
| primary_coverage | ⋃ theme_clusters.photos / N |
| primary_outliers | 未命中任何 theme_cluster 的 photo |

### 3.2 · 次字段 (main_subjects)

仅 primary_band ∈ {TH.2, TH.3} 时计算:

| 变量 | 定义 |
|---|---|
| tag_pool_secondary | ⋃ p.main_subjects 跨 photos 去重 |
| secondary_clusters | 层次聚类同 (复用算法) |
| secondary_theme_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 |
| secondary_coverage | ⋃ secondary_theme_clusters.photos / N |

⚠ 主 band 不在 {TH.2, TH.3} 时, 次字段**不计算** (省 CPU + 落痕表为 None).

---

## 四、判定网格 (主 6 行 + 次字段升降档)

### 4.1 · 主字段 Grid (Phase 2)

| # | primary_coverage | theme_cluster_count | N_valid | primary_band | 触发次字段? |
|---|---|---|---|---|---|
| TH.1 | = 1.0 | ≥ 1 | — | **strong** | ❌ 已 strong |
| **TH.2** | **0.8 ≤ < 1.0** | ≥ 1 | — | medium | **✅ 看次字段** |
| **TH.3** | **0.6 ≤ < 0.8** | ≥ 1 | — | medium | **✅ 看次字段** |
| TH.4 | 0.4 ≤ < 0.6 | ≥ 1 | — | **weak** | ❌ 已 weak |
| TH.5 | < 0.4 OR cluster_count=0 | — | ≥ 2 | **weak** | ❌ 已 weak |
| TH.6 | — | — | ≤ 1 | **none** | ❌ 无信号 |

### 4.2 · 次字段升降档 (Phase 3, 仅 TH.2/TH.3)

| secondary_coverage | 调整 | 最终 band | rule_fired 后缀 |
|---|---|---|---|
| ≥ 2/3 ≈ 0.667 | 升 1 档 | **strong** | `+secondary_boost` |
| 1/3 ≤ < 2/3 | 不动 | **medium** | (无后缀) |
| < 1/3 ≈ 0.333 | 降 1 档 | **weak** | `+secondary_demote` |

**最终 band 仍只有 4 档** (strong/medium/weak/none), 真值表不变.

### 4.3 · 完整最终 band → rule_fired 映射

| 路径 | 主 band | 次字段动作 | 最终 band | rule_fired |
|---|---|---|---|---|
| 1 | TH.1 strong | (跳过) | strong | `TH.1` |
| 2 | TH.2 medium-high | 次升 | strong | `TH.2+secondary_boost` |
| 3 | TH.2 medium-high | 次不动 | medium | `TH.2` |
| 4 | TH.2 medium-high | 次降 | weak | `TH.2+secondary_demote` |
| 5 | TH.3 medium-low | 次升 | strong | `TH.3+secondary_boost` |
| 6 | TH.3 medium-low | 次不动 | medium | `TH.3` |
| 7 | TH.3 medium-low | 次降 | weak | `TH.3+secondary_demote` |
| 8 | TH.4 weak-high | (跳过) | weak | `TH.4` |
| 9 | TH.5 weak | (跳过) | weak | `TH.5` |
| 10 | TH.6 none | (跳过) | none | `TH.6` |

---

## 五、Case 验证

### Case A · 主字段 strong 不看次字段
```
theme_tags = [lakeside × 5]
主聚类: lake hit_rate=1.0 → primary_coverage=1.0 → TH.1 strong
(次字段不算)
→ 最终 strong, rule_fired="TH.1"
```

### Case B · 主字段 TH.2 + 次字段救升 strong (v0.3 关键)
```
theme_tags:
  P1-P4 [lakeside],  P5 [urban]
主聚类: lake hit_rate=0.8, urban=0.2
        theme_clusters={lake}, primary_coverage=0.8 → TH.2 medium-high

main_subjects:
  P1-P5 都含 [湖面]
次聚类: 湖面 hit_rate=1.0, secondary_coverage=1.0 ≥ 2/3 → 升档

→ 最终 strong, rule_fired="TH.2+secondary_boost"
```

⚠ 体感: 4 张明确 lake 主题 + 1 张 urban 异常, **但 main_subjects 全员"湖面"** → 实际 5 张都讲湖, urban 是 LLM 误标 → 升 strong 合理.

### Case C · 主字段 TH.2 + 次字段拉降 weak
```
theme_tags:
  P1-P4 [lakeside],  P5 [urban]
主聚类: lake hit_rate=0.8 → TH.2 medium-high, primary_coverage=0.8

main_subjects:
  P1 [湖面], P2 [树], P3 [桥], P4 [汽车], P5 [楼]
次聚类: 各自独立, hit_count 都 < 2 → 无主题簇
        secondary_coverage = 0 < 1/3 → 降档

→ 最终 weak, rule_fired="TH.2+secondary_demote"
```

⚠ 体感: theme_tags 显示 lake 主题但 main_subjects 5 张完全散 → 主题信号其实薄弱, 降 weak.

### Case D · 主字段 TH.3 + 次字段中间不动
```
theme_tags:
  P1-P3 [lakeside],  P4-P5 [urban]
主聚类: lake hit_rate=0.6, urban=0.4 → theme_clusters={lake}, primary_coverage=0.6 → TH.3

main_subjects:
  P1-P2 [湖面], P3-P4 [楼], P5 [桥]
次聚类: 湖面 hit_rate=0.4, 楼=0.4, 桥=0.2 → 无主题簇 (none ≥ 0.5)
        secondary_coverage = 0 < 1/3 → 降档

→ 最终 weak, rule_fired="TH.3+secondary_demote"
```

### Case E · 主字段 TH.3 + 次字段中间不动 (medium 段示例)
```
theme_tags 同 Case D → TH.3

main_subjects:
  P1-P3 [湖面], P4-P5 [楼]
次聚类: 湖面 hit_rate=0.6 (主题簇), 楼=0.4 (不入)
        secondary_coverage = 3/5 = 0.6 ∈ [1/3, 2/3) → 不动

→ 最终 medium, rule_fired="TH.3"
```

### Case F · 主字段 TH.4 (weak-high) 不看次字段
```
theme_tags: lake hit_rate=0.4, urban=0.4, park=0.2
主聚类: theme_clusters 全过 0.5? 等下 — 0.4 < 0.5, no theme_clusters
       → primary_coverage=0 < 0.4 → TH.5 weak (不是 TH.4)
```

让我重新构造 TH.4:
```
theme_tags:
  P1-P2 [lakeside], P3 [lakeside], P4-P5 [urban]
主聚类: lake hit_rate=0.6 ≥ 0.5 → theme_cluster, urban=0.4 不入
       primary_coverage = 3/5 = 0.6 → TH.3 (不是 TH.4)

实际 TH.4 (0.4 ≤ < 0.6) 案例:
  P1-P2 [lake] (hit_rate=0.4? 不到 0.5 阈值, no theme_cluster)
  → primary_coverage = 0 → TH.5
```

⚠ **发现设计冲突**: hit_rate ≥ 0.5 才入 theme_cluster, primary_coverage 永远 ≥ 0.5 或 = 0. 所以 **TH.4 (0.4 ≤ < 0.6) 范围实际不存在**!

**修订**: TH.4 / TH.5 合并:
- 0.4 ≤ primary_coverage < 0.6 → 实际不会出现 (因为单 cluster 覆盖必 ≥ 0.5 → primary_coverage ≥ 0.5)
- 0.5 ≤ < 0.6 是窄区间, 算 TH.4 weak 还是 TH.3 medium-low?

修订 grid (调整阈值):

| # | primary_coverage | primary_band | 触发次字段? |
|---|---|---|---|
| TH.1 | = 1.0 | strong | ❌ |
| TH.2 | 0.8 ≤ < 1.0 | medium-high | ✅ |
| TH.3 | 0.5 ≤ < 0.8 | medium-low | ✅ |
| TH.4 | < 0.5 OR no theme_clusters | weak | ❌ |
| TH.5 | N_valid ≤ 1 | none | ❌ |

**5 行简化 grid** (合并 TH.4/TH.5 weak; TH.6 改 TH.5 none). 解决 v0.2 TH.4 空区间问题.

### Case 重跑 (新 5 行 grid)

| Case | theme_tags | main_subjects | primary_coverage | primary_band | secondary_coverage | 最终 |
|---|---|---|---|---|---|---|
| A | [lake × 5] | — | 1.0 | TH.1 strong | (skip) | **strong** |
| B | [lake × 4, urban × 1] | [湖面 × 5] | 0.8 | TH.2 | 1.0 ≥ 2/3 | **strong+boost** |
| C | [lake × 4, urban × 1] | 5 散 | 0.8 | TH.2 | 0 < 1/3 | **weak+demote** |
| D | [lake × 3, urban × 2] | [湖 × 2, 楼 × 2, 桥 × 1] | 0.6 | TH.3 | 0 < 1/3 (无簇) | **weak+demote** |
| E | [lake × 3, urban × 2] | [湖面 × 3, 楼 × 2] | 0.6 | TH.3 | 3/5=0.6 中间 | **medium** |
| F | [全 5 张 tag 不同] | — | 0 | TH.4 weak | (skip) | **weak** |
| G | [a × 1, b × 1] (2 张) | — | 0 | TH.4 weak | (skip) | **weak** (N_valid=2 ≥ 2, 不进 TH.5) |
| H | [] × 5 (全空) | — | — | TH.5 none | (skip) | **none** |

---

## 六、数据结构 (ThemeFeature v0.3)

```python
class ThemeShape(str, Enum):
    """ThemeFeature.shape 落痕枚举 (ADR-0013 v0.3, 5 个核心 + 升降档变体)."""
    FULL_COVERAGE_THEMED = "full_coverage_themed"        # TH.1 strong
    DOMINANT_THEMED = "dominant_themed"                  # TH.2 medium-high
    PARTIAL_THEMED = "partial_themed"                    # TH.3 medium-low
    NO_DOMINANT_THEME = "no_dominant_theme"              # TH.4 weak
    NO_THEME_SIGNAL = "no_theme_signal"                  # TH.5 none


class ThemeFeature(BaseModel):
    """路径 B theme 维度产出 (ADR-0013 v0.3 直出 band, 双层判定)."""

    band: BandLevel
    rule_fired: str = Field(min_length=1)       # "TH.1" / "TH.2+secondary_boost" / "TH.3+secondary_demote"
    score: float = Field(ge=0.0, le=1.0)

    # ─── 主字段诊断 ──────────────────────────────────────────
    total_photos: int
    valid_photo_count: int                       # N_valid (有 theme_tags)
    primary_tag_pool_size: int
    primary_cluster_count: int
    primary_theme_clusters: list[list[str]]      # 过阈值的主题簇 tags
    primary_hit_rates: list[float]
    primary_coverage: float
    primary_outlier_ids: list[str]

    # ─── 次字段诊断 (仅 TH.2/TH.3 时计算, 否则 None) ────────
    secondary_tag_pool_size: int | None = None
    secondary_cluster_count: int | None = None
    secondary_theme_clusters: list[list[str]] = Field(default_factory=list)
    secondary_hit_rates: list[float] = Field(default_factory=list)
    secondary_coverage: float | None = None       # None 表示未触发计算

    # ─── 升降档诊断 ──────────────────────────────────────────
    secondary_action: str = "none"                # "none" | "boost" | "demote"

    shape: ThemeShape
    primary_signal: str = "theme_tags"
    secondary_signal: str = "main_subjects"
```

---

## 七、与已落 ADR 关系

| ADR | 共享 / 独立 |
|---|---|
| ADR-0008 path A theme | 共享 MockEmbedder + cluster_tags |
| ADR-0012 path B event | 双门槛范式同构, 触发条件相反 (event 严档 / theme 模糊段) |
| ADR-0010/0011 | 同构输出 (band/shape/rule_fired) |

---

## 八、不变性

1. band 4 档终值, 真值表 28 条直读
2. 双阈值架构 (聚类 0.75 + 主题 0.5) + cluster hit_count ≥ 2
3. **strong 唯一通道: TH.1 (primary_coverage=1.0) 或 TH.2/TH.3 + secondary_coverage ≥ 2/3**
4. **次字段仅 TH.2 / TH.3 触发**, 其他档不算
5. coverage 都基于 N (跟 ADR-0010/0011/0012 对齐)
6. outlier 不影响 band, 仅落痕 (用户兜底剔除)
7. N < 2 → band="none" (红线 §3)
8. 复用 ADR-0008 cluster_tags + MockEmbedder
9. rule_fired 必填 (TH.1~TH.5 + 升降档后缀)
10. 多主题相册自然存在 (theme_clusters 无上限)

---

## 九、配置

```yaml
# config/path_b_theme.yaml
path_b_theme:

  # ─── 主字段 ─────────────────────────────────────
  primary_field: "theme_tags"
  primary_hit_rate_threshold: 0.5     # cluster.hit_rate ≥ 此值 → 主题簇
  min_hit_count: 2                     # cluster.hit_count ≥ 此值

  primary_band_thresholds:
    strong_coverage: 1.0               # TH.1
    medium_high: 0.8                   # TH.2 触发次字段
    medium_low: 0.5                    # TH.3 触发次字段
    # < 0.5 → TH.4 weak

  # ─── 次字段升降档 (仅 TH.2/TH.3 触发) ────────────
  secondary_field: "main_subjects"
  secondary_band_adjust:
    boost_threshold: 0.667             # ≥ 此 → 升 strong (2/3)
    demote_threshold: 0.333            # < 此 → 降 weak (1/3)
    # [1/3, 2/3) 中间 → 不动

  # ─── 复用 ADR-0008 ───────────────────────────
  # cluster.merge_similarity = 0.75
  # embedder = MockEmbedder (OQ-018 切 Qwen)

  fallback:
    n_valid_min: 1                     # N_valid ≤ 此值 → TH.5 none
```

---

## 十、待决 OQ

### OQ-24a · 双阈值 (0.5/0.5 + 0.667/0.333) 真实数据校准
v0.2 真实数据 grid search.

### OQ-24b · min_hit_count = 2 vs 3
推荐 2 (小相册友好).

### OQ-24c · 次字段是否独立 cluster_threshold
当前复用 ADR-0008 0.75. 候选: main_subjects 用更松 0.65 (开放短语相似度低).

### OQ-24d · MockEmbedder 表覆盖小 (Case E mock 局限)
v0.2 OQ-018 真 Qwen 接入解.

### OQ-24e · 升降档幅度
当前 1 档 (medium → strong / medium → weak). 候选: 2 档 (medium → strong 直接? medium → none?).
推荐 1 档 (跟 ADR-0010 transit 降档 1 档同).

---

## 十一、与老 docs/07 边界对照

| 场景 | 老 score | v0.3 band | 体感 |
|---|---|---|---|
| 全员同 tag | 1.0 strong | TH.1 strong | ✓ |
| 4:1 离群 + 次字段强 | ≈ 0 none | **TH.2+boost strong** | **新好** |
| 4:1 离群 + 次字段散 | ≈ 0 none | **TH.2+demote weak** | 新降 (主弱次也弱) |
| 3:2 + 次字段中 | ≈ 0 none | TH.3 medium | 新好 |
| 同义不同字 (表内) | ≈ 0 none | TH.1 strong | 新好 |
| 同义不同字 (表外) | ≈ 0 none | TH.4 weak (mock) / TH.1 (真模型) | mock 局限 |
| 全 5 张不同 | 0 none | TH.4 weak | 微升 |
| 2 张不同 | 0 none | TH.4 weak (修 min_hit_count) | OK |

---

## 十二、实施清单 (12 步)

| Step | 动作 |
|---|---|
| 1 | 写 `decisions/0013-path-b-theme-two-tier-cluster.md` |
| 2 | 写 `docs/19_path_b_theme.md` |
| 3 | 改 `docs/02_data_contracts.md` (ThemeFeature v0.3 + ThemeShape) |
| 4 | 改 `docs/07_dimension_thresholds.md` §3.2.3 (指向 docs/19) |
| 5 | 改 `docs/00/01/11/12` |
| 6 | 关闭 OQ-009 §9a |
| 7 | 写 `config/path_b_theme.yaml` |
| 8 | 改 `src/contracts/features.py` (ThemeFeature 升级 + ThemeShape v0.3) |
| 9 | 改 `src/contracts/__init__.py` 导出 |
| 10 | 重写 `src/features/theme.py` (build_theme_feature + 复用 ADR-0008 cluster_tags + 双层逻辑) |
| 11 | 改 `src/features/assemble.py` + `src/policy/bands.py` |
| 12 | 单测 + 重生 golden + grep + 归档 spec |

---

## 十三、待 Ace 最终审核 (v0.3)

1. **双层判定核心** (§二): 主 (theme_tags) 定主 band, 仅 TH.2/TH.3 看次 (main_subjects) 升降档. 确认?
2. **升降档阈值 2/3 / 1/3 (跟 ADR-0012 activity_gate 同款 2/3)** OK?
3. **TH.4 weak / TH.5 none 不看次字段** (跟主 weak/none 已确定一致). OK?
4. **rule_fired 加后缀 +secondary_boost / +secondary_demote** 落痕区分. OK?
5. **5 行主 grid 简化** (合并 TH.4/TH.5 重复 weak 段, 解决 0.4-0.5 空区间). OK?
6. **次字段 cluster_threshold 复用 0.75** (不单独配置). OK 或调?
7. **关闭 OQ-009 §9a**.

---

## 十四、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-18 | 初版, photo 单一主簇 + primary_share |
| v0.2 (draft) | 2026-05-18 | Ace 提范式: cluster-centric (hit_rate + coverage + outlier 标记); 双阈值; min_hit_count=2 |
| v0.3 (draft) | 2026-05-18 | Ace 提双层字段: 主 (theme_tags) + 次 (main_subjects) 分层, 仅 TH.2/TH.3 用次升降档 (2/3 升 / 1/3 降); 5 行主 grid 简化; rule_fired +secondary_boost/_demote 落痕 |
