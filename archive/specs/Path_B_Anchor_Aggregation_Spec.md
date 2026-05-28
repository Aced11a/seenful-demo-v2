# L2 Path B · Anchor 维度判断规范

> **版本**: v0.3 (draft, 待 Ace 最终审核)
> **日期**: 2026-05-18
> **适用**: Seenful L2 Engine 路径 B (多张照片自身) anchor 维度
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (写 ADR-0014 + 后续 docs/src/config/tests).
> **v0.3 改动**: 跟 ADR-0013 theme v0.3 同步, **双层字段判定** — 主字段 (meaning_anchors) 定主 band, 仅 TH.2/TH.3 (anchor 用 AN.2/AN.3) 用次字段 (object_anchors) 升降档. **不再合并 meaning + object 成单 set** (改正 OQ-008 §8e 推荐 — 因为主次重要性显然不同, 不该混合).

---

## 一、背景

### 1.1 · 现状

`src/features/anchor.py` v0.1: meaning + object 各自 Jaccard 取 max, 严格交集 1 张离群 → 0.

### 1.2 · 失败模式

- 1 张离群 → max=0
- meaning + object 各自弱但合起来强 → 老 max 取不到
- 字面不识同义
- OQ-008 §8e 推荐"合并 set" — v0.3 **修订为分层** (主 meaning + 次 object)

### 1.3 · v0.3 修订 OQ-008 §8e

**OQ-008 §8e 老推荐**: meaning + object 合并成单 set, 不频次过滤
**v0.3 修订**: **分层判定** — meaning 是主字段, object 是次字段

修订理由 (Ace 2026-05-18 提):
- meaning_anchors 抽象 (天光/树影/慢下来) 是相册"灵魂"层级
- object_anchors 具体 (扶梯/篮球/楼) 是相册"物体"层级
- 二者**重要性不同**, 合并会丢失分层信号
- 跟 theme v0.3 (theme_tags 主 + main_subjects 次) 同范式

---

## 二、核心算法范式

### 2.1 · 与 theme v0.3 同骨架

```
通用工具 _build_two_tier_feature(photos, primary_field, secondary_field, cfg):
  Phase 1: 主字段 cluster + coverage → primary_band
  Phase 2: 主 band ∈ {TH.2, TH.3} → 次字段 cluster + coverage → 升降档

theme: primary=theme_tags, secondary=main_subjects
anchor: primary=meaning_anchors, secondary=object_anchors
```

### 2.2 · 三阶段流水线 (同 theme v0.3 §2.2 图, 仅字段名换)

主字段 → 主 band; 主 band ∈ {AN.2, AN.3} → 次字段升降档.

### 2.3 · 双阈值架构 (同 theme)

| 阈值 | 配置 | 作用 |
|---|---|---|
| cluster_merge_similarity | 0.75 (复用 ADR-0008) | 聚类同义阈值 |
| primary_hit_rate_threshold | 0.5 | 主字段主题簇阈值 |
| min_hit_count | 2 | 主题簇最小绝对命中数 |
| secondary_boost_threshold | 2/3 ≈ 0.667 | 次字段升档触发 |
| secondary_demote_threshold | 1/3 ≈ 0.333 | 次字段降档触发 |

---

## 三、核心变量定义 (同 theme v0.3 §三, 仅字段前缀)

### 3.1 · 主字段 (meaning_anchors)

| 变量 | 定义 |
|---|---|
| N | 总照片数 |
| N_valid | 有 ≥ 1 个 meaning_anchor 的 photo 数 |
| tag_pool_primary | ⋃ p.meaning_anchors 跨 photos 去重 |
| primary_clusters | 层次聚类后簇 |
| anchor_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 |
| primary_coverage | ⋃ anchor_clusters.photos / N |
| primary_outliers | 未命中任一 anchor_cluster 的 photo |

### 3.2 · 次字段 (object_anchors)

仅 primary_band ∈ {AN.2, AN.3} 时计算:

| 变量 | 定义 |
|---|---|
| tag_pool_secondary | ⋃ p.semantic_facts.object_anchors 跨 photos 去重 |
| secondary_clusters | 层次聚类 |
| secondary_anchor_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 |
| secondary_coverage | ⋃ secondary_anchor_clusters.photos / N |

