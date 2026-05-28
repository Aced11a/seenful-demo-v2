"""Theme 语义簇聚合 + 匹配单测 (ADR-0008).

覆盖:
  · cosine_similarity / l2_normalize / weighted_centroid
  · agglomerative_cluster_cosine (单点 / 同义合并 / 阈值不合并)
  · aggregate_theme_clusters (空 / 单 tag / 多簇 / 同义合并)
  · truncate_by_relative_threshold (spec §四 5 行 case 表)
  · match_theme (spec §七 Case 1-5)
  · MockEmbedder 确定性 + 同义组 cosine ≈ 1
  · build_theme_clusters 高层入口
  · get_embedder 切换

参考: docs/14_theme_aggregation.md, decisions/0008-theme-semantic-clustering.md.
"""
from __future__ import annotations

import math

import pytest

from src.contracts import SemanticCluster
from src.contracts.l1_output import ImageFacts
from src.contracts import L1Output
from src.mini_album.theme_aggregation import (
    MockEmbedder,
    QwenEmbedder,
    aggregate_theme_clusters,
    agglomerative_cluster_cosine,
    build_theme_clusters,
    cosine_similarity,
    get_embedder,
    l2_normalize,
    match_theme,
    truncate_by_relative_threshold,
    weighted_centroid,
)

BAND_CFG = {"strong": 0.75, "medium": 0.55, "weak": 0.35}


# ═════════════════════════════════════════════════════════════════
# 向量工具
# ═════════════════════════════════════════════════════════════════

class TestCosine:
    def test_identical(self):
        assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestL2Normalize:
    def test_already_unit(self):
        v = l2_normalize([1.0, 0.0])
        assert v == [1.0, 0.0]

    def test_scales_to_unit(self):
        v = l2_normalize([3.0, 4.0])
        assert v == pytest.approx([0.6, 0.8])

    def test_zero_returns_zero(self):
        assert l2_normalize([0.0, 0.0]) == [0.0, 0.0]


class TestWeightedCentroid:
    def test_equal_weights(self):
        v = weighted_centroid([[1.0, 0.0], [0.0, 1.0]], [1, 1])
        # 平均 (0.5, 0.5) 归一化 ≈ (0.707, 0.707)
        assert v == pytest.approx([math.sqrt(0.5), math.sqrt(0.5)])

    def test_weighted_pull(self):
        # 权重 3:1, 应该偏向第一个
        v = weighted_centroid([[1.0, 0.0], [0.0, 1.0]], [3, 1])
        assert v[0] > v[1]

    def test_empty(self):
        assert weighted_centroid([], []) == []


# ═════════════════════════════════════════════════════════════════
# 层次聚类
# ═════════════════════════════════════════════════════════════════

class TestAgglomerative:
    def test_empty(self):
        assert agglomerative_cluster_cosine([], distance_threshold=0.25) == []

    def test_single_point(self):
        assert agglomerative_cluster_cosine([[1.0, 0.0]], 0.25) == [0]

    def test_two_identical_merge(self):
        labels = agglomerative_cluster_cosine(
            [[1.0, 0.0], [1.0, 0.0]],
            distance_threshold=0.25,
        )
        assert labels[0] == labels[1]

    def test_two_orthogonal_dont_merge(self):
        # cos=0 → dist=1 > threshold=0.25
        labels = agglomerative_cluster_cosine(
            [[1.0, 0.0], [0.0, 1.0]],
            distance_threshold=0.25,
        )
        assert labels[0] != labels[1]

    def test_mock_synonym_group_merges(self):
        # 走 MockEmbedder: 湖边/水边/湖面 同组 → 应聚成 1 簇
        emb = MockEmbedder(dim=16)
        vecs = emb(["湖边", "水边", "湖面"])
        labels = agglomerative_cluster_cosine(vecs, distance_threshold=1 - 0.75)
        assert labels[0] == labels[1] == labels[2]

    def test_mock_different_groups_dont_merge(self):
        # 湖边 vs 夕阳: 不同组
        emb = MockEmbedder(dim=16)
        vecs = emb(["湖边", "夕阳"])
        labels = agglomerative_cluster_cosine(vecs, distance_threshold=1 - 0.75)
        assert labels[0] != labels[1]


