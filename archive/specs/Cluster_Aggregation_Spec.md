# 小集 Theme 指纹聚合规范

> **版本**: v0.2
> **日期**: 2026-05-12
> **适用**: L2 Association Engine 工程实现规范 v1.3 L2.5

---

## 一、背景

L2.5 动态生长时,新照片要和老小集做 4 维比对:

| 维度 | 状态 |
|---|---|
| location | ✓ 已规范 (DBCH 算法,见 `Place_Anchor_Spec_Final`) |
| **theme** | ❌ 之前只是字面并集,无法处理"湖边/水边"这种同义场景 |
| event | ❌ 无小集级聚合规范 (本规范暂不覆盖) |
| people | ❌ 暂时不做 |

**核心问题**:照片级 `theme_tags` 有了,但小集级没有"语义指纹",新照片来时无法精确比对。

**本规范定位**:仅定义 **theme 维度**的聚合与匹配算法。event/people 后续补充。

**重要前提**:
- L1 输出 `theme_tags`: **2-4 个/张** (PRD §3.1.3)
- L1 大部分字段已验证可靠
- embedding 模型: **Qwen3-Embedding-0.6B** (中文优势 + 速度 + 精度三优先)

---

## 二、总体设计

### 核心流程

```
所有照片的 theme_tags (含重复)
    ↓
Step 1: 频次统计 + 字面去重
    ↓
Step 2: 批量 embedding (Qwen3-Embedding-0.6B)
    ↓
Step 3: 层次聚类 (sklearn AgglomerativeClustering)
    ↓
Step 4: 每簇加权聚合 (representative + centroid + frequency)
    ↓
Step 5: 按频率降序排
    ↓
Step 6: 自然断层截断 (max_keep=5)
    ↓
小集 theme 指纹: list[SemanticCluster]
```

### 匹配流程

```
新照片的 theme_tags
    ↓
embed
    ↓
对每个簇算"被命中最强相似度" (max)
    ↓
按簇频率加权求和
    ↓
分数 → 档位 (strong/medium/weak/none)
```

---

## 三、数据结构

```python
@dataclass
class SemanticCluster:
    """语义簇 = 同义标签的合并"""
    representative: str          # 簇内频次最高的字面 (作为代表)
    members: dict[str, int]      # {字面: 该字面频次}
    frequency: int               # 簇内总频次 (所有成员频次之和)
    centroid: np.ndarray         # 加权平均的 embedding 向量,归一化
```

小集级新增字段:

```python
class MiniAlbum:
    # ... 原有字段
    theme_clusters: list[SemanticCluster]   # max 5 个,按频率降序
    theme_aggregated_at: datetime
```

---

## 四、聚合算法

### Step 1-4 · 语义聚类