---

## 四、判定网格

### 4.1 · 主字段 Grid (5 行简化)

| # | primary_coverage | primary_band | 触发次字段? |
|---|---|---|---|
| AN.1 | = 1.0 | **strong** | ❌ |
| AN.2 | 0.8 ≤ < 1.0 | medium-high | ✅ |
| AN.3 | 0.5 ≤ < 0.8 | medium-low | ✅ |
| AN.4 | < 0.5 OR no anchor_clusters | **weak** | ❌ |
| AN.5 | N_valid ≤ 1 | **none** | ❌ |

### 4.2 · 次字段升降档 (Phase 3)

| secondary_coverage | 调整 | 最终 band | rule_fired 后缀 |
|---|---|---|---|
| ≥ 2/3 | 升 1 档 | **strong** | `+secondary_boost` |
| 1/3 ≤ < 2/3 | 不动 | **medium** | (无) |
| < 1/3 | 降 1 档 | **weak** | `+secondary_demote` |

### 4.3 · rule_fired 完整映射

| 主 band | 次字段动作 | 最终 band | rule_fired |
|---|---|---|---|
| AN.1 | (skip) | strong | `AN.1` |
| AN.2 | boost | strong | `AN.2+secondary_boost` |
| AN.2 | 不动 | medium | `AN.2` |
| AN.2 | demote | weak | `AN.2+secondary_demote` |
| AN.3 | boost | strong | `AN.3+secondary_boost` |
| AN.3 | 不动 | medium | `AN.3` |
| AN.3 | demote | weak | `AN.3+secondary_demote` |
| AN.4 | (skip) | weak | `AN.4` |
| AN.5 | (skip) | none | `AN.5` |

⚠ anchor 是辅证 (真值表 A 系列无 anchor=强单独成集规则). 但仍保留 strong 档以备 E 系列升档逻辑.

---

## 五、Case 验证

### Case A · 主字段 strong (AN.1)
```
meaning_anchors = [天光 × 5]
object_anchors = (不看)

主聚类: 天光 hit_rate=1.0 → primary_coverage=1.0
→ AN.1 strong, rule_fired="AN.1"
```

### Case B · 主 AN.2 + 次救升 strong (v0.3 关键)
```
meaning_anchors:
  P1-P4 [天光],  P5 [拥堵]
主聚类: 天光 hit_rate=0.8 → AN.2

object_anchors:
  P1-P5 都含 [湖面] (或近义)
次聚类: 湖面 hit_rate=1.0 → secondary_coverage=1.0 ≥ 2/3 → 升

→ 最终 strong, rule_fired="AN.2+secondary_boost"
```

⚠ 体感: P5 meaning 突兀 "拥堵" (LLM 噪点), 但 object 一致 "湖面" → 实际是湖边游, 救升合理.

### Case C · 主 AN.2 + 次拉降 weak
```
meaning_anchors: 同 Case B → AN.2 (0.8)

object_anchors:
  P1 [扶梯], P2 [树], P3 [桥], P4 [汽车], P5 [楼]
次聚类: 各自独立, hit_count 都 < 2 → 无主题簇
        secondary_coverage = 0 < 1/3 → 降

→ 最终 weak, rule_fired="AN.2+secondary_demote"
```

⚠ 体感: meaning 显示有主导, 但 object 完全散 → 5 张实际不是同场景, 降 weak.

### Case D · 主 AN.3 + 次不动 (medium)
```
meaning_anchors:
  P1-P3 [天光], P4-P5 [楼影]
主聚类: 天光 hit_rate=0.6 → AN.3 medium-low, primary_coverage=0.6

object_anchors:
  P1-P3 [湖面], P4-P5 [桥]
次聚类: 湖面 hit_rate=0.6 (主题簇), 桥=0.4 (不入)
        secondary_coverage=3/5=0.6 ∈ [1/3, 2/3) → 不动

→ 最终 medium, rule_fired="AN.3"
```