# ═════════════════════════════════════════════════════════════════
# aggregate_theme_clusters
# ═════════════════════════════════════════════════════════════════

class TestAggregate:
    def test_empty(self):
        emb = MockEmbedder()
        assert aggregate_theme_clusters([], emb) == []

    def test_single_unique_tag(self):
        emb = MockEmbedder()
        clusters = aggregate_theme_clusters(["lakeside"], emb)
        assert len(clusters) == 1
        assert clusters[0].representative == "lakeside"
        assert clusters[0].frequency == 1
        assert clusters[0].members == {"lakeside": 1}

    def test_repeated_same_tag_counted(self):
        emb = MockEmbedder()
        clusters = aggregate_theme_clusters(["lakeside", "lakeside", "lakeside"], emb)
        assert len(clusters) == 1
        assert clusters[0].frequency == 3
        assert clusters[0].members == {"lakeside": 3}

    def test_synonym_merge_into_one_cluster(self):
        # 湖边 / 水边 / 湖面 同组, 应合并; 桥 / 夕阳 各独立
        emb = MockEmbedder()
        clusters = aggregate_theme_clusters(
            ["湖边", "水边", "湖面", "桥", "夕阳"], emb,
            merge_similarity=0.75,
        )
        # 找出湖簇 (含 3 个成员)
        lake_cluster = next(c for c in clusters if len(c.members) == 3)
        assert set(lake_cluster.members.keys()) == {"湖边", "水边", "湖面"}
        assert lake_cluster.frequency == 3
        # 桥 / 夕阳 各成独立簇
        singles = [c for c in clusters if len(c.members) == 1]
        assert len(singles) == 2
        single_reprs = {c.representative for c in singles}
        assert single_reprs == {"桥", "夕阳"}

    def test_representative_is_max_frequency(self):
        # 湖边×3 / 水边×1 → 同组合并, representative=湖边
        emb = MockEmbedder()
        clusters = aggregate_theme_clusters(
            ["湖边", "湖边", "湖边", "水边"], emb,
        )
        assert len(clusters) == 1
        assert clusters[0].representative == "湖边"
        assert clusters[0].frequency == 4
        assert clusters[0].members == {"湖边": 3, "水边": 1}

    def test_sorted_by_frequency_desc(self):
        emb = MockEmbedder()
        clusters = aggregate_theme_clusters(
            ["夕阳"] + ["湖边"] * 5 + ["桥"] * 2,
            emb,
        )
        freqs = [c.frequency for c in clusters]
        assert freqs == sorted(freqs, reverse=True)


# ═════════════════════════════════════════════════════════════════
# 截断 (spec §四 case 验证表)
# ═════════════════════════════════════════════════════════════════

def _mk_cluster(freq: int) -> SemanticCluster:
    """构造仅含 frequency 字段的最小 cluster (其他字段填占位)."""
    return SemanticCluster(
        representative="x",
        members={"x": freq},
        frequency=freq,
        centroid=[1.0] + [0.0] * 15,
    )


class TestTruncate:
    def test_empty_input(self):
        assert truncate_by_relative_threshold([]) == []

    @pytest.mark.parametrize(
        "freqs, expected_kept",
        [
            ([7, 4, 3, 3, 3], 5),     # max=7, t=2.8, 全保留
            ([9, 8, 2, 2, 1], 2),     # max=9, t=3.6, [9,8]
            ([5, 4, 3, 2, 1], 4),     # max=5, t=2.0, [5,4,3,2]
            ([10, 1, 1, 1, 1], 1),    # max=10, t=4.0, [10]
            ([3, 3, 3, 3, 3], 5),     # max=3, t=1.2, 全保留
        ],
    )
    def test_spec_table(self, freqs, expected_kept):
        clusters = [_mk_cluster(f) for f in freqs]
        result = truncate_by_relative_threshold(
            clusters, max_keep=5, relative_threshold=0.4,
        )
        assert len(result) == expected_kept

    def test_max_keep_caps(self):
        # 10 个 frequency=10 的簇, max_keep=5 应该截断到 5
        clusters = [_mk_cluster(10) for _ in range(10)]
        result = truncate_by_relative_threshold(
            clusters, max_keep=5, relative_threshold=0.4,
        )
        assert len(result) == 5

    def test_at_least_one(self):
        # 单簇即使没人能 ≥ 阈值, 也至少保留 1 个
        clusters = [_mk_cluster(1)]
        result = truncate_by_relative_threshold(
            clusters, max_keep=5, relative_threshold=0.4,
        )
        assert len(result) == 1


