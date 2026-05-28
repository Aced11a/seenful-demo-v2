# 07 · 维度分档阈值 + 信号计算

> 配置文件 `config/dimension_thresholds.yaml`。代码层不得硬编码任何数值。
>
> ⚠ **ADR-0018 (2026-05-19)**: Path B 7 维度走双版本开关 (L2 2.0 / L2 1.0). L2 2.0 (默认) 各维度直出 band 跳过阈值; L2 1.0 (副 demo) 走 v1.3 §3.2 score-based, 阈值在 `config/feature_assembler.yaml::legacy_thresholds` (跟此处一致). 详见 [docs/24](./24_feature_assembler_plan_ab.md).

## Changelog

- **v1.3.3 (2026-05-15)**: 路径 B location 维度由 score-driven 重写为 band-driven (ADR-0010): 分级 DBSCAN + PCA OBB + 形状校正 + transit 降档. §3.2.1 老 LocationContext + 三 context 距离档位**直接删**, 完整算法转 [docs/16](./16_path_b_location.md). 老 `location_distance_bands` / `location_distance_thresholds_unified` yaml 段保留为派生 `score` 计算用 (展示值, 真值表不读).
- **v1.3.2 (2026-05-12)**: 替换 location_score / time_score / theme_overlap_score 实现方案 (Ace + KY 评审,见 `decisions/0004-feature-assembler-revision.md`)。老 v1.3.1 方案已**直接删除**(产品判断:老方案语义偏差太大,无追溯价值)。location_score 部分被 ADR-0010 supersede.
- **v1.3.1 (2026-05-12)**: 初版 (v0.1 demo)。已废弃,见 ADR 0004。

## ⚠ Multi-cross 算法严格度问题

