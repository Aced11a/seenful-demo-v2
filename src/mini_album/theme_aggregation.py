"""Theme 语义簇聚合 + 匹配 (路径 A theme 维度) · 纯 Python 实现.

参考:
  docs/14_theme_aggregation.md
  decisions/0008-theme-semantic-clustering.md
  archive/specs/Cluster_Aggregation_Spec.md (原始 spec, 已归档)

提供:
  · cosine_similarity              — 两向量余弦
  · l2_normalize                   — 向量 L2 归一化
  · weighted_centroid              — 频次加权平均 + 归一化
  · agglomerative_cluster_cosine   — 层次聚类 (average linkage, cosine 距离)
  · aggregate_theme_clusters       — spec §四 Step 1-4
  · truncate_by_relative_threshold — spec §四 Step 6
  · match_theme                    — spec §五 (1 张新照片 vs 老相册)
  · build_theme_clusters           — 高层入口, 从 L1 photos 构造
  · MockEmbedder / get_embedder    — embedding 服务

依赖: 仅 stdlib (math, hashlib, collections). 不引 numpy/sklearn/sentence_transformers.
v0.1 demo 用 MockEmbedder; v0.2 接 Qwen3-Embedding-0.6B (OQ-018).
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from datetime import datetime
from typing import Callable

from src.contracts import (
    L1Output,
    SemanticCluster,
    ThemeMatchResult,
)
from src.policy.config_loader import load_config

# embed_fn 签名: list[tag_str] -> list[unit_vector (list[float])]
EmbedFn = Callable[[list[str]], list[list[float]]]


# ═════════════════════════════════════════════════════════════════
# 向量工具
# ═════════════════════════════════════════════════════════════════

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """两向量余弦相似度. 假定输入已归一化, 但仍做最后除法保险."""
    if len(v1) != len(v2):
        raise ValueError(f"dim mismatch: {len(v1)} vs {len(v2)}")
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def l2_normalize(v: list[float]) -> list[float]:
    """L2 归一化为单位向量. 零向量返回零向量."""
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        return list(v)
    return [x / norm for x in v]


def weighted_centroid(
    vectors: list[list[float]],
    weights: list[int],
) -> list[float]:
    """按权重平均向量, 再 L2 归一化."""
    if not vectors:
        return []
    if len(vectors) != len(weights):
        raise ValueError("vectors and weights length mismatch")
    dim = len(vectors[0])
    total_w = sum(weights)
    if total_w == 0:
        return [0.0] * dim
    avg = [0.0] * dim
    for vec, w in zip(vectors, weights):
        for i in range(dim):
            avg[i] += vec[i] * w
    avg = [x / total_w for x in avg]
    return l2_normalize(avg)


# ═════════════════════════════════════════════════════════════════
# 层次聚类 (Agglomerative · average linkage · cosine 距离)
# ═════════════════════════════════════════════════════════════════

def agglomerative_cluster_cosine(
    embeddings: list[list[float]],
    distance_threshold: float,
) -> list[int]:
    """对向量集做凝聚式层次聚类, 返回每点的簇 label.

    算法 (n ≤ 30 用 O(n²) 距离矩阵 + O(n³) 主循环, 足够快):
      1. 每点自成簇
      2. 反复合并距离最近的两簇, 直到所有簇间距离都 > threshold
      3. 簇间距离用 average linkage (所有跨簇点对距离的平均)
      4. 点距用 1 - cosine_similarity

    参考: docs/14 §三 Step 3, spec §四 (sklearn AgglomerativeClustering 等价行为).
    """
    n = len(embeddings)
    if n == 0:
        return []
    if n == 1:
        return [0]

    # 距离矩阵 (1 - cosine)
    def point_dist(i: int, j: int) -> float:
        return 1.0 - cosine_similarity(embeddings[i], embeddings[j])

    # 每个簇用其包含的点 index list 表示
    clusters: list[list[int]] = [[i] for i in range(n)]

    def cluster_dist(a: list[int], b: list[int]) -> float:
        """Average linkage: 所有跨簇点对距离的平均."""
        total = 0.0
        count = 0
        for i in a:
            for j in b:
                total += point_dist(i, j)
                count += 1
        return total / count if count > 0 else float("inf")

    while len(clusters) > 1:
        # 找最近的两簇
        best_d = float("inf")
        best_pair = (-1, -1)
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = cluster_dist(clusters[i], clusters[j])
                if d < best_d:
                    best_d = d
                    best_pair = (i, j)
        # 如果最近的两簇距离已超阈值, 停止合并
        if best_d > distance_threshold:
            break
        # 合并 (j 并入 i, 移除 j)
        i, j = best_pair
        clusters[i] = clusters[i] + clusters[j]
        clusters.pop(j)

    # 输出每点的 label
    labels = [-1] * n
    for cid, members in enumerate(clusters):
        for idx in members:
            labels[idx] = cid
    return labels


# ═════════════════════════════════════════════════════════════════
# 聚合 (spec §四 Step 1-4)
# ═════════════════════════════════════════════════════════════════

def aggregate_theme_clusters(
    tags: list[str],
    embed_fn: EmbedFn,
    merge_similarity: float = 0.75,
) -> list[SemanticCluster]:
    """对全部照片的 tag 流做语义簇聚合, 返回按频次降序的簇列表 (未截断).

    参考: docs/14 §三 Step 1-4.

    流程:
      Step 1: Counter 频次统计 + 字面去重
      Step 2: 批量 embed (相同字面只 embed 一次)
      Step 3: 层次聚类 (cosine + average linkage)
      Step 4: 每簇加权聚合 (representative = 簇内频次最高, centroid = 频次加权)
      Step 5: 按 frequency 降序
    """
    if not tags:
        return []

    # Step 1: 频次统计
    tag_counts: Counter[str] = Counter(tags)
    unique_tags = list(tag_counts.keys())

    # Step 2: 批量 embed
    embeddings = embed_fn(unique_tags)
    if len(embeddings) != len(unique_tags):
        raise ValueError("embed_fn returned wrong length")

    # 边界: 单 tag
    if len(unique_tags) == 1:
        tag = unique_tags[0]
        return [SemanticCluster(
            representative=tag,
            members={tag: tag_counts[tag]},
            frequency=tag_counts[tag],
            centroid=l2_normalize(embeddings[0]),
        )]

    # Step 3: 层次聚类
    labels = agglomerative_cluster_cosine(
        embeddings,
        distance_threshold=1.0 - merge_similarity,
    )

    # Step 4: 每簇聚合
    cluster_buckets: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        cluster_buckets.setdefault(label, []).append(idx)

    clusters: list[SemanticCluster] = []
    for member_idx in cluster_buckets.values():
        member_dict = {
            unique_tags[i]: tag_counts[unique_tags[i]] for i in member_idx
        }
        total_freq = sum(member_dict.values())
        representative = max(member_dict.items(), key=lambda x: x[1])[0]
        member_embs = [embeddings[i] for i in member_idx]
        weights = [member_dict[unique_tags[i]] for i in member_idx]
        centroid = weighted_centroid(member_embs, weights)
        clusters.append(SemanticCluster(
            representative=representative,
            members=member_dict,
            frequency=total_freq,
            centroid=centroid,
        ))

    # Step 5: 按频率降序
    clusters.sort(key=lambda c: c.frequency, reverse=True)
    return clusters


# ═════════════════════════════════════════════════════════════════
# 截断 (spec §四 Step 6)
# ═════════════════════════════════════════════════════════════════

def truncate_by_relative_threshold(
    clusters: list[SemanticCluster],
    max_keep: int = 5,
    relative_threshold: float = 0.4,
) -> list[SemanticCluster]:
    """按 frequency ≥ max × relative_threshold 截断, 上限 max_keep, 至少 1 个.

    输入要求: clusters 已按 frequency 降序排好.
    参考: docs/14 §三 Step 6.
    """
    if not clusters:
        return []
    max_freq = clusters[0].frequency
    threshold = max_freq * relative_threshold
    kept: list[SemanticCluster] = []
    for c in clusters[:max_keep]:
        if c.frequency >= threshold:
            kept.append(c)
        else:
            break   # 频次降序, 后面只会更小
    return kept if kept else [clusters[0]]


# ═════════════════════════════════════════════════════════════════
# 匹配 (spec §五)
# ═════════════════════════════════════════════════════════════════

def match_theme(
    new_tags: list[str],
    clusters: list[SemanticCluster],
    embed_fn: EmbedFn,
    band_thresholds: dict[str, float],
) -> ThemeMatchResult:
    """1 张新照片 vs 老相册 theme_clusters 的匹配, 返回 ThemeMatchResult.

    band_thresholds 形如 {"strong": 0.75, "medium": 0.55, "weak": 0.35}.
    参考: docs/14 §四.
    """
    if not new_tags:
        return ThemeMatchResult(
            band="none", score=0.0, per_cluster=[], reason="no_tags",
        )
    if not clusters:
        return ThemeMatchResult(
            band="none", score=0.0, per_cluster=[], reason="empty_clusters",
        )

    # 去重保序
    unique_new = list(dict.fromkeys(new_tags))
    new_embs = embed_fn(unique_new)

    # 每簇被命中的最强相似度
    per_cluster_max_sim: list[float] = []
    per_cluster_matched_by: list[str] = []
    for c in clusters:
        sims = [cosine_similarity(e, c.centroid) for e in new_embs]
        best_i = max(range(len(sims)), key=lambda i: sims[i])
        per_cluster_max_sim.append(sims[best_i])
        per_cluster_matched_by.append(unique_new[best_i])

    # 簇 frequency 归一化作权重
    total_freq = sum(c.frequency for c in clusters)
    if total_freq == 0:
        return ThemeMatchResult(
            band="none", score=0.0, per_cluster=[], reason="empty_clusters",
        )
    weights = [c.frequency / total_freq for c in clusters]

    # 加权和 (核心公式)
    score = sum(s * w for s, w in zip(per_cluster_max_sim, weights))
    # 浮点容差: 把 [0,1] 外的微量误差夹住
    score = max(0.0, min(1.0, score))

    # 分档
    if score >= band_thresholds["strong"]:
        band: str = "strong"
    elif score >= band_thresholds["medium"]:
        band = "medium"
    elif score >= band_thresholds["weak"]:
        band = "weak"
    else:
        band = "none"

    # 诊断
    per_cluster_diag: list[dict] = []
    for c, w, s, m in zip(
        clusters, weights, per_cluster_max_sim, per_cluster_matched_by,
    ):
        per_cluster_diag.append({
            "representative": c.representative,
            "frequency": c.frequency,
            "weight": w,
            "max_sim": s,
            "matched_by": m,
            "contribution": s * w,
        })

    return ThemeMatchResult(
        band=band,          # type: ignore[arg-type]
        score=score,
        per_cluster=per_cluster_diag,
    )


# ═════════════════════════════════════════════════════════════════
# 高层入口: 从 L1 photos 构造 theme_clusters
# ═════════════════════════════════════════════════════════════════

def build_theme_clusters(
    photos: list[L1Output],
    embed_fn: EmbedFn | None = None,
    cfg: dict | None = None,
) -> tuple[list[SemanticCluster], datetime]:
    """从相册照片列表生成 (theme_clusters, aggregated_at).

    流程: 提取所有 theme_tags → aggregate_theme_clusters → truncate.
    参考: docs/14 §六 (增量更新策略 = 全量重算).
    """
    cfg = cfg or load_config("theme_aggregation.yaml")["theme_aggregation"]
    embed_fn = embed_fn or get_embedder(cfg)

    all_tags: list[str] = []
    for p in photos:
        all_tags.extend(p.theme_tags)

    raw_clusters = aggregate_theme_clusters(
        all_tags, embed_fn,
        merge_similarity=float(cfg["merge_similarity"]),
    )
    truncated = truncate_by_relative_threshold(
        raw_clusters,
        max_keep=int(cfg["max_clusters"]),
        relative_threshold=float(cfg["relative_threshold"]),
    )
    return truncated, datetime.now()


# ═════════════════════════════════════════════════════════════════
# Embedding 服务 (MockEmbedder / QwenEmbedder 占位)
# ═════════════════════════════════════════════════════════════════

# 手工 fixture 表 (mock 用): 同义 tag 映射到同一向量基底,
# 测试集中验证算法逻辑正确性. 真模型质量验证见 OQ-018.
#
# 设计原则:
#   - 同义组内 cosine ≈ 1.0
#   - 不同组间 cosine 较低 (< 0.3)
#   - 不在表里的 tag 走 hash → 单位向量 (与任何固定基底不会相似)
_MOCK_FIXTURE: dict[str, str] = {
    # 湖 同义簇
    "lakeside": "lake",
    "湖边": "lake",
    "水边": "lake",
    "湖面": "lake",
    "湖水": "lake",
    "湖": "lake",
    "lake": "lake",
    "波光": "lake",
    "lakefront": "lake",

    # 夕阳 同义簇
    "sunset": "sunset",
    "夕阳": "sunset",
    "晚霞": "sunset",
    "dusk": "sunset",
    "暮色": "sunset",

    # 桥 同义簇
    "bridge": "bridge",
    "桥": "bridge",
    "石栏": "bridge",
    "石桥": "bridge",

    # spring / trees / slow_life — 各自独立
    "spring": "spring",
    "春": "spring",
    "trees": "trees",
    "树": "trees",
    "slow_life": "slow_life",
    "慢生活": "slow_life",

    # 餐厅类 (无关组, 用于 Case 4/5)
    "美食": "food",
    "餐厅": "food",
    "聚餐": "food",
    "啤酒": "food",
    "餐桌": "food",
    "甜品": "food",
    "酒水": "food",
    "朋友": "people",
    "夜晚": "night",
}


class MockEmbedder:
    """确定性 mock embedding (ADR-0008 §2.5).

    设计:
      - 同义组 tag → 同一基底向量 (cosine ≈ 1.0)
      - 未知 tag → md5 hash 派生向量, 与任何基底正交化倾向 (cosine 一般 < 0.3)
      - 输出固定 dim (默认 16, 与 yaml 一致)
      - 100% 确定性 (相同输入相同输出)

    测试目标: 算法**逻辑正确性** (聚合 / 截断 / 加权匹配 / 分档).
    不测语义识别质量 — 那是 v0.2 OQ-018 真 Qwen 接入时的事.
    """

    def __init__(self, dim: int = 16):
        self.dim = dim
        # 同义组基底向量 (每组用一个固定 seed 生成)
        self._basis_cache: dict[str, list[float]] = {}

    def _basis_for(self, group: str) -> list[float]:
        if group in self._basis_cache:
            return self._basis_cache[group]
        # 用 group 名做 seed, 派生 dim 维向量, 再归一化
        v = self._hash_to_vector(group + "::basis")
        self._basis_cache[group] = v
        return v

    def _hash_to_vector(self, key: str) -> list[float]:
        """md5(key) → dim 维 [-1, 1] 向量, 再 L2 归一化."""
        v: list[float] = []
        nonce = 0
        while len(v) < self.dim:
            h = hashlib.md5(f"{key}:{nonce}".encode("utf-8")).digest()
            for b in h:
                v.append((b / 255.0) * 2 - 1)   # [0,255] -> [-1,1]
                if len(v) >= self.dim:
                    break
            nonce += 1
        return l2_normalize(v)

    def __call__(self, tags: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for tag in tags:
            group = _MOCK_FIXTURE.get(tag)
            if group is not None:
                # 同义组: 用组基底 + 极小扰动 (保持组内 cosine 接近 1)
                base = self._basis_for(group)
                # 用 tag 字面派生微小扰动, 让同组内不同字面 cosine ≈ 0.99
                perturb = self._hash_to_vector(tag + "::perturb")
                mixed = [0.99 * b + 0.01 * p for b, p in zip(base, perturb)]
                out.append(l2_normalize(mixed))
            else:
                # 未知 tag: 走 hash 派生, 与任何基底大概率不相似
                out.append(self._hash_to_vector(tag))
        return out


class QwenEmbedder:
    """ADR-0020: Qwen3-Embedding-0.6B 本地接入 (sentence-transformers).

    首次加载: 自动下载 ~1.2GB 模型到 ~/.cache/huggingface/
    后续调用: 内存 cache, 5-20ms/句 (CPU)
    输出维度: 1024 (跟 config dim 一致才能比较)
    """

    _instance_cache: dict[str, object] = {}     # 全局 model cache, 避免重复加载

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B"):
        self.model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return
        if self.model_name in QwenEmbedder._instance_cache:
            self._model = QwenEmbedder._instance_cache[self.model_name]
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers not installed. Run: "
                "pip install sentence-transformers"
            ) from e
        self._model = SentenceTransformer(self.model_name)
        QwenEmbedder._instance_cache[self.model_name] = self._model

    def __call__(self, tags: list[str]) -> list[list[float]]:
        if not tags:
            return []
        self._ensure_model()
        # sentence-transformers 返回 numpy array, 转 list[list[float]]
        embeddings = self._model.encode(tags, convert_to_numpy=True)
        return [list(map(float, vec)) for vec in embeddings]


def get_embedder(cfg: dict) -> EmbedFn:
    """按 config 选择 embedder.

    cfg 是 theme_aggregation 段 dict (已下钻一层).
    ADR-0008 §2.5: demo 不留 silent fallback, provider 不能用直接报错.
    """
    embedding_cfg = cfg.get("embedding", {})
    provider = embedding_cfg.get("provider", "mock")
    dim = int(embedding_cfg.get("dim", 16))

    if provider == "mock":
        return MockEmbedder(dim=dim)
    if provider == "qwen3-embedding-0.6b":
        model_name = embedding_cfg.get("model") or "Qwen/Qwen3-Embedding-0.6B"
        return QwenEmbedder(model_name=model_name)
    raise ValueError(
        f"unknown theme_aggregation.embedding.provider: {provider!r}. "
        f"supported: 'mock' | 'qwen3-embedding-0.6b'."
    )