### Case E · 主字段 AN.4 weak (不看次字段)
```
meaning_anchors: 全 5 张各不同
主聚类: 5 簇 each hit_count=1 < 2 → 无主题簇
       primary_coverage=0 → AN.4 weak
(次字段不看)
→ weak, rule_fired="AN.4"
```

### Case F · N_valid ≤ 1 (AN.5 none)
```
所有 photo 的 meaning_anchors 为空 (object 可能有 — 但仅 meaning 决定 N_valid)
→ AN.5 none
```

⚠ **设计选择**: AN.5 仅看 meaning 还是含 object?
- (a) 仅 meaning: meaning 是主字段, meaning 空 = 无主信号 = none
- (b) 任一空: meaning 或 object 都空才 none

我倾向 (a), 跟 theme 同 (N_valid 仅看主字段).

---

## 六、数据结构 (AnchorFeature v0.3)

```python
class AnchorShape(str, Enum):
    """AnchorFeature.shape 落痕枚举 (ADR-0014 v0.3, 5 个)."""
    FULL_COVERAGE_ANCHORED = "full_coverage_anchored"    # AN.1
    DOMINANT_ANCHORED = "dominant_anchored"              # AN.2
    PARTIAL_ANCHORED = "partial_anchored"                # AN.3
    NO_DOMINANT_ANCHOR = "no_dominant_anchor"            # AN.4
    NO_ANCHOR_SIGNAL = "no_anchor_signal"                # AN.5


class AnchorFeature(BaseModel):
    """路径 B anchor 维度产出 (ADR-0014 v0.3 直出 band, 双层判定)."""

    band: BandLevel
    rule_fired: str = Field(min_length=1)        # "AN.1" / "AN.2+secondary_boost" 等
    score: float = Field(ge=0.0, le=1.0)

    # ─── 主字段诊断 (meaning_anchors) ────────────────────
    total_photos: int
    valid_photo_count: int                       # N_valid (有 meaning_anchors)
    primary_tag_pool_size: int
    primary_cluster_count: int
    primary_anchor_clusters: list[list[str]]
    primary_hit_rates: list[float]
    primary_coverage: float
    primary_outlier_ids: list[str]

    # ─── 次字段诊断 (object_anchors, 仅 AN.2/AN.3 计算) ─
    secondary_tag_pool_size: int | None = None
    secondary_cluster_count: int | None = None
    secondary_anchor_clusters: list[list[str]] = Field(default_factory=list)
    secondary_hit_rates: list[float] = Field(default_factory=list)
    secondary_coverage: float | None = None       # None 表示未触发

    # ─── 升降档诊断 ──────────────────────────────────────────
    secondary_action: str = "none"                # "none" | "boost" | "demote"

    shape: AnchorShape
    primary_signal: str = "meaning_anchors"
    secondary_signal: str = "object_anchors"
```

---

## 七、与已落 ADR 关系

| ADR | 共享/独立 |
|---|---|
| ADR-0008 path A theme | 共享 MockEmbedder + cluster_tags |
| **ADR-0013 path B theme v0.3** | **共享 `_build_two_tier_feature` 通用骨架** (theme 实施时提取) |
| ADR-0012 path B event | 双门槛范式同, 触发条件不同 |
| ADR-0010/0011 | 同构输出 |

---

## 八、不变性

1. band 4 档终值
2. 双阈值 (聚类 0.75 + 主题 0.5) + hit_count ≥ 2
3. **strong 唯一通道**: AN.1 (主 coverage=1.0) 或 AN.2/AN.3 + secondary ≥ 2/3
4. **次字段仅 AN.2/AN.3 触发**
5. **meaning_anchors 是主, object_anchors 是次** (v0.3 修订 OQ-008 §8e)
6. coverage 基于 N
7. outlier 不影响 band, 仅落痕
8. N < 2 → none (红线 §3)
9. 复用 ADR-0013 `_build_two_tier_feature` (依赖 theme 先落)
10. rule_fired 必填

---

## 九、配置

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

  # 复用 ADR-0008 配置
  # cluster.merge_similarity = 0.75

  fallback:
    n_valid_min: 1