```python
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from collections import Counter

def aggregate_theme_clusters(
    tags: list[str],                    # 带重复的标签流
    embed_fn,                            # embedding 函数
    merge_similarity: float = 0.75
) -> list[SemanticCluster]:
    """
    输入: ["湖边", "湖边", "湖边", "湖面", "湖水", "湖水", "桥", "夕阳"]
    输出 (按频率降序):
      [
        {representative: "湖边", members: {湖边:3, 湖面:1, 湖水:2}, frequency: 6, centroid: ...},
        {representative: "桥",   members: {桥:1},                     frequency: 1, centroid: ...},
        {representative: "夕阳", members: {夕阳:1},                   frequency: 1, centroid: ...}
      ]
    """
    if not tags:
        return []
    
    # 频次统计 + 字面去重 (优化:相同字面只 embed 一次)
    tag_counts = Counter(tags)
    unique_tags = list(tag_counts.keys())
    
    # 批量 embed
    embeddings = embed_fn(unique_tags)   # (n_unique, dim)
    
    # 边界:只有 1 个 unique tag
    if len(unique_tags) == 1:
        emb = embeddings[0] / np.linalg.norm(embeddings[0])
        return [SemanticCluster(
            representative=unique_tags[0],
            members={unique_tags[0]: tag_counts[unique_tags[0]]},
            frequency=tag_counts[unique_tags[0]],
            centroid=emb
        )]
    
    # 层次聚类: 余弦距离 > 阈值不合并
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1 - merge_similarity,
        metric="cosine",
        linkage="average"
    )
    labels = clustering.fit_predict(embeddings)
    
    # 每簇聚合
    clusters = []
    for cluster_id in np.unique(labels):
        member_idx = np.where(labels == cluster_id)[0]
        
        # 成员字面 + 频次
        member_dict = {
            unique_tags[i]: tag_counts[unique_tags[i]]
            for i in member_idx
        }
        
        # 簇总频次 (语义层面的频率)
        total_frequency = sum(member_dict.values())
        
        # 代表 = 簇内频次最高
        representative = max(member_dict.items(), key=lambda x: x[1])[0]
        
        # centroid = 按字面频次加权平均
        member_embs = embeddings[member_idx]
        weights = np.array([member_dict[unique_tags[i]] for i in member_idx])
        centroid = (member_embs * weights[:, None]).sum(axis=0) / weights.sum()
        centroid = centroid / np.linalg.norm(centroid)
        
        clusters.append(SemanticCluster(
            representative=representative,
            members=member_dict,
            frequency=total_frequency,
            centroid=centroid
        ))
    
    # 按频率降序
    clusters.sort(key=lambda c: c.frequency, reverse=True)
    return clusters
```

### Step 6 · 自然断层截断

按频次降序排好后,需要截断:**保留主流簇,丢弃长尾**。

**规则**: `frequency ≥ max_frequency × 0.4` 才保留,上限 `max_keep=5`,至少保留 1 个。

```python
def truncate_by_relative_threshold(
    clusters: list[SemanticCluster],
    max_keep: int = 5,
    relative_threshold: float = 0.4
) -> list[SemanticCluster]:
    """
    保留: frequency ≥ max(frequency) × relative_threshold
    上限: max_keep
    至少: 1 个
    """
    if not clusters:
        return []
    
    max_freq = clusters[0].frequency
    threshold = max_freq * relative_threshold
    
    kept = []
    for c in clusters[:max_keep]:
        if c.frequency >= threshold:
            kept.append(c)
        else:
            break  # 频次降序,后面只会更小
    
    return kept if kept else [clusters[0]]   # 至少保留 1 个
```

### 截断 case 验证

| 输入频次序列 | max | threshold (0.4) | 保留 |
|---|---|---|---|
| `[7,4,3,3,3]` | 7 | 2.8 | 全保留 (都 ≥ 2.8) |
| `[9,8,2,2,1]` | 9 | 3.6 | 保留 [9,8] |
| `[5,4,3,2,1]` | 5 | 2.0 | 保留 [5,4,3,2] |
| `[10,1,1,1,1]` | 10 | 4.0 | 保留 [10] |
| `[3,3,3,3,3]` | 3 | 1.2 | 全保留 |

---

## 五、匹配函数 (新照片 vs 小集 theme 指纹)

### 核心算法

**每个簇看自己被新照片最强命中多少,按簇频率加权求和。**

**关键设计**:
- **每个簇的视角看命中**:`max(cos(new_tag_j, cluster_i.centroid) for j)`
- **按簇频率加权求和**:主簇权重大,长尾簇权重小
- **不对新 tag 取平均**:保留关键信号的尖锐性

