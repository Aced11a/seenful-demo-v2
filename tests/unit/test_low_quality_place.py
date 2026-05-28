"""低质量地点判定 (ADR-0006) 单测.

覆盖:
  · pass_frequency_check (新用户保护 / 历史不足 / 不同日子门槛)
  · compute_user_density_baseline (样本不足 → None / 25 分位)
  · signal_l1_density (双低占比)
  · is_low_quality_plan_a 主入口
  · is_low_quality_place 分发 (no_user_context / plan_a / disabled)
  · spec §七 七个 case 验证
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.contracts import (
    Cluster,
    L1Output,
    UserContext,
    UserDensityBaseline,
)
from src.contracts.l1_output import ImageFacts, PlaceSignals, SafetyFlags, SemanticFacts
from src.mini_album.low_quality_place import (
    compute_user_density_baseline,
    is_low_quality_place,
    is_low_quality_plan_a,
    pass_frequency_check,
    signal_l1_density,
)


# ═════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════

NOW = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)


def mk_l1(
    pid: str,
    captured: datetime | None = None,
    meaning_d: float = 0.5,
    aesthetic_d: float = 0.5,
) -> L1Output:
    return L1Output(
        photo_id=pid,
        user_id="user_demo",
        individual_title="t",
        individual_understanding="x" * 70,
        captured_at=captured or NOW,
        meaning_density=meaning_d,
        aesthetic_density=aesthetic_d,
    )


def mk_cluster(member_ids: list[str]) -> Cluster:
    return Cluster(
        cluster_id="c_test",
        member_photo_ids=member_ids,
        convex_hull=[(30.0, 120.0), (30.001, 120.001), (30.0, 120.001)],
        centroid=(30.0005, 120.0005),
        is_low_quality=False,
    )


def stub_cfg(plan_a_enabled: bool = True, plan_b_enabled: bool = False) -> dict:
    return {
        "frequency": {
            "radius_m": 500,
            "lookback_days": 30,
            "min_distinct_days": 5,
            "new_user_min_age_days": 30,
            "new_user_min_photos": 10,
        },
        "plan_a": {
            "enabled": plan_a_enabled,
            "baseline_percentile": 25,
            "min_samples_for_baseline": 25,
            "double_low_ratio": 0.5,
        },
        "plan_b": {"enabled": plan_b_enabled},
    }


# ═════════════════════════════════════════════════════════════════
# pass_frequency_check
# ═════════════════════════════════════════════════════════════════

class TestFrequencyCheck:
    def test_new_user_blocked(self):
        ctx = UserContext(
            user_id="u",
            account_age_days=10,   # < 30
            user_history=[mk_l1(f"p{i}") for i in range(50)],
        )
        passed, diag = pass_frequency_check(mk_cluster(["p0"]), ctx, stub_cfg(), now=NOW)
        assert not passed
        assert diag["reason"] == "new_user_protection"

    def test_user_history_too_small(self):
        ctx = UserContext(
            user_id="u", account_age_days=100,
            user_history=[mk_l1(f"p{i}") for i in range(5)],   # < 10
        )
        passed, diag = pass_frequency_check(mk_cluster(["p0"]), ctx, stub_cfg(), now=NOW)
        assert not passed
        assert diag["reason"] == "user_history_too_small"

    def test_distinct_days_below_threshold(self):
        # 4 个不同日子 < 5
        history = [
            mk_l1("p_in", captured=NOW - timedelta(days=d))
            for d in [1, 2, 3, 4]
        ]
        # 凑满 user_history 数量 (10+)
        history += [mk_l1(f"p_other_{i}") for i in range(10)]
        ctx = UserContext(user_id="u", account_age_days=100, user_history=history)
        passed, diag = pass_frequency_check(
            mk_cluster(["p_in"]), ctx, stub_cfg(), now=NOW,
        )
        assert not passed
        assert diag["reason"] == "frequency_failed"
        assert diag["distinct_days"] == 4   # 4 个不同日子, < 5 不达标

    def test_passes_with_5_distinct_days(self):
        # 5 张照片在 cluster 内, 各不同日子
        cluster_photos = [
            mk_l1(f"p_in_{d}", captured=NOW - timedelta(days=d))
            for d in [1, 2, 3, 4, 5]
        ]
        history = cluster_photos + [mk_l1(f"p_other_{i}") for i in range(10)]
        ctx = UserContext(user_id="u", account_age_days=100, user_history=history)
        passed, diag = pass_frequency_check(
            mk_cluster([p.photo_id for p in cluster_photos]),
            ctx, stub_cfg(), now=NOW,
        )
        assert passed
        assert diag["distinct_days"] == 5


# ═════════════════════════════════════════════════════════════════
# compute_user_density_baseline
# ═════════════════════════════════════════════════════════════════

class TestBaseline:
    def test_returns_none_when_samples_insufficient(self):
        history = [mk_l1(f"p{i}") for i in range(10)]   # < 25
        baseline = compute_user_density_baseline("u", history, stub_cfg(), now=NOW)
        assert baseline is None

    def test_computes_25_percentile(self):
        # 100 张照片, density 均匀 0.0 - 0.99
        history = [
            mk_l1(f"p{i}", meaning_d=i / 100, aesthetic_d=i / 100)
            for i in range(100)
        ]
        baseline = compute_user_density_baseline("u", history, stub_cfg(), now=NOW)
        assert baseline is not None
        # 25 分位应约 0.25
        assert 0.20 < baseline.meaning_threshold < 0.30
        assert 0.20 < baseline.aesthetic_threshold < 0.30
        assert baseline.sample_size == 100


# ═════════════════════════════════════════════════════════════════
# signal_l1_density
# ═════════════════════════════════════════════════════════════════

class TestSignalL1Density:
    def test_no_baseline_returns_false(self):
        cluster = mk_cluster(["p1"])
        l1_data = {"p1": mk_l1("p1")}
        passed, diag = signal_l1_density(cluster, l1_data, None, stub_cfg())
        assert not passed
        assert diag["reason"] == "baseline_missing"

    def test_above_threshold_marks_low_quality(self):
        # 4 张照片, 3 张双低 (75% ≥ 50%) → 低质量
        baseline = UserDensityBaseline(
            user_id="u", meaning_threshold=0.5, aesthetic_threshold=0.5,
            last_computed_at=NOW, sample_size=100,
        )
        l1_data = {
            "p1": mk_l1("p1", meaning_d=0.1, aesthetic_d=0.1),   # 双低
            "p2": mk_l1("p2", meaning_d=0.1, aesthetic_d=0.1),   # 双低
            "p3": mk_l1("p3", meaning_d=0.2, aesthetic_d=0.2),   # 双低
            "p4": mk_l1("p4", meaning_d=0.8, aesthetic_d=0.8),   # 不双低
        }
        cluster = mk_cluster(["p1", "p2", "p3", "p4"])
        passed, diag = signal_l1_density(cluster, l1_data, baseline, stub_cfg())
        assert passed
        assert diag["ratio"] == 0.75

    def test_below_threshold_not_low_quality(self):
        # 4 张里 1 张双低 (25% < 50%) → 非低质量
        baseline = UserDensityBaseline(
            user_id="u", meaning_threshold=0.5, aesthetic_threshold=0.5,
            last_computed_at=NOW, sample_size=100,
        )
        l1_data = {
            "p1": mk_l1("p1", meaning_d=0.1, aesthetic_d=0.1),
            "p2": mk_l1("p2", meaning_d=0.8, aesthetic_d=0.8),
            "p3": mk_l1("p3", meaning_d=0.8, aesthetic_d=0.8),
            "p4": mk_l1("p4", meaning_d=0.8, aesthetic_d=0.8),
        }
        cluster = mk_cluster(["p1", "p2", "p3", "p4"])
        passed, _ = signal_l1_density(cluster, l1_data, baseline, stub_cfg())
        assert not passed


# ═════════════════════════════════════════════════════════════════
# is_low_quality_place 主入口 (含 7 个 spec case)
# ═════════════════════════════════════════════════════════════════

class TestSpecCases:
    """spec §七 七个 case + 主分发."""

    def test_case6_new_user_returns_false(self):
        # Case 6: 新用户 (注册 < 30 天), 即使家也不判低质量
        ctx = UserContext(
            user_id="u", account_age_days=10,
            user_history=[mk_l1(f"p{i}") for i in range(50)],
        )
        cluster = mk_cluster(["p1"])
        result = is_low_quality_place(cluster, ctx, {}, stub_cfg(), now=NOW)
        assert result.is_low_quality is False
        assert result.signal_source == "frequency_failed"
        assert result.diagnostics["frequency"]["reason"] == "new_user_protection"

    def test_case5_moved_away_returns_false(self):
        # Case 5: 搬家后老家 30 天内 0 次拍摄 → 频率不过 → 非低质量
        cluster = mk_cluster(["p_old"])
        history = [
            mk_l1("p_old", captured=NOW - timedelta(days=60))   # 60 天前老照片
        ]
        history += [mk_l1(f"p_other_{i}") for i in range(40)]
        ctx = UserContext(user_id="u", account_age_days=100, user_history=history)
        result = is_low_quality_place(cluster, ctx, {}, stub_cfg(), now=NOW)
        assert result.is_low_quality is False
        assert result.signal_source == "frequency_failed"

    def test_case1_home_low_quality(self):
        # Case 1: 杭州家, 频率达标 + 双低占比 75% → 低质量
        cluster_photos = [
            mk_l1(f"home_d{d}", captured=NOW - timedelta(days=d),
                  meaning_d=0.1, aesthetic_d=0.1)
            for d in [1, 3, 5, 7, 9]   # 5 个不同日子
        ]
        cluster_photos.append(
            mk_l1("home_high", captured=NOW - timedelta(days=2),
                  meaning_d=0.8, aesthetic_d=0.8)   # 1 张高 density (调性)
        )
        # 凑用户历史: 25 张混合 density 用作 baseline
        history = cluster_photos + [
            mk_l1(f"hist_{i}", meaning_d=0.5 + i * 0.01, aesthetic_d=0.5 + i * 0.01)
            for i in range(30)
        ]
        ctx = UserContext(user_id="u", account_age_days=100, user_history=history)

        l1_data = {p.photo_id: p for p in cluster_photos}
        cluster = mk_cluster([p.photo_id for p in cluster_photos])

        result = is_low_quality_place(cluster, ctx, l1_data, stub_cfg(), now=NOW)
        assert result.is_low_quality is True
        assert result.signal_source == "plan_a"
        # 5/6 ≈ 83% 双低 ≥ 50%
        assert result.diagnostics["density"]["ratio"] >= 0.5

    def test_case2_favorite_park_not_low_quality(self):
        # Case 2: 常去公园, 频率达标 + 双低占比 20% (照片有调性) → 非低质量
        cluster_photos = [
            mk_l1(f"park_d{d}", captured=NOW - timedelta(days=d),
                  meaning_d=0.7, aesthetic_d=0.7)
            for d in [1, 3, 5, 7, 9]
        ]
        history = cluster_photos + [
            mk_l1(f"hist_{i}", meaning_d=0.5, aesthetic_d=0.5)
            for i in range(30)
        ]
        ctx = UserContext(user_id="u", account_age_days=100, user_history=history)
        l1_data = {p.photo_id: p for p in cluster_photos}
        cluster = mk_cluster([p.photo_id for p in cluster_photos])

        result = is_low_quality_place(cluster, ctx, l1_data, stub_cfg(), now=NOW)
        assert result.is_low_quality is False


class TestDispatch:
    def test_no_user_context_returns_false(self):
        cluster = mk_cluster(["p1"])
        result = is_low_quality_place(cluster, None, {}, stub_cfg())
        assert result.is_low_quality is False
        assert result.signal_source == "no_user_context"

    def test_disabled_returns_false(self):
        ctx = UserContext(user_id="u", account_age_days=100, user_history=[])
        cluster = mk_cluster(["p1"])
        cfg = stub_cfg(plan_a_enabled=False, plan_b_enabled=False)
        result = is_low_quality_place(cluster, ctx, {}, cfg)
        assert result.is_low_quality is False
        assert result.signal_source == "disabled"

    def test_plan_b_stub_raises(self):
        ctx = UserContext(user_id="u", account_age_days=100, user_history=[])
        cluster = mk_cluster(["p1"])
        cfg = stub_cfg(plan_a_enabled=False, plan_b_enabled=True)
        with pytest.raises(NotImplementedError):
            is_low_quality_place(cluster, ctx, {}, cfg)