# ═════════════════════════════════════════════════════════════════
# match_theme (spec §七 Case 1-5)
# ═════════════════════════════════════════════════════════════════

def _build_lakeside_fingerprint(embedder: MockEmbedder) -> list[SemanticCluster]:
    """构造 spec §七 假设的指纹 (湖×6 / 夕阳×3 / 桥×1)."""
    tags = ["湖边"] * 6 + ["夕阳"] * 3 + ["桥"] * 1
    clusters = aggregate_theme_clusters(tags, embedder, merge_similarity=0.75)
    # 不截断, 保留 3 簇做 spec case 验证
    return clusters


class TestMatchTheme:
    """spec §七 Case 1-5 验证.

    用 dim=64 (与 yaml 一致), 16 维下 hash 偶发 spike 会导致 case 5 假阳.
    """

    def setup_method(self):
        self.embedder = MockEmbedder(dim=64)
        self.clusters = _build_lakeside_fingerprint(self.embedder)

    def test_case1_strong_full_hit(self):
        # 湖水 + 夕阳 → 湖簇/夕阳簇都命中 → strong
        result = match_theme(
            ["湖水", "夕阳"], self.clusters, self.embedder, BAND_CFG,
        )
        assert result.band == "strong"
        assert result.score >= 0.75

    def test_case2_medium_partial(self):
        # 湖面 + 波光 (都映射到湖簇) → 主簇满命中但夕阳簇没命中 → medium
        # mock 表里波光也在 lake 组, 所以两个 tag 都命中湖簇
        result = match_theme(
            ["湖面", "波光"], self.clusters, self.embedder, BAND_CFG,
        )
        # 湖簇 ≈ 1.0 × 0.6 = 0.6; 夕阳/桥不命中 (low) → 大约 0.6 范围
        assert result.band == "medium"
        assert 0.55 <= result.score < 0.75

    def test_case3_only_low_freq_cluster_hit(self):
        # 桥 + 石栏 (都在 bridge 组) → 桥簇满命中, 但权重只 0.1
        # 主簇没命中 → 综合应该 weak 或 none (依阈值)
        result = match_theme(
            ["桥", "石栏"], self.clusters, self.embedder, BAND_CFG,
        )
        # 桥簇贡献 ≈ 1.0 × 0.1 = 0.1; 湖簇/夕阳簇命中度很低
        # 综合 < 0.35 → none
        assert result.band == "none"

    def test_case4_unrelated_tags(self):
        # 美食 + 餐厅 (food 组) — 完全无关
        result = match_theme(
            ["美食", "餐厅"], self.clusters, self.embedder, BAND_CFG,
        )
        assert result.band == "none"

    def test_case5_many_unrelated_no_false_positive(self):
        # 反假阳: 8 个 unrelated tag 不应该因数量假阳
        new_tags = ["美食", "聚餐", "啤酒", "朋友", "夜晚", "餐桌", "甜品", "酒水"]
        result = match_theme(new_tags, self.clusters, self.embedder, BAND_CFG)
        assert result.band == "none"

    def test_empty_new_tags(self):
        result = match_theme([], self.clusters, self.embedder, BAND_CFG)
        assert result.band == "none"
        assert result.reason == "no_tags"

    def test_empty_clusters(self):
        result = match_theme(["lakeside"], [], self.embedder, BAND_CFG)
        assert result.band == "none"
        assert result.reason == "empty_clusters"

    def test_per_cluster_diag_complete(self):
        result = match_theme(
            ["湖水", "夕阳"], self.clusters, self.embedder, BAND_CFG,
        )
        # 应该有 3 簇 (湖/夕阳/桥) 的诊断
        assert len(result.per_cluster) == 3
        for diag in result.per_cluster:
            assert "representative" in diag
            assert "frequency" in diag
            assert "weight" in diag
            assert "max_sim" in diag
            assert "matched_by" in diag
            assert "contribution" in diag
        # 权重应该归一化到 1
        total_w = sum(d["weight"] for d in result.per_cluster)
        assert total_w == pytest.approx(1.0)