```python
from sklearn.metrics.pairwise import cosine_similarity

def match_theme(
    new_tags: list[str],
    clusters: list[SemanticCluster],
    embed_fn,
    band_thresholds: dict
) -> tuple[str, dict]:
    """
    返回 (band, diagnostics)
    band ∈ {strong, medium, weak, none}
    """
    if not new_tags or not clusters:
        return "none", {"reason": "empty_input"}
    
    # embed 新 tag (去重)
    unique_new_tags = list(set(new_tags))
    new_embs = embed_fn(unique_new_tags)        # (n_new, dim)
    
    # 簇 centroid 矩阵
    cluster_centroids = np.array([c.centroid for c in clusters])  # (n_clusters, dim)
    
    # 相似度矩阵
    sim_matrix = cosine_similarity(new_embs, cluster_centroids)   # (n_new, n_clusters)
    
    # 每个簇被命中的最强匹配
    per_cluster_max_sim = sim_matrix.max(axis=0)   # (n_clusters,)
    
    # 簇频率作权重 (归一化)
    cluster_weights = np.array([c.frequency for c in clusters], dtype=float)
    cluster_weights = cluster_weights / cluster_weights.sum()
    
    # 加权和 (核心公式)
    score = float((per_cluster_max_sim * cluster_weights).sum())
    
    # 档位映射
    if score >= band_thresholds["strong"]:
        band = "strong"
    elif score >= band_thresholds["medium"]:
        band = "medium"
    elif score >= band_thresholds["weak"]:
        band = "weak"
    else:
        band = "none"
    
    # 诊断
    diag = []
    for i, c in enumerate(clusters):
        best_new_tag_idx = int(sim_matrix[:, i].argmax())
        diag.append({
            "representative": c.representative,
            "frequency": c.frequency,
            "weight": float(cluster_weights[i]),
            "max_sim": float(per_cluster_max_sim[i]),
            "matched_by": unique_new_tags[best_new_tag_idx],
            "contribution": float(per_cluster_max_sim[i] * cluster_weights[i])
        })
    
    return band, {
        "score": score,
        "per_cluster": diag
    }
```

---

## 六、配置

```yaml
theme_aggregation:
  embedding_model: "Qwen/Qwen3-Embedding-0.6B"
  
  # 聚类
  merge_similarity: 0.75       # cosine > 0.75 合并
  
  # 截断
  max_clusters: 5
  relative_threshold: 0.4      # frequency ≥ max × 0.4 保留
  
  # 匹配档位
  band_thresholds:
    strong: 0.75
    medium: 0.55
    weak: 0.35
```

---

## 七、Case 验证

### 小集 theme 指纹

```
8 张照片聚合后:
clusters = [
  {representative: "湖", frequency: 6, weight: 0.6},
  {representative: "夕阳", frequency: 3, weight: 0.3},
  {representative: "桥", frequency: 1, weight: 0.1}
]
```

### Case 1 · 主题完全命中

```
new_tags = ["湖水", "夕阳"]

每簇最强命中:
  湖簇:   max sim = 0.95 (湖水命中)
  夕阳簇: max sim = 1.00 (夕阳命中)
  桥簇:   max sim = 0.20 (没人命中)

加权和 = 0.95×0.6 + 1.00×0.3 + 0.20×0.1
      = 0.57 + 0.30 + 0.02 = 0.89

→ strong ✓
```

### Case 2 · 部分命中主簇

```
new_tags = ["湖面", "波光"]

每簇最强命中:
  湖簇:   0.92 (湖面命中)
  夕阳簇: 0.40 (没真命中)
  桥簇:   0.25

加权和 = 0.92×0.6 + 0.40×0.3 + 0.25×0.1
      = 0.55 + 0.12 + 0.025 = 0.70

→ medium ✓
```

**关键**:夕阳主簇没命中,score 被拉到 medium。

### Case 3 · 只命中低频簇

```
new_tags = ["桥", "石栏"]

每簇最强命中:
  湖簇:   0.30
  夕阳簇: 0.10
  桥簇:   1.00

加权和 = 0.30×0.6 + 0.10×0.3 + 1.00×0.1
      = 0.18 + 0.03 + 0.10 = 0.31

→ weak ✓
```

**关键**:即使"桥"完美命中,**因为它权重只 0.1,主簇没命中,综合 weak**。簇权重生效的体现。

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

### Case 5 · 新 tag 数量多但都不像

```
new_tags = ["美食","聚餐","啤酒","朋友","夜晚","餐桌","甜品","酒水"]  (8 个)

每簇最强命中都 ≤ 0.10
加权和 ≈ 0.10

→ none ✓
```

**关键**:即使新 tag 多,只要没命中任何主簇,**不会因为数量假阳**。

---

## 八、性能预算