```

---

## 十、待决 OQ

### OQ-25a · OQ-008 §8e 修订 (合并 → 分层)
v0.3 决定: meaning 主 + object 次. 关闭 OQ-008 §8e 老推荐, 走分层.

### OQ-25b · 阈值复用 theme 还是独立调
当前阈值 0.5/0.667/0.333/0.75 复用 theme. 候选: anchor 中文短语相似度可能需要更松 0.65.

### OQ-25c · object_anchors cluster_threshold
同 theme OQ-24c.

### OQ-25d · MockEmbedder 中文 anchor 同义覆盖
mock 表是否含 "天光/阳光/光斑" 等. v0.2 真 Qwen 接入后解.

### OQ-25e · AN.5 N_valid 判定字段
当前仅看 meaning (主字段). 候选: 看 meaning OR object.
推荐保持仅主字段 (跟 theme 一致).

---

## 十一、与老 docs/07 边界对照

| 场景 | 老 max(meaning_j, object_j) | v0.3 band | 体感 |
|---|---|---|---|
| 全员同 meaning + object | max(1,1) strong | AN.1 strong | ✓ |
| 4:1 离群 + object 强 | max=0 none | **AN.2+boost strong** | **新好** |
| 4:1 离群 + object 散 | max=0 none | **AN.2+demote weak** | 新降 |
| 3:2 + object 中 | max≈0 none | AN.3 medium | 新好 |
| meaning 散 + object 强 | max=0 none | AN.4 weak | 不救 (主字段定档) |
| 同义不同字 (表内) | max≈0 none | AN.1 strong | 新好 |
| 全员散 | 0 none | AN.4 weak | 微升 |

---

## 十二、实施清单 (12 步)

| Step | 动作 |
|---|---|
| 1 | 写 `decisions/0014-path-b-anchor-two-tier-cluster.md` |
| 2 | 写 `docs/20_path_b_anchor.md` |
| 3 | 改 `docs/02_data_contracts.md` (AnchorFeature + AnchorShape) |
| 4 | 改 `docs/07_dimension_thresholds.md` §anchor |
| 5 | 改 `docs/00/01/11/12` |
| 6 | 关闭 OQ-009 §9d + 修订 OQ-008 §8e |
| 7 | 写 `config/path_b_anchor.yaml` |
| 8 | 改 `src/contracts/features.py` (AnchorFeature + AnchorShape + FeaturePackage.anchor) |
| 9 | 改 `src/contracts/__init__.py` 导出 |
| 10 | 重写 `src/features/anchor.py` (build_anchor_feature + 复用 ADR-0013 `_build_two_tier_feature`) |
| 11 | 改 `src/features/assemble.py` + `src/policy/bands.py` |
| 12 | 单测 + 重生 golden + grep + 归档 spec |

⚠ **依赖 ADR-0013 (theme) 先落** — 通用工具 `_build_two_tier_feature` 由 theme 实施时提取.

---

## 十三、待 Ace 最终审核 (v0.3)

1. **修订 OQ-008 §8e**: 不再合并 meaning+object, 改分层 (meaning 主 + object 次). 确认?
2. **双层判定核心**: 主 meaning_anchors 定主 band; AN.2/AN.3 看次 object_anchors 升降档. OK?
3. **5 行主 grid + 升降档后缀**: 同 theme v0.3 结构. OK?
4. **AN.5 N_valid 仅看主字段 meaning** (跟 theme N_valid 仅看 theme_tags 一致). OK?
5. **anchor 阈值复用 theme**: 0.5/0.667/0.333 不独立调. OK?
6. **依赖 ADR-0013 (theme) 先落**: 通用工具复用. OK?
7. **关闭 OQ-009 §9d** + **修订 OQ-008 §8e**.

---

## 十四、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-18 | 初版, 复用 ADR-0008 + primary_share grid + meaning/object 合并 set |
| v0.2 (draft) | 2026-05-18 | 跟 theme v0.2 同步: cluster hit_rate + coverage + min_hit_count=2 |
| v0.3 (draft) | 2026-05-18 | 跟 theme v0.3 同步: 双层字段判定 (meaning 主 + object 次, AN.2/AN.3 升降档); **修订 OQ-008 §8e 老推荐 (合并 → 分层)**; 5 行主 grid + +secondary_boost/_demote 后缀 |
