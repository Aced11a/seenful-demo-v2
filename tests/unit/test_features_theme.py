"""路径 B theme 维度单测 (ADR-0013 v0.3 双层判定).

覆盖:
  - TH.1 strong (主 coverage=1.0)
  - TH.2/TH.3 + 次字段升降档
  - TH.4 weak / TH.5 none
  - jaccard_multi (向后兼容, growth_features 仍用)

参考: docs/19_path_b_theme.md, decisions/0013-path-b-theme-two-tier-cluster.md
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.contracts import L1Output, ThemeShape
from src.contracts.l1_output import SemanticFacts
from src.features.theme import build_theme_feature, jaccard_multi


def make_photo(
    pid: str,
    theme_tags: list[str] | None = None,
    main_subjects: list[str] | None = None,
) -> L1Output:
    return L1Output(
        photo_id=pid,
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=datetime(2026, 5, 1, 12, 0),
        theme_tags=theme_tags or [],
        semantic_facts=SemanticFacts(main_subjects=main_subjects or []),
    )


# ─── jaccard_multi 向后兼容 ──────────────────────────────────


class TestJaccardMulti:
    def test_empty(self):
        assert jaccard_multi([]) == 0.0
        assert jaccard_multi([set()]) == 0.0

    def test_two_sets_full_overlap(self):
        assert jaccard_multi([{"a", "b"}, {"a", "b"}]) == 1.0

    def test_two_sets_no_overlap(self):
        assert jaccard_multi([{"a"}, {"b"}]) == 0.0

    def test_partial_overlap(self):
        assert jaccard_multi([{"a", "b"}, {"a", "c"}]) == pytest.approx(1 / 3)


# ─── TH.1 strong (主字段全员一致) ──────────────────────────


class TestTH0MultiParallel:
    """ADR-0022: 多并列主簇覆盖 100% → medium (修 B5 误判)."""

    def test_two_parallel_clusters_full_coverage(self):
        # 3 张 work 系 + 3 张苏州系, 真 Qwen 聚成 2 簇都覆盖 → coverage=1.0 + cluster_count=2
        ps = [
            make_photo("p1", theme_tags=["work", "conference"]),
            make_photo("p2", theme_tags=["work", "presentation"]),
            make_photo("p3", theme_tags=["work", "business"]),
            make_photo("p4", theme_tags=["zhuozheng", "garden"]),
            make_photo("p5", theme_tags=["zhuozheng", "lotus"]),
            make_photo("p6", theme_tags=["suzhou", "snack"]),
        ]
        tf = build_theme_feature(ps)
        assert tf.band == "medium", f"got {tf.band}"
        assert tf.rule_fired == "TH.0"
        assert tf.primary_coverage == 1.0
        # 真 Qwen 应聚成 >= 2 簇 (mock 时跳过校验)
        # (Qwen 实测: [['work', 'business'], ['zhuozheng', 'suzhou']])


class TestTH1Strong:
    def test_all_same_theme_tags(self):
        ps = [
            make_photo(f"p{i}", theme_tags=["lakeside", "sunset"])
            for i in range(5)
        ]
        tf = build_theme_feature(ps)
        assert tf.band == "strong"
        assert tf.rule_fired == "TH.1"
        assert tf.shape == ThemeShape.FULL_COVERAGE_THEMED
        assert tf.primary_coverage == 1.0
        assert tf.secondary_coverage is None  # 不触发次

    def test_semantic_synonym_in_mock_table(self):
        """真 Qwen 同义识别 (lakeside / lake / lakefront 同英文系列, 跨语言识别较弱).

        ADR-0020 v0.7 改: 真 Qwen 跨语言 (英中) 同义相似度只有 0.49-0.62,
        不达 merge_similarity=0.75. 用同语言变体 + cluster threshold 校准.
        """
        ps = [
            make_photo("p1", theme_tags=["lakeside"]),
            make_photo("p2", theme_tags=["lake"]),
            make_photo("p3", theme_tags=["lakefront"]),
            make_photo("p4", theme_tags=["lakeshore"]),
            make_photo("p5", theme_tags=["waterside"]),
        ]
        tf = build_theme_feature(ps)
        # 真 Qwen 把 5 个英文 lake 同义词合并入同一 cluster, hit_count=5
        assert tf.band == "strong"
        assert tf.primary_coverage == 1.0


# ─── TH.2 + 次字段升降档 ───────────────────────────────────


class TestTH2SecondaryBoost:
    """TH.2: primary_coverage=0.8 + secondary 强 → 升 strong."""
    def test_main_subjects_save(self):
        ps = [
            make_photo("p1", theme_tags=["lakeside"], main_subjects=["湖面"]),
            make_photo("p2", theme_tags=["lakeside"], main_subjects=["湖面"]),
            make_photo("p3", theme_tags=["lakeside"], main_subjects=["湖面"]),
            make_photo("p4", theme_tags=["lakeside"], main_subjects=["湖面"]),
            make_photo("p5", theme_tags=["urban"], main_subjects=["湖面"]),
        ]
        tf = build_theme_feature(ps)
        # primary_coverage = 0.8 (4/5) → TH.2
        # secondary_coverage = 1.0 ≥ 2/3 → boost
        assert tf.band == "strong"
        assert "TH.2" in tf.rule_fired
        assert "+secondary_boost" in tf.rule_fired
        assert tf.secondary_action == "boost"
        assert tf.primary_coverage == pytest.approx(0.8)


class TestTH2SecondaryDemote:
    """TH.2: primary_coverage=0.8 + secondary 散 → 降 weak."""
    def test_main_subjects_all_different(self):
        # ADR-0020 v0.7: a/b/c/d/e 单字符在真 Qwen 中也高度相似, 用真实多样词
        ps = [
            make_photo("p1", theme_tags=["lakeside"], main_subjects=["apple"]),
            make_photo("p2", theme_tags=["lakeside"], main_subjects=["telescope"]),
            make_photo("p3", theme_tags=["lakeside"], main_subjects=["fireworks"]),
            make_photo("p4", theme_tags=["lakeside"], main_subjects=["violin"]),
            make_photo("p5", theme_tags=["urban"], main_subjects=["mushroom"]),
        ]
        tf = build_theme_feature(ps)
        # primary_coverage=0.8 → TH.2
        # secondary 5 个独立 cluster, 各 hit_count=1 < min_hit_count=2 → 无次主题簇
        # secondary_coverage = 0 < 1/3 → demote
        assert tf.band == "weak"
        assert "TH.2+secondary_demote" in tf.rule_fired
        assert tf.secondary_action == "demote"


class TestTH3MediumNoChange:
    """ADR-0024 后语义变化: Top-K 让 3:2 lake/urban 同时入选 → cov=1.0 TH.0 medium.
    subject [湖面×3 + 楼×2] 同 Top-K → cov=1.0 strong → MAX 取 strong dominant=subject.
    """
    def test_secondary_middle(self):
        ps = [
            make_photo("p1", theme_tags=["lakeside"], main_subjects=["湖面"]),
            make_photo("p2", theme_tags=["lakeside"], main_subjects=["湖面"]),
            make_photo("p3", theme_tags=["lakeside"], main_subjects=["湖面"]),
            make_photo("p4", theme_tags=["urban"], main_subjects=["楼"]),
            make_photo("p5", theme_tags=["urban"], main_subjects=["楼"]),
        ]
        tf = build_theme_feature(ps)
        # ADR-0024 + ADR-0023: subject 全覆盖 + 多簇 → subject_band=strong → MAX 取 strong
        assert tf.theme_band == "medium"  # TH.0 多并列
        assert tf.subject_band == "strong"
        assert tf.band == "strong"
        assert tf.dominant_field == "subject"
        assert tf.primary_coverage == pytest.approx(1.0)


# ─── TH.4 weak (主字段散, 不看次) ──────────────────────────


class TestTH4Weak:
    def test_all_different_tags(self):
        # ADR-0020 v0.7: 用真实多样化 tag, 避免真 Qwen 把 "tag_N" 模式聚成一簇
        diverse_tags = ["fireworks", "anchor", "telescope", "violin", "mushroom"]
        ps = [
            make_photo(f"p{i}", theme_tags=[diverse_tags[i]])
            for i in range(5)
        ]
        tf = build_theme_feature(ps)
        # 5 个独立 cluster 各 hit_count=1 < 2 → no theme_clusters → primary_coverage=0
        assert tf.band == "weak"
        assert tf.rule_fired == "TH.4"
        assert tf.shape == ThemeShape.NO_DOMINANT_THEME
        assert tf.secondary_coverage is None  # 不触发

    def test_two_photos_binary_choice(self):
        ps = [
            make_photo("p1", theme_tags=["lakeside"]),
            make_photo("p2", theme_tags=["urban"]),
        ]
        tf = build_theme_feature(ps)
        # 2 张二选一, 各 cluster hit_count=1 < 2 → no theme_clusters → TH.4
        assert tf.band == "weak"
        assert tf.rule_fired == "TH.4"


# ─── TH.5 none ─────────────────────────────────────────────


class TestTH5None:
    def test_empty(self):
        tf = build_theme_feature([])
        assert tf.band == "none"
        assert tf.rule_fired == "TH.5"
        assert tf.shape == ThemeShape.NO_THEME_SIGNAL

    def test_single_photo(self):
        ps = [make_photo("p1", theme_tags=["lakeside"])]
        tf = build_theme_feature(ps)
        # N=1 < 2 → none
        assert tf.band == "none"

    def test_all_empty_tags(self):
        ps = [make_photo(f"p{i}", theme_tags=[]) for i in range(5)]
        tf = build_theme_feature(ps)
        # N_valid = 0 ≤ n_valid_min=1 → none
        assert tf.band == "none"
        assert tf.rule_fired == "TH.5"


# ─── ADR-0023 · MAX-OR + 泛词 stoplist ─────────────────────


class TestSubjectMaxOrA6:
    """A6 牡丹 30 天 case: theme weak (词散), subject strong → final strong by subject.

    参考: decisions/0023-theme-subject-max-or.md §一 + docs/19 J 行
    """
    def test_main_subjects_rescue_when_theme_weak(self):
        """主题词完全散 (5 张各异不关联), 但 subject 一致 → MAX 取 subject strong.

        模拟 A6 类型场景: 主题词颗粒度不一, subject 稳定.
        """
        diverse_themes = ["fireworks", "anchor", "telescope", "violin", "mushroom"]
        ps = [
            make_photo(f"p{i}", theme_tags=[diverse_themes[i]], main_subjects=["flower", "petal"])
            for i in range(5)
        ]
        tf = build_theme_feature(ps)
        # theme 单跑: 5 散簇各 hit=1 < min_hit_count=2 → no theme_clusters → TH.4 weak
        assert tf.theme_band == "weak", f"theme_band={tf.theme_band}"
        # subject 单跑: [flower, petal] × 5 → cov=1.0 → TH.1 strong
        assert tf.subject_band == "strong", f"subject_band={tf.subject_band}"
        # MAX → strong, dominant=subject, rule_fired 加 .subject 后缀
        assert tf.band == "strong"
        assert tf.dominant_field == "subject"
        assert tf.rule_fired == "TH.1.subject"
        assert not tf.subject_stoplist_capped


class TestSubjectStopwordCap:
    """K case: theme weak + subject 全泛词 → cap medium, 不假阳 strong."""

    def test_subject_person_capped(self):
        # theme 全散 (TH.4 weak), subject=[person × 5] (cov=1.0 strong, 但被 cap medium)
        diverse_themes = ["fireworks", "anchor", "telescope", "violin", "mushroom"]
        ps = [
            make_photo(f"p{i}", theme_tags=[diverse_themes[i]], main_subjects=["person"])
            for i in range(5)
        ]
        tf = build_theme_feature(ps)
        assert tf.theme_band == "weak"
        # subject 主簇命中 stoplist → cap medium
        assert tf.subject_stoplist_capped
        assert "person" in tf.subject_stoplist_hits
        assert tf.subject_band == "medium"
        # MAX(weak, medium) = medium, dominant=subject
        assert tf.band == "medium"
        assert tf.dominant_field == "subject"
        assert "+stopword_cap" in tf.rule_fired

    def test_phase3_boost_capped_by_stoplist(self):
        """主弱+次救老逻辑 (TH.2+secondary_boost) 不能被泛词触发."""
        # theme=4 lake + 1 urban (TH.2 medium), main_subjects=[person × 5]
        # 老 ADR-0013: secondary_coverage=1.0 → boost strong (假阳)
        # ADR-0023 Phase 3 cap: secondary 全泛词 → 撤销 boost, theme_band=medium
        ps = [
            make_photo("p1", theme_tags=["lakeside"], main_subjects=["person"]),
            make_photo("p2", theme_tags=["lakeside"], main_subjects=["person"]),
            make_photo("p3", theme_tags=["lakeside"], main_subjects=["person"]),
            make_photo("p4", theme_tags=["lakeside"], main_subjects=["person"]),
            make_photo("p5", theme_tags=["urban"],    main_subjects=["person"]),
        ]
        tf = build_theme_feature(ps)
        # theme primary_coverage=0.8 → TH.2, 老逻辑 secondary→boost strong, 被 cap 退 medium
        assert tf.theme_band == "medium", f"theme_band={tf.theme_band}"
        assert "stopword_phase3_cap" in tf.rule_fired or tf.dominant_field == "subject"
        # final: theme medium vs subject medium (capped), MAX = medium
        assert tf.band == "medium"


class TestThemeWinsWhenStronger:
    """theme 单簇全员一致 (TH.1) 时, theme 赢, dominant=theme, 无 .subject 后缀."""

    def test_theme_dominates(self):
        ps = [
            make_photo(f"p{i}", theme_tags=["lakeside", "sunset"], main_subjects=["water"])
            for i in range(5)
        ]
        tf = build_theme_feature(ps)
        assert tf.band == "strong"
        assert tf.dominant_field == "theme"
        assert tf.rule_fired == "TH.1"
        assert ".subject" not in tf.rule_fired