```
单次聚合 (30 张照片 × 3 tag = 90 实例, ~30 unique):
  · embed batch (有缓存): ~5ms
  · 层次聚类: <1ms
  · 后处理 + 截断: <1ms
  总: ~7ms

单次匹配 (新照片 3 tag vs 5 簇):
  · embed 新 tag (大概率命中缓存): <2ms
  · 余弦矩阵 (3×5): <1ms
  · 加权求和: <1ms
  总: ~3ms

对话场景延迟可接受 ✓
```

---

## 九、增量更新

新照片加入小集后,**全量重算 theme 指纹** (代价小):

```python
def on_photo_added(album, new_photo, config):
    album.member_photo_ids.append(new_photo.photo_id)
    
    # 重新聚合 theme
    members = load_l1(album.member_photo_ids)
    all_theme_tags = []
    for p in members:
        all_theme_tags.extend(p.theme_tags)
    
    raw_clusters = aggregate_theme_clusters(
        all_theme_tags, embed_fn,
        merge_similarity=config.merge_similarity
    )
    
    album.theme_clusters = truncate_by_relative_threshold(
        raw_clusters,
        max_keep=config.max_clusters,
        relative_threshold=config.relative_threshold
    )
    
    album.theme_aggregated_at = datetime.now()
```

**性能**: 30 张照片全量重算 ~7ms,加照片就刷一次,无需复杂增量逻辑。

---

## 十、Embedding 服务

**模型选择**: Qwen3-Embedding-0.6B
- 中文场景顶尖
- 0.6B 参数,推理快
- 开源可本地部署

**部署**:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B')

def embed_fn(texts: list[str]) -> np.ndarray:
    """带缓存的 embedding"""
    cached = []
    to_embed = []
    to_embed_idx = []
    
    for i, t in enumerate(texts):
        if t in embedding_cache:
            cached.append((i, embedding_cache[t]))
        else:
            to_embed.append(t)
            to_embed_idx.append(i)
    
    if to_embed:
        new_embs = model.encode(to_embed, normalize_embeddings=True)
        for t, e in zip(to_embed, new_embs):
            embedding_cache[t] = e
    
    result = np.zeros((len(texts), model.get_sentence_embedding_dimension()))
    for i, e in cached:
        result[i] = e
    for i, t in zip(to_embed_idx, to_embed):
        result[i] = embedding_cache[t]
    
    return result
```

**缓存策略**: tag 级永久缓存 (tag 字面稳定,无需失效)

---

## 十一、待补 OQ

| OQ | 问题 | 优先级 |
|---|---|---|
| OQ-1 | `merge_similarity = 0.75` 是否合理 (场景测试调) | P0.5 |
| OQ-2 | `band_thresholds` 三档值是否合理 | P0.5 |
| OQ-3 | `relative_threshold = 0.4` 截断是否会丢失重要长尾 | P0.5 |
| OQ-4 | Qwen3-Embedding-0.6B 实际效果验证 (上线前 benchmark) | P0 |
| OQ-5 | 极大相册 (50+ 张) 的指纹是否需要"代表性采样" | P1 |

---

## 十二、核心不变性

1. **频率信息保留到最后**:聚类后的簇 frequency = 簇内所有字面频次之和
2. **簇权重必须用**:匹配时按簇频率加权,主簇影响大,长尾影响小
3. **不对新 tag 取平均**:保留关键信号的尖锐性
4. **每个簇看自己被命中**:`max(sim)`,而非平均
5. **截断保留主流**:`frequency ≥ max × 0.4`,且 ≤ `max_keep=5`
6. **指纹实时重算**:每次加照片重算,逻辑简单,~7ms

---

## 十三、与现有规范的关系

| 字段 (工程规范 v1.3) | 本规范升级 |
|---|---|
| `theme_tags_set` (字面集合) | 🔄 替换为 `theme_clusters` (语义簇) |
| `dominant_theme` | ✅ 不变,仍由 LLM 综述输出 |

event / anchor / people 维度后续规范补充,本文档暂不覆盖。

---

*v0.2 · 2026-05-12 · 仅 theme 维度,event/people 后续补充*
