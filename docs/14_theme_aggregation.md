# 14 · Theme 语义簇聚合 + 匹配规范

> 路径 A (动态生长) **theme 维度** 的小集级指纹生成 + 1 张新照片匹配算法.
> 算法依据: [ADR-0008](../decisions/0008-theme-semantic-clustering.md), 原始 spec 见 [archive/specs/Cluster_Aggregation_Spec.md](../archive/specs/Cluster_Aggregation_Spec.md).
> 仅覆盖 theme 维度. event/people/anchor 不在本文档范围, 见 [OQ-008](./12_open_questions.md#oq-008-小集指纹合成-mini-album-fingerprint-synthesis).
> 路径 B (多张 vs 多张) 的 theme 算法见 [ADR-0004](../decisions/0004-feature-assembler-revision.md) §3.2.3, 与本文档算法**互补不冲突**.

---

## 一、问题与定位

L2.5 动态生长 (路径 A) 用"1 张新照片 vs 老相册指纹"做 4 维比对. 老相册需要一个**语义层指纹**, 而不是字面 tag 集合.

| 维度 | 状态 |
|---|---|
| location | ✅ DBCH (ADR-0005, v0.1 距离档位被 ADR-0007 临时统一) |
| **theme** | ✅ 本文档 (ADR-0008) |
| event / anchor / people | ⏳ 暂用简化算法, 见 OQ-008 §8d/8e |

老 v0.1 方案 (字面 `jaccard(new.theme_tags, album.theme_tags_set)`) 的问题:
1. 同义词盲 (`湖边` vs `水边` Jaccard = 0)
2. 无频次权重 (出现 6 次的"湖"和出现 1 次的"桥"视为同等)
3. 长尾污染 (离群 tag 进 set 拉低 Jaccard)

---

## 二、数据结构

### 2.1 · SemanticCluster (语义簇)

```python
class SemanticCluster(BaseModel):
    representative: str            # 簇内频次最高的字面, 作为代表
    members: dict[str, int]        # {字面: 该字面频次}
    frequency: int                 # 簇内总频次 (= sum of members.values())
    centroid: list[float]          # 加权平均的归一化 embedding 向量
```

### 2.2 · MiniAlbumFingerprint 相关字段

```python
class MiniAlbumFingerprint(BaseModel):
    # ... 其他字段省略
    theme_clusters: list[SemanticCluster]   # max 5, 按 frequency 降序
    theme_aggregated_at: datetime | None
```

⚠ **dominant_theme 不在 fingerprint 内** — 那是 Mini Album 完整 schema 给 LLM/用户看的展示字段, 算法侧只用 `theme_clusters`.

### 2.3 · ThemeMatchResult (匹配输出)

```python
class ThemeMatchResult(BaseModel):
    band: Literal["strong", "medium", "weak", "none"]
    score: float                   # 加权和原始分
    per_cluster: list[dict]        # 每簇命中诊断
    reason: str = ""               # 空时 "no_tags" / "empty_clusters"
```

`per_cluster[i]` 字段:
- `representative`: 簇代表
- `frequency`: 簇频次
- `weight`: 归一化后的簇权重 (= frequency / sum(all_freq))
- `max_sim`: 该簇被新 tag 最强命中的 cosine
- `matched_by`: 命中它的新 tag 字面
- `contribution`: max_sim × weight (该簇对总分贡献)

---

## 三、聚合算法 (build_theme_clusters)

### 3.1 · 总流程

```
所有照片的 theme_tags (含重复)
    ↓
Step 1: Counter 频次统计 + 字面去重
    ↓
Step 2: 批量 embedding (Qwen3-Embedding-0.6B / Mock)
    ↓
Step 3: 层次聚类 (cosine + average linkage, threshold = 1 - merge_similarity)
    ↓
Step 4: 每簇加权聚合 (representative = 簇内频次最高, centroid = 频次加权平均)
    ↓
Step 5: 按 frequency 降序排序
    ↓
Step 6: 自然断层截断 (frequency ≥ max × 0.4, 上限 max_keep=5, 至少 1 个)
    ↓
list[SemanticCluster]
```

### 3.2 · Step 1-4 伪代码

```python
def aggregate_theme_clusters(
    tags: list[str],          # 带重复的 tag 流
    embed_fn,                 # callable: list[str] -> list[list[float]] (归一化向量)
    merge_similarity: float,  # cosine > 该值 合并 (默认 0.75)
) -> list[SemanticCluster]:
    # Step 1: 频次统计 + 字面去重
    tag_counts = Counter(tags)
    unique_tags = list(tag_counts.keys())

    # Step 2: 批量 embed (相同字面只 embed 一次)
    embeddings = embed_fn(unique_tags)

    # 边界: 单 tag
    if len(unique_tags) == 1:
        return [SemanticCluster(
            representative=unique_tags[0],
            members={unique_tags[0]: tag_counts[unique_tags[0]]},
            frequency=tag_counts[unique_tags[0]],
            centroid=embeddings[0],
        )]

    # Step 3: 层次聚类 (cosine + average linkage)
    labels = agglomerative_cluster_cosine(
        embeddings,
        distance_threshold=1 - merge_similarity,
    )

    # Step 4: 每簇聚合
    clusters = []
    for cluster_id in set(labels):
        member_idx = [i for i, l in enumerate(labels) if l == cluster_id]

        member_dict = {
            unique_tags[i]: tag_counts[unique_tags[i]]
            for i in member_idx
        }
        total_freq = sum(member_dict.values())
        representative = max(member_dict.items(), key=lambda x: x[1])[0]

        # centroid = 按字面频次加权平均, 再归一化
        weights = [member_dict[unique_tags[i]] for i in member_idx]
        centroid = weighted_mean_normalize(
            [embeddings[i] for i in member_idx], weights,
        )

        clusters.append(SemanticCluster(
            representative=representative,
            members=member_dict,
            frequency=total_freq,
            centroid=centroid,
        ))

    # Step 5: 按频率降序
    clusters.sort(key=lambda c: c.frequency, reverse=True)
    return clusters
```

### 3.3 · Step 6 · 自然断层截断

按频次降序排好后, 需截断:**保留主流簇, 丢弃长尾**.

**规则**: `frequency ≥ max_frequency × 0.4` 才保留, 上限 `max_keep=5`, 至少保留 1 个.

```python
def truncate_by_relative_threshold(
    clusters: list[SemanticCluster],
    max_keep: int = 5,
    relative_threshold: float = 0.4,
) -> list[SemanticCluster]:
    if not clusters:
        return []
    max_freq = clusters[0].frequency
    threshold = max_freq * relative_threshold
    kept = []
    for c in clusters[:max_keep]:
        if c.frequency >= threshold:
            kept.append(c)
        else:
            break   # 频次降序, 后面只更小
    return kept if kept else [clusters[0]]
```

### 3.4 · 截断 Case 验证表

| 输入频次序列 | max | threshold (×0.4) | 保留 |
|---|---|---|---|
| `[7,4,3,3,3]` | 7 | 2.8 | 全保留 |
| `[9,8,2,2,1]` | 9 | 3.6 | `[9,8]` |
| `[5,4,3,2,1]` | 5 | 2.0 | `[5,4,3,2]` |
| `[10,1,1,1,1]` | 10 | 4.0 | `[10]` |
| `[3,3,3,3,3]` | 3 | 1.2 | 全保留 |

---

## 四、匹配算法 (match_theme · 1 张新照片 vs 老相册 theme_clusters)

### 4.1 · 核心公式

```
每个簇看自己被命中:    per_cluster_max_sim[j] = max_i cos(new_tag_i, cluster_j.centroid)
按簇频率归一化作权重:   weight[j] = cluster_j.frequency / sum(cluster.frequency)
加权求和:               score = sum_j (per_cluster_max_sim[j] × weight[j])
分档:                  band ← {strong ≥ 0.75, medium ≥ 0.55, weak ≥ 0.35, else none}
```

### 4.2 · 核心设计 (不变性)

1. **每个簇看自己被命中 (max)** — 不取平均, 保留信号尖锐性
2. **按簇 frequency 加权** — 主簇 (出现多次的语义概念) 权重大, 长尾簇权重小
3. **不对新 tag 取平均** — 新 tag 数量多但都不像 → 不会因数量假阳
4. **截断保留主流** — 长尾簇被截断, 不参与匹配, 避免噪声
5. **指纹实时重算** — 每次加照片重算, 逻辑简单, n ≤ 30 约 7ms (真 Qwen)

### 4.3 · 伪代码

```python
def match_theme(
    new_tags: list[str],
    clusters: list[SemanticCluster],
    embed_fn,
    band_thresholds: dict,         # {strong: 0.85, medium: 0.70, weak: 0.55} (ADR-0020 v0.7 真 Qwen 校准)
) -> ThemeMatchResult:
    if not new_tags or not clusters:
        return ThemeMatchResult(band="none", score=0.0, per_cluster=[],
                                reason="no_tags" if not new_tags else "empty_clusters")

    # embed 新 tag (去重)
    unique_new = list(dict.fromkeys(new_tags))   # 去重保序
    new_embs = embed_fn(unique_new)

    # 每个簇被命中的最强相似度
    per_cluster_max_sim = []
    per_cluster_matched_by = []
    for c in clusters:
        sims = [cosine_similarity(e, c.centroid) for e in new_embs]
        best_i = max(range(len(sims)), key=lambda i: sims[i])
        per_cluster_max_sim.append(sims[best_i])
        per_cluster_matched_by.append(unique_new[best_i])

    # 簇 frequency 归一化作权重
    total_freq = sum(c.frequency for c in clusters)
    weights = [c.frequency / total_freq for c in clusters]

    # 加权和 (核心公式)
    score = sum(s * w for s, w in zip(per_cluster_max_sim, weights))

    # 分档
    if score >= band_thresholds["strong"]:
        band = "strong"
    elif score >= band_thresholds["medium"]:
        band = "medium"
    elif score >= band_thresholds["weak"]:
        band = "weak"
    else:
        band = "none"

    # 诊断
    per_cluster_diag = []
    for c, w, s, m in zip(clusters, weights, per_cluster_max_sim, per_cluster_matched_by):
        per_cluster_diag.append({
            "representative": c.representative,
            "frequency": c.frequency,
            "weight": w,
            "max_sim": s,
            "matched_by": m,
            "contribution": s * w,
        })

    return ThemeMatchResult(band=band, score=score, per_cluster=per_cluster_diag)
```

---

## 五、Case 验证 (spec §七)

### 小集 theme 指纹 (假设)

```
8 张照片聚合后:
clusters = [
  {representative: "湖",   frequency: 6, weight: 0.6},
  {representative: "夕阳", frequency: 3, weight: 0.3},
  {representative: "桥",   frequency: 1, weight: 0.1},
]
```

### Case 1 · 主题完全命中

```
new_tags = ["湖水", "夕阳"]

每簇最强命中:
  湖簇:   0.95 (湖水命中)
  夕阳簇: 1.00 (夕阳命中)
  桥簇:   0.20

加权和 = 0.95×0.6 + 1.00×0.3 + 0.20×0.1 = 0.57 + 0.30 + 0.02 = 0.89

→ strong ✓ (≥ 0.75)
```

### Case 2 · 部分命中主簇

```
new_tags = ["湖面", "波光"]

每簇最强命中:
  湖簇:   0.92
  夕阳簇: 0.40
  桥簇:   0.25

加权和 = 0.92×0.6 + 0.40×0.3 + 0.25×0.1 = 0.55 + 0.12 + 0.025 = 0.70

→ medium ✓ (≥ 0.55)
```

关键: 夕阳主簇没命中, score 被拉到 medium.

### Case 3 · 只命中低频簇

```
new_tags = ["桥", "石栏"]

每簇最强命中:
  湖簇:   0.30
  夕阳簇: 0.10
  桥簇:   1.00

加权和 = 0.30×0.6 + 0.10×0.3 + 1.00×0.1 = 0.18 + 0.03 + 0.10 = 0.31

→ weak ✓ (≥ 0.35? no. ≥ 0.30? 0.31 是 weak 还是 none? 阈值 weak = 0.35)
```

⚠ 0.31 < 0.35, 实际是 **none**. spec §七 case 3 标"weak" 是阈值边界笔误, 以 yaml 配置为准. 单测以 0.35 weak 阈值为基线.

关键: 即使"桥"完美命中, 主簇没命中 + 桥簇权重只 0.1 → 综合 weak/none. 簇权重生效.

### Case 4 · 完全无关

```
new_tags = ["美食", "餐厅"]

每簇最强命中:
  湖簇:   0.10
  夕阳簇: 0.08
  桥簇:   0.15

加权和 ≈ 0.10

→ none ✓
```

### Case 5 · 新 tag 数量多但都不像 (反假阳)

```
new_tags = ["美食","聚餐","啤酒","朋友","夜晚","餐桌","甜品","酒水"]  (8 个)

每簇最强命中都 ≤ 0.10
加权和 ≈ 0.10

→ none ✓
```

关键: 新 tag 多, **不会因数量假阳** — 因为只对每个簇取 max, 不对新 tag 取平均.

---

## 六、增量更新策略

新照片加入小集后, **全量重算 theme 指纹** (~7ms, 代价小, 无需复杂增量逻辑).

```python
def on_photo_added(album, new_photo, cfg):
    album.member_photo_ids.append(new_photo.photo_id)
    members = load_l1(album.member_photo_ids)
    all_theme_tags = [t for p in members for t in p.theme_tags]
    raw_clusters = aggregate_theme_clusters(
        all_theme_tags, embed_fn, cfg.merge_similarity,
    )
    album.theme_clusters = truncate_by_relative_threshold(
        raw_clusters, cfg.max_clusters, cfg.relative_threshold,
    )
    album.theme_aggregated_at = datetime.now()
```

---

## 七、Embedding 服务

| 阶段 | provider | 实现 |
|---|---|---|
| v0.1 demo | `mock` | `MockEmbedder` 确定性桩 (fixture 表 + 默认 hash → 单位向量) |
| v0.2 生产 | `qwen3-embedding-0.6b` | `QwenEmbedder` (本地 sentence_transformers, 见 [OQ-018](./12_open_questions.md#oq-018-qwen-真实-embedding-接入与基准测试)) |

**配置** `config/theme_aggregation.yaml::embedding.provider` 切换.

**v0.1 mock 设计原则** (ADR-0008 §2.5):
- 测算法**逻辑正确性** (聚合 / 截断 / 加权匹配 / 分档), 不测语义识别质量
- fixture embedding 表手工构造: 湖边/水边/湖面/湖 → 等价向量, 桥 / 夕阳 → 独立向量
- 真模型质量验证是 OQ-018 的事, 当前阶段不做

**失败处理**: **无 silent fallback** (demo 不要兜底, 真模型挂了直接崩, 上线时 OQ-018 处理 SLA).

---

## 八、配置 (`config/theme_aggregation.yaml`)

完整配置见 [config/theme_aggregation.yaml](../config/theme_aggregation.yaml). 本文档不重复内容.

修改阈值改 yaml, 算法逻辑改本文档.

### 8.1 · 真 Qwen Embedding 阈值校准 (ADR-0020 v0.7, 2026-05-20)

接入 Qwen3-Embedding-0.6B 后, 真实分数分布跟 mock 完全不同:

| Case | mock score | 真 Qwen score | 说明 |
|---|---|---|---|
| 完全无关随机词 (zzz vs lakeside) | ~0.1 | **0.47** | Qwen 对任何词都给"有意义"向量 |
| 不同语义 (meal vs lakeside) | ~0.1 | **0.51** | 仍有 baseline 相似度 |
| 不同英文词 (apple vs xylophone) | ~0.0 | **0.67** | 同语言 baseline 偏高 |
| 相关近义 (sunset vs lake) | ~0.5 | **0.69** | 真实近义 |
| 跨语言同义 (湖边 vs lakeside) | ~1.0 | **0.68-0.90** | 真实同义 |

**阈值上移** (mock 估值 → 真实校准):
- strong: 0.75 → **0.85** (真同义)
- medium: 0.55 → **0.70** (真相关)
- weak: 0.35 → **0.55** (避开 Qwen baseline 噪声)

详见 [ADR-0020 v0.7](../decisions/0020-real-api-integration.md).

---

## 九、性能预算

```
单次聚合 (30 张照片 × 3 tag = 90 实例, ~30 unique):
  · embed batch (有缓存): ~5ms (真 Qwen) / <1ms (mock)
  · 层次聚类 (n=30, O(n³)): <1ms
  · 后处理 + 截断: <1ms
  总: ~7ms (Qwen) / ~2ms (mock)

单次匹配 (新照片 3 tag vs 5 簇):
  · embed 新 tag: <2ms (Qwen, 大概率缓存命中)
  · 余弦矩阵 (3×5): <1ms
  · 加权求和: <1ms
  总: ~3ms
```

对话场景延迟可接受.

---

## 十、关联

**ADR**:
- [ADR-0008](../decisions/0008-theme-semantic-clustering.md) (本算法的决策依据)
- [ADR-0004](../decisions/0004-feature-assembler-revision.md) §3.2.3 (路径 B theme 算法, 与本文档互补)

**docs**:
- [docs/10_mini_album_schema.md](./10_mini_album_schema.md) 第三节 (指纹总览引用本文档)
- [docs/04_truth_table_growth.md](./04_truth_table_growth.md) theme 段 (使用方)
- [docs/02_data_contracts.md](./02_data_contracts.md) (`SemanticCluster` / `MiniAlbumFingerprint` 字段)
- [docs/07_dimension_thresholds.md](./07_dimension_thresholds.md) (path A theme 分档说明)

**代码**:
- `src/contracts/theme.py::SemanticCluster`
- `src/contracts/growth.py::MiniAlbumFingerprint.theme_clusters`
- `src/mini_album/theme_aggregation.py` (算法实现)
- `src/features/growth_features.py::_compute_theme_match` (path A 1 vs aggregation 匹配调用方)

**待补 OQ**:
- [OQ-018](./12_open_questions.md#oq-018-qwen-真实-embedding-接入与基准测试) — Qwen 真实接入 + 基准测试
- [OQ-019](./12_open_questions.md#oq-019-语义聚类参数调优) — merge_similarity / relative_threshold / band_thresholds 调优

**原始 spec** (归档):
- [archive/specs/Cluster_Aggregation_Spec.md](../archive/specs/Cluster_Aggregation_Spec.md) v0.2 (2026-05-12)
