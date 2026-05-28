# ADR-0008 · 路径 A theme 维度语义簇聚合 (替换字面 Jaccard)

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-14 |
| 决策人 | Ace (产品/增长) — 来自 `archive/specs/Cluster_Aggregation_Spec.md` v0.2 (2026-05-12, 实施后归档) |
| 影响范围 | 新增 `src/contracts/theme.py` + `src/mini_album/theme_aggregation.py` + `config/theme_aggregation.yaml` + `docs/14_theme_aggregation.md`; 改 `src/contracts/growth.py::MiniAlbumFingerprint` + `src/features/growth_features.py::_compute_theme_overlap` + `tests/fixtures/albums/*.json` + `docs/{00,01,02,04,07,10,11,12}` |
| 相关文档 | `docs/14_theme_aggregation.md` (本算法主规范), `docs/10_mini_album_schema.md` (指纹总览引用) |
| 关联 OQ | **关闭 [OQ-008](../docs/12_open_questions.md#oq-008-小集指纹合成-mini-album-fingerprint-synthesis) §8b** (theme_tags_set 聚合规则); 引发 [OQ-018](../docs/12_open_questions.md#oq-018-qwen-真实-embedding-接入与基准测试) + [OQ-019](../docs/12_open_questions.md#oq-019-语义聚类参数调优) |
| 关联 ADR | 与 [ADR-0004](./0004-feature-assembler-revision.md) §3.2.3 互补 — ADR-0004 是**路径 B (多张 vs 多张)** 的 theme 算法, 本 ADR 是**路径 A (1 张 vs 老相册指纹)** 的 theme 算法, 不冲突 |

---

## 1 · 背景

L2.5 动态生长 (路径 A) 用"1 张新照片 vs 老相册指纹"做 4 维比对. 原 v0.1 `_compute_theme_overlap` 用字面 `jaccard(new.theme_tags, album.theme_tags_set)`:

- 老相册 `theme_tags_set` 是全照片 tag **字面并集** (OQ-008 §8b 推荐方案)
- 新照片 `theme_tags` 与之做 Jaccard

### 失败模式

1. **同义词盲**: `["湖边"]` vs `["水边"]` → Jaccard = 0, band = none
2. **无频次权重**: 8 张照片里 "湖" 出现 6 次 + "桥" 出现 1 次, 字面集合视为同等重要; 新照片只命中 "桥" 也算"主题命中"
3. **长尾污染**: 一张离群照片带的 tag 进 set 后, Jaccard 分母扩大, 拉低 score

### 引发本 ADR 的具体问题

OQ-008 §8b 原推荐 v0.1 用"简单并集", P0.5 升级"频次≥2 过滤". 但**频次≥2 仍不解决同义词问题**, 且需要等 P0.5. Ace 在 spec `Cluster_Aggregation_Spec.md` 中直接给出更彻底方案: **语义聚类 + 频次加权匹配**, 一次解决同义词 + 频次权重两个问题, 跳过中间过渡方案.

---

## 2 · 决策

### 2.1 · 数据结构 (新增)

```python
class SemanticCluster(BaseModel):
    """语义簇 = 同义标签的合并."""
    representative: str            # 簇内频次最高的字面, 作为代表
    members: dict[str, int]        # {字面: 该字面频次}
    frequency: int                 # 簇内总频次 (= sum of members.values())
    centroid: list[float]          # 加权平均的归一化 embedding 向量
```

### 2.2 · MiniAlbumFingerprint 字段变更

```python
# 删 (替换):
# theme_tags_set: list[str]      # 字面并集
# dominant_theme: str | None     # 字面众数

# 新增:
theme_clusters: list[SemanticCluster]   # 最多 5 个, 按 frequency 降序
theme_aggregated_at: datetime | None    # 上次聚合时间
```

⚠ **dominant_theme 完全从 fingerprint 移除** — spec §十三说"dominant_theme 不变, 仍由 LLM 综述输出". 这里的语义是: dominant_theme 是 Mini Album 给用户/LLM 看的**展示字段** (在完整 Mini Album schema 里), 不在路径 A 算法用的 fingerprint 里. 算法侧只用 `theme_clusters`.

### 2.3 · 聚合算法 (build)

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

### 2.4 · 匹配算法 (1 张新照片 vs 老相册 theme_clusters)

```python
def match_theme(new_tags, clusters, embed_fn, band_thresholds) -> (band, diag):
    # 每个簇看自己被新照片最强命中多少
    sim_matrix[i,j] = cos(new_tag_i_emb, cluster_j.centroid)
    per_cluster_max_sim[j] = max(sim_matrix[:,j])

    # 按簇 frequency 归一化作权重, 加权求和
    weights[j] = cluster_j.frequency / sum(cluster.frequency for cluster in clusters)
    score = sum(per_cluster_max_sim[j] * weights[j])

    # 分档
    band = (strong if score ≥ 0.75) | (medium ≥ 0.55) | (weak ≥ 0.35) | else none
```

**关键设计** (核心不变性):
1. **每个簇看自己被命中 (max)** — 不取平均, 保留信号尖锐性
2. **按簇 frequency 加权** — 主簇 (出现多次的语义概念) 权重大, 长尾簇权重小
3. **不对新 tag 取平均** — 新 tag 数量多但都不像 → 不会因数量假阳
4. **截断保留主流** — 长尾簇被截断, 不参与匹配, 避免噪声

### 2.5 · Embedding 服务

**生产**: Qwen3-Embedding-0.6B (中文场景顶尖 + 0.6B 推理快 + 开源可本地部署)

**v0.1 demo**: `MockEmbedder` 确定性桩 (类比 `MockJudge` / `MockGrowthJudge`)
- 测试用一张**手工 fixture embedding 表** (湖边/水边/湖面/湖 → 等价向量, 桥 / 夕阳 → 独立向量), 验证聚合/匹配/分档**逻辑正确性**
- **不验证模型本身**的语义识别能力 — 这是 Qwen3-Embedding-0.6B 真模型上线时验证, 见 [OQ-018](../docs/12_open_questions.md#oq-018-qwen-真实-embedding-接入与基准测试)

**embedding 失败兜底**: **不留** — demo 不要兜底, 真模型挂了直接崩 (上线时由 OQ-018 处理 SLA, 当前阶段不写 silent fallback)

### 2.6 · 增量更新策略

新照片加入相册后, **全量重算 theme 指纹** (~7ms, 代价小, 无需复杂增量逻辑)

---

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| **A. 字面 Jaccard (v0.1 当前)** | 同义词盲 + 无频次权重 (§1 失败模式) |
| **B. 频次 ≥ 2 过滤 (OQ-008 §8b P0.5 原推荐)** | 仍是字面层, 同义词盲, 且 P0.5 才上 |
| **C. embedding 双向最大池化 (ADR-0004 §3.2.3 路径 B 算法)** | 是"两组照片 tag 集合对集合"的算法, 不能直接用在"1 张 vs 老相册指纹"场景 (老相册需要"指纹"概念, 而不是逐张 tag) |
| **D. K-Means 聚类** | 需预设 K, 对小样本不稳, 不能产生 outlier (单 tag 主题被强行并入大簇) |
| **E. DBSCAN 聚类** | 用在 location 上有空间稠密性, 用在 tag embedding 上语义稠密性弱, 多数 tag 会成 noise (合并不出簇) |
| **F. 层次聚类 + 频次加权匹配 (本 ADR 采用)** | 自然产生簇 + 保留频次信息 + 簇权重生效 + 不假阳 + 算法简单 (n ≤ 30 不需要 numpy/sklearn) |

---

## 4 · 影响范围

### 契约变更

**新增** `src/contracts/theme.py`:
- `SemanticCluster` (representative / members / frequency / centroid)

**修改** `src/contracts/growth.py::MiniAlbumFingerprint`:
- **删** `theme_tags_set: list[str]`
- **删** `dominant_theme: str | None` (移到 Mini Album 完整 schema, fingerprint 不用)
- **新增** `theme_clusters: list[SemanticCluster]` (max 5)
- **新增** `theme_aggregated_at: datetime | None`

### 新增算法模块 `src/mini_album/theme_aggregation.py`

纯 Python 实现, **零外部依赖** (无 numpy/sklearn/sentence_transformers):
- `cosine_similarity(v1, v2)` — 两向量余弦
- `agglomerative_cluster_cosine(embeddings, threshold)` — 层次聚类 (average linkage, cosine 距离, O(n³) 但 n ≤ 30 足够)
- `aggregate_theme_clusters(tags, embed_fn, merge_similarity)` — spec §四 Step 1-4
- `truncate_by_relative_threshold(clusters, max_keep, relative_threshold)` — spec §四 Step 6
- `match_theme(new_tags, clusters, embed_fn, band_thresholds)` — spec §五
- `build_theme_clusters(photos, embed_fn, cfg)` — 高层入口, 接 MiniAlbumFingerprint
- `MockEmbedder` — 确定性桩 (基于 fixture 表 + 默认 hash → 单位向量)
- `QwenEmbedder` (stub, `raise NotImplementedError`) — v0.2 接 Qwen3-Embedding-0.6B

### 配置 `config/theme_aggregation.yaml` (新增)

```yaml
theme_aggregation:
  embedding:
    provider: "mock"                # v0.1: mock | v0.2: qwen3-embedding-0.6b
    model: null                     # null on mock, "Qwen/Qwen3-Embedding-0.6B" on qwen
    dim: 16                         # mock 用低维; 真 Qwen 是 1024
  merge_similarity: 0.75
  max_clusters: 5
  relative_threshold: 0.4
  band_thresholds:
    strong: 0.75
    medium: 0.55
    weak: 0.35
```

### `src/features/growth_features.py::_compute_theme_overlap` 重写

旧:
```python
return jaccard_multi([set(p.theme_tags), set(album.theme_tags_set)])
```

新:
```python
embedder = get_theme_embedder(cfg)
band, diag = match_theme(p.theme_tags, album.theme_clusters, embedder, cfg.band_thresholds)
return ThemeMatchResult(band=band, score=diag["score"], per_cluster=diag["per_cluster"])
```

⚠ 返回类型从 `float` 改为 `ThemeMatchResult` (类比 ADR-0005 location_match 模式), `compute_growth_bands` 直接读 `band`.

### 测试

- **新建** `tests/unit/test_theme_aggregation.py` (spec §七 Case 1-5 + 截断 5 行 + 边界 case)
- **改** `tests/fixtures/albums/lakeside_album.json` (删 theme_tags_set/dominant_theme, 加 theme_clusters + theme_aggregated_at)
- **改** `tests/unit/test_growth_features.py` (适配新字段)
- **重生** 10 个 golden

---

## 5 · 决策回滚条件

如果 v0.2 真 Qwen 接入后表现劣于预期, 触发以下任一条件即回滚:

- **同义词识别准确率 < 60%** — 用 100 张人工标注 case 上验证 (湖边/水边/湖面等同义对识别率)
- **embedding 服务 P99 > 200ms** — 影响生长决策 SLA
- **簇截断丢失重要长尾 > 15%** — 用户主观调研发现"我的相册被错判"

回滚动作: `config/theme_aggregation.yaml` `embedding.provider: "mock"` + 单独 PR 改 ThemeMatchResult 兼容字面 jaccard 子函数. (但当前 demo 不留 feature flag — 见 §2.5)

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-008 §8b (theme_tags_set 聚合) | 待决, 推荐 v0.1 简单并集 / P0.5 频次≥2 | **被本 ADR 关闭** — 直接跳到语义聚类 + 频次加权 |
| OQ-008 §8c (dominant_theme) | 待决, 推荐最高频 + 字典序 | **失效** — dominant_theme 不在 fingerprint 内, 移到 Mini Album 完整 schema, 由 LLM 综述输出 |
| OQ-018 (新增) | — | Qwen3-Embedding-0.6B 真实接入与基准测试 (v0.2 P0) |
| OQ-019 (新增) | — | 语义聚类参数调优 (merge_similarity / relative_threshold / band_thresholds) |

OQ-008 §8d/8e/8h/8i 与本 ADR 无关, 状态不变.

---

## 7 · 后续动作

1. ✅ 本 ADR 写完
2. ✅ `docs/14_theme_aggregation.md` 写完整算法规范 (Case 1-5 + 截断 case 表 + 不变性)
3. ✅ `docs/10_mini_album_schema.md` 第三节"theme_tags_set 等待 OQ-008"段重写
4. ✅ `docs/02_data_contracts.md` MiniAlbumFingerprint 字段更新
5. ✅ `docs/04_truth_table_growth.md` + `docs/07_dimension_thresholds.md` theme 段
6. ✅ `docs/00/01/11/12` 同步
7. ✅ `config/theme_aggregation.yaml` 新建
8. ✅ `src/contracts/theme.py` 新建; `src/contracts/growth.py` 字段调整
9. ✅ `src/mini_album/theme_aggregation.py` 实现 (纯 Python)
10. ✅ `src/features/growth_features.py::_compute_theme_overlap` 重写
11. ✅ 单测 + fixture + golden 重生
12. ✅ spec 归档 `archive/specs/Cluster_Aggregation_Spec.md`
13. ⏳ v0.2: OQ-018 接真 Qwen + 100 case 基准测试
14. ⏳ v0.2/0.5: OQ-019 网格搜索调优