# ═════════════════════════════════════════════════════════════════
# MockEmbedder
# ═════════════════════════════════════════════════════════════════

class TestMockEmbedder:
    def test_deterministic_same_input(self):
        e1 = MockEmbedder(dim=16)
        e2 = MockEmbedder(dim=16)
        assert e1(["lakeside"])[0] == e2(["lakeside"])[0]

    def test_synonym_group_high_cosine(self):
        # 湖边 / 水边 同组, cosine 应 ≈ 0.99+
        emb = MockEmbedder()
        v1, v2 = emb(["湖边", "水边"])
        assert cosine_similarity(v1, v2) > 0.95

    def test_different_group_low_cosine(self):
        # 湖边 vs 夕阳 不同组, cosine 应低
        emb = MockEmbedder()
        v1, v2 = emb(["湖边", "夕阳"])
        assert cosine_similarity(v1, v2) < 0.5

    def test_unknown_tag_via_hash(self):
        # 未知 tag 走 hash → 单位向量
        emb = MockEmbedder()
        v = emb(["zzz_totally_unknown_tag"])[0]
        # 应该归一化
        norm = math.sqrt(sum(x * x for x in v))
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_unknown_vs_known_low_cosine(self):
        # 未知 tag 与已知组的 cosine 大概率 < 0.5
        emb = MockEmbedder()
        v_known, v_unknown = emb(["lakeside", "zzz_random_xyz"])
        assert cosine_similarity(v_known, v_unknown) < 0.5

    def test_output_dim_matches_config(self):
        emb = MockEmbedder(dim=32)
        v = emb(["lakeside"])[0]
        assert len(v) == 32


# ═════════════════════════════════════════════════════════════════
# build_theme_clusters 高层入口
# ═════════════════════════════════════════════════════════════════

def _mk_l1(pid: str, tags: list[str]) -> L1Output:
    return L1Output(
        photo_id=pid,
        user_id="user_demo",
        individual_title="t",
        individual_understanding="x" * 70,
        image_facts=ImageFacts(),
        theme_tags=tags,
    )


class TestBuildThemeClusters:
    def test_build_from_photos(self):
        photos = [
            _mk_l1("p1", ["lakeside", "spring"]),
            _mk_l1("p2", ["lakeside", "trees"]),
            _mk_l1("p3", ["lakeside", "trees"]),
        ]
        clusters, agg_at = build_theme_clusters(photos)
        # lakeside 3 次最高频
        assert clusters[0].representative == "lakeside"
        assert clusters[0].frequency == 3
        # truncate 后至少 1 个
        assert len(clusters) >= 1
        assert agg_at is not None

    def test_empty_photos(self):
        clusters, agg_at = build_theme_clusters([])
        assert clusters == []


# ═════════════════════════════════════════════════════════════════
# get_embedder 切换
# ═════════════════════════════════════════════════════════════════

class TestGetEmbedder:
    def test_mock_provider(self):
        cfg = {"embedding": {"provider": "mock", "dim": 16}}
        emb = get_embedder(cfg)
        assert isinstance(emb, MockEmbedder)

    def test_qwen_provider_returns_real_or_friendly_error(self):
        """ADR-0020: QwenEmbedder 现真实现 sentence-transformers.

        未装包时抛友好 RuntimeError ('sentence-transformers not installed').
        装包后可调用 (跑真模型, 本测试不验证质量).
        """
        cfg = {"embedding": {"provider": "qwen3-embedding-0.6b"}}
        emb = get_embedder(cfg)
        assert isinstance(emb, QwenEmbedder)
        try:
            import sentence_transformers   # noqa: F401
            # 装了就跑 (但跳过质量校验, 因为依赖网络下载模型)
        except ImportError:
            # 未装包时, 调用应抛 RuntimeError 友好提示
            with pytest.raises(RuntimeError, match="sentence-transformers not installed"):
                emb(["lakeside"])

    def test_unknown_provider_raises(self):
        cfg = {"embedding": {"provider": "wat"}}
        with pytest.raises(ValueError, match="unknown.*provider"):
            get_embedder(cfg)

    def test_default_provider_is_mock(self):
        # 缺省时走 mock
        cfg: dict = {}
        emb = get_embedder(cfg)
        assert isinstance(emb, MockEmbedder)