v0.1 多维度 (theme/event/people/anchor) 用"严格交集 / 全员一致" multi-cross, 1 张离群照片就把 score 拉到 0. 路径 A 用 "1 vs 聚合指纹" 也稀释了照片级强信号. 详见 **[OQ-009](./12_open_questions.md#oq-009-多维度匹配分档-multi-cross-算法严格度)**.

ADR-0004 (v1.3.2 location/time/theme 重写) 部分覆盖 (9a / 9d / 9g), 但 **event / people 严格一致问题 (9b/9c) 和路径 A 1v1 问题 (9e) ADR-0004 不覆盖**, 需 OQ-009 独立处理.

---

## 7 维分档阈值 (真值表用)

| 维度 | 强 ≥ | 中 ≥ | 弱 ≥ | 无 < |
|---|---|---|---|---|
| location  | 0.85 | 0.65 | 0.40 | 0.40 |
| theme     | 0.75 | 0.55 | 0.30 | 0.30 |
| event     | 0.70 | 0.50 | 0.30 | 0.30 |
| people    | 0.70 | 0.50 | 0.30 | 0.30 |
| time      | 0.85 | 0.65 | 0.40 | 0.40 |
| anchor    | 0.70 | 0.50 | 0.30 | 0.30 |
| emotional | 0.75 | 0.55 | 0.30 | 0.30 |

特殊处理:
- **people**: P0 score 上限 0.65,无法达 strong (即 A4 永不触发)
- **location**: 高频地点强制降一档

## 主载体 / 放大器 / 辅证 分组

```yaml
main_signals: [location, theme, event, people]
amplifier_signals: [time]
auxiliary_signals: [anchor, emotional]
```

---

## §3.2.1 · location 维度

### Path B (多张照片自身) — ADR-0010 直出 band

> ⚠ **完整算法见 [docs/16_path_b_location.md](./16_path_b_location.md)**. 本节只放总览, 不重复细节.

### Path A (1 张 vs 老相册指纹) — ADR-0005 DBCH + ADR-0016 4 档升级

> ⚠ **完整算法见 [docs/22_location_geocoder.md](./22_location_geocoder.md)** (ADR-0016).
>
> Geocoder (高德 reverse geocoding) + 4 档判定 (市内/省内/国内/国外) + DBCH 距离阈值 4 档表 (strong=500/1000/1500/2000m, medium/weak 派生).
> **ADR-0007 临时单一表 supersede**, OQ-005/§10a/§10b/§17 关闭.

### Path B 核心范式 (ADR-0010)

```
Phase 1 · 几何预处理      → 经纬度局部米制化 + 外层 DBSCAN(eps=1500m)
Phase 2 · K_outer=1 特征  → 内层 DBSCAN(eps=500m) + PCA OBB + 凸包直径 D + 轨迹长度 T + transit
Phase 3 · 三层判定:
  · Step A1: PCA 基础 band (9 行网格, L/W/R/K_inner)
  · Step A2: 形状校正 (τ = T/D, 救 PCA 失效的环形 / U 形)
  · Step A3: transit 降档 (Δt≥20min 过滤后的 max 速率 ≥ 30 kmh → 降一档)
路径 B · K_outer=2          → 单步判定 (gap + transit, 4 行)
K_outer=0 或 ≥3            → none
```

完整 9+2+1+4 行网格规则 + 字段定义 + 配置见 [docs/16](./16_path_b_location.md).

### 输出落痕字段 (写入 LocationFeature)

- `band` (4 档终值, 真值表直读)
- `rule_fired` ("A1.7" / "A2.1" / "A3_transit_demote" / "B.2" 等)
- `shape` (compact / linear / linear_curved / stretched / extended / irregular / oversized / loop / u_shape / multi_close / multi_walk / multi_drive / multi_far / scattered)
- K_outer / K_inner / L / W / R / D / T / τ / gap / max_transit_kmh / outlier_count (诊断)
- `score` 仍输出, 但仅做派生展示, 真值表不读

完整字段定义见 [docs/02 §LocationFeature](./02_data_contracts.md).

### 高频地点降一档

ADR-0006 高频低质量地点降档逻辑**保留**: `is_high_frequency_place=true` 时 Policy Engine bands 阶段把 location.band 降一档. 与 ADR-0010 输出的 band 解耦.

### 边界用例

- 1 张照片: K_outer=0 → band=none (照旧不算关联)
- 全 GPS 缺失: K_outer=0 → band=none
- 退化双簇 (K_outer=1, K_inner=2): A1.5 linear 不命中, 顺延 A1.7 → medium (设计意图, 见 docs/16 §3.1)

### 暂不修复的边界 (ADR-0010 接受)

- 沿江步道 5.5km 直线散步 → 仍判 none (L > 5 硬边界, 待 OQ-017 后用 cross_province 弹性 eps)
- U 形栈道 (1km × 0.5km 内走 4km, τ=4) → 仍判 strong (1km 跨度合理, τ > 4 不降档 — Ace 接受)

---

## §3.2.2 · time_score (ADR-0011: 自然日归属 + 链式切分 + T1/T2/T3 grid)

⚠ **本节由 [ADR-0011](../decisions/0011-time-natural-day-event-clustering.md) supersede v1.3.2 设计**. 完整算法见 [docs/17_path_b_time.md](./17_path_b_time.md), 本节聚焦"为什么这样改" + 接口约定.

### 核心思想 (ADR-0011)

- **直出 band, 不再算 score**: 与 ADR-0010 location 输出范式对齐 — 真值表直读 TimeFeature.band
- **K_days 是路径分流主键**: 0/1/2/≥3 分三路 grid (T1/T2/T3)
- **自然日归属**: 0-6 点归"前一日 night", 对齐自然作息
- **时间链式切分** (gap > 120min 切, 非 DBSCAN): 替代 v1.3.2 的"等距时段硬切 / 双峰检测"
- **边界保护带** (gap ∈ [100, 140] 落痕 `+near_eps_boundary`): 缓解 gap 阈值脆性
- **fallback 不动 band, 走 confidence**: supersede OQ-003 (× 0.5 全局降权)

### 与 location 的耦合

⚠ **time 不再依赖 location** (ADR-0011 §2.1 断 ADR-0004 location → time 单向依赖): 旅游档判定独立于 location.context (ADR-0010 已删该字段), 由 `K_days + has_overnight_chain` 内部判定.

### 落痕字段 (写入 TimeFeature, ADR-0011)

详见 [docs/02_data_contracts.md](./02_data_contracts.md) TimeFeature 段:
- `band` / `rule_fired` / `shape` / `score` (派生展示)
- `unique_days_count` (K_days) / `span_days` / `has_empty_days` / `events_per_day`
- `total_span_hours` / `max_inter_cluster_gap_h` / `max_intra_cluster_span_h`
- `has_overnight_chain` / `has_dawn_photos` / `near_eps_boundary_count`
- `fallback_count` / `fallback_ratio` / `confidence`

### v1.3.2 设计废弃字段

| 旧字段 | 废弃原因 |
|---|---|
| `is_bimodal` | 双峰检测整段废弃, 1D 链式切分覆盖 |
| `is_travel_relaxed` | ADR-0010 删 LocationContext 后字段已死 |
| `median_gap_hours` | 不再用 median 统计 |
| `all_fallback` (bool) | 用 `fallback_ratio == 1.0` 表达更细 |

### 暂不修复的边界 (ADR-0011 接受, OQ-022 跟踪)

- 凌晨归属 + overnight chain 双重逻辑冗余 (OQ-022g)
- 时区 / 夏令时未规整 (OQ-022h, 假设 timestamps 已为拍摄地 local time)
- T2.3 单日 ≥3 events 一律 weak 可能误伤跨日游 (OQ-022j)

---

## §3.2.3 · theme_overlap_score (ADR-0013: 双层字段 cluster + 升降档)

⚠ **本节由 [ADR-0013](../decisions/0013-path-b-theme-two-tier-cluster.md) supersede v1.3.2 设计**. 完整算法见 [docs/19_path_b_theme.md](./19_path_b_theme.md).

### 核心思想 (ADR-0013)

- **直出 band**: 跟 ADR-0010/0011/0012 输出范式对齐
- **双层字段**: 主 (theme_tags) 定主 band, 仅 medium 段 (TH.2/TH.3) 看次 (main_subjects) 升降档
- **cluster hit_rate + coverage**: 每 cluster 算"被多少 photo 命中" → 过阈值是主题簇 → coverage 决定 band
- **复用 ADR-0008 MockEmbedder + agglomerative_cluster_cosine**
- **min_hit_count=2**: cluster 至少 2 张命中才算主题簇 (防 2 张二选一升 strong)

### 与 ADR-0004 老设计的关系

ADR-0004 v1.3.2 设计的双向最大池化**未落地**, v0.3 完全 supersede. 不再用 `tag_embedding_similarity / main_subjects_jaccard / scene_type_consistency` 加权融合.

### 待 v0.2 OQ-018 升级

MockEmbedder 表外 tag 走 md5 hash, 真实场景 99% 退化为字面 Jaccard. 接 BGE-M3 / Qwen3-Embedding-0.6B (OQ-018) 后, ADR-0013 才能真正发挥语义识别效力.

---

## event_score 计算 (ADR-0012: event primary_share + activity 二次门槛)

⚠ **本节由 [ADR-0012](../decisions/0012-path-b-event-aggregation.md) supersede**. 完整算法见 [docs/18_path_b_event.md](./18_path_b_event.md).

### 核心思想 (ADR-0012)

- **直出 band, 不再算 score**: 跟 ADR-0010/0011 输出范式对齐
- **event 优先 + activity 二次门槛**: event=1.0 AND activity ≥ 2/3 双重才 strong (A3 真值表让 event-only 单独成集, 必须严)
- **复用 ADR-0009 `aggregate_event`**: 路径 A path B 共享 distribution 算法
- **8 行 grid E.1~E.8**: 含 activity 兜底 (N_valid ≤ 1)

### 老设计 (v0.1, supersede)

```
event_hint 一致 (且非 unknown) → 0.9
event_hint 全 unknown          → 0.0
activity 一致 (且非 unknown)   → 0.6
其余                            → 0.2
```

严格全员一致 1 张离群即降 0.2, v0.3 完全 supersede. OQ-009 §9b 已关闭 (ADR-0012).

## people_score 计算 (P0 上限 0.65)

```
people_presence 全 none           → 0.0
≥1 张有人 但 presence 不一致     → 0.3
people_presence 一致 (非 unknown):
  face_count 全部接近 (max - min <= 1) → 0.65   ← P0 上限
  face_count 差距大                    → 0.45
```

## anchor_score 计算 (ADR-0014: 双层字段 cluster + 升降档)

⚠ **本节由 [ADR-0014](../decisions/0014-path-b-anchor-two-tier-cluster.md) supersede**. 完整算法见 [docs/20_path_b_anchor.md](./20_path_b_anchor.md).

### 核心思想 (ADR-0014)

- **直出 band**: 跟 path B 其他 4 维一致
- **双层字段**: 主 (meaning_anchors) 定主 band; 仅 AN.2/AN.3 看次 (object_anchors) 升降档
- **修订 OQ-008 §8e**: 不再合并 meaning + object 成 set, 改主次分层 (重要性显然不同)
- **复用 ADR-0013 `_two_tier_cluster` 通用工具**

### 老设计 (v0.1)

```
取 max( jaccard(meaning_anchors), jaccard(object_anchors) )
```
严格交集 1 张离群 → 0, 子字段独立丢分层信号. v0.3 完全 supersede.

## emotional_score 计算 (ADR-0015: 开放字段 + 单层语义聚类 + neutral baseline)

⚠ **本节由 [ADR-0015](../decisions/0015-path-b-emotional-single-tier-cluster.md) supersede**. 完整算法见 [docs/21_path_b_emotional.md](./21_path_b_emotional.md).

### 核心思想 (ADR-0015 v0.2)

- **字段开放**: `emotional_tone: str` 不是封闭枚举, 算法不硬校验
- **照片情感 ≠ 用户情绪** (Ace 洞察): 老 7 白名单偏"用户体验词", 扩到画面氛围开放词 (诗意/怀旧/静谧/...)
- **单层语义聚类**: 复用 ADR-0013 `_two_tier_cluster(enable_secondary=False)`
- **EM.0 preempt**: 主簇=neutral 强制 cap weak (修核心 bug)
- **红线落痕不阻断**: LLM 违反"不做情绪推断" 仍进 distribution, 仅落痕 detected_inferred_*
- **L1 prompt 改一行**: 7 白名单 → 开放画面氛围词 + 阻拦推断情绪词

### 老设计 (v0.1, supersede)

```
emotional_tone 一致 → 0.85
完全不同 → 0.10
2/3 多数派 → 0.55
```

老算法 [neutral × 5] 给 0.85 strong 是 bug (neutral 是 baseline 不该 strong), ADR-0015 修.

---

## 配置加载示例

```python
from src.policy.config_loader import load_config

cfg = load_config("dimension_thresholds.yaml")
threshold_strong = cfg["dimension_bands"]["location"]["strong"]
```

⚠️ **代码里禁止出现魔数 0.85 / 0.65 / 0.40 等**。一律走配置。
