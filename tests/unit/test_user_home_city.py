"""user_home_city 4 档判定 单测 (ADR-0016).

覆盖:
  · infer_user_home_city stub 默认返回 + 字段
  · get_context_for_photo 4 档 (市内/省内/国内/国外) + GPS None 兜底
  · get_album_context 取最严档
"""
from __future__ import annotations

import pytest

from src.contracts import HomeCityRegion
from src.mini_album.geocoder import clear_cache
from src.mini_album.user_home_city import (
    get_album_context,
    get_context_for_photo,
    infer_user_home_city,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


# ─── infer_user_home_city ───────────────────────────────────


class TestInferUserHomeCity:
    def test_user_demo_returns_hangzhou(self):
        home = infer_user_home_city("user_demo")
        assert home.country == "中国"
        assert home.province == "浙江省"
        assert home.city == "杭州市"
        assert home.inferred_source == "stub"

    def test_unknown_user_falls_back_to_hangzhou_default(self):
        home = infer_user_home_city("unknown_user_xxx")
        assert home.country == "中国"
        assert home.city == "杭州市"


# ─── get_context_for_photo 4 档 (ADR-0016 核心) ─────────────


class TestGetContextForPhoto:
    """4 档判定: 市内 / 省内 / 国内 / 国外."""

    @pytest.fixture
    def home(self):
        return infer_user_home_city("user_demo")  # 中国/浙江省/杭州市

    def test_xihu_same_city(self, home):
        """杭州西湖 → 市内 (跟 home_city 同)."""
        # photo_gps = (lat, lng)
        assert get_context_for_photo((30.26, 120.13), home) == "市内"

    def test_xiaoshan_same_city_fix_old_radius(self, home):
        """萧山机场 → 市内 (修老 30km 半径漏判 cross_province)."""
        assert get_context_for_photo((30.23, 120.43), home) == "市内"

    def test_ningbo_same_province(self, home):
        """宁波 → 省内 (跨市同省)."""
        assert get_context_for_photo((29.87, 121.55), home) == "省内"

    def test_shanghai_cross_province_fix_old_distance(self, home):
        """上海 → 国内 (修老 same_province 距离 168km<500km 判同省错)."""
        assert get_context_for_photo((31.24, 121.49), home) == "国内"

    def test_beijing_cross_province(self, home):
        """北京 → 国内."""
        assert get_context_for_photo((39.916, 116.397), home) == "国内"

    def test_suzhou_cross_province_fix_old_distance(self, home):
        """苏州 → 国内 (修老 same_province 距离 180km<500km 判同省错)."""
        assert get_context_for_photo((31.30, 120.74), home) == "国内"

    def test_no_gps_falls_back_to_shi_nei(self, home):
        """photo_gps=None → 兜底"市内" (跟 OQ-005 保守)."""
        assert get_context_for_photo(None, home) == "市内"

    def test_unknown_gps_falls_back_to_guo_wai(self, home):
        """GPS 不在 MockGeocoder fixture → admin=None → 兜底"国外"."""
        # 0,0 不在 MockGeocoder _FIXTURE 里
        assert get_context_for_photo((0.0, 0.0), home) == "国外"


# ─── get_album_context 取最严档 ─────────────────────────────


class TestGetAlbumContext:
    """一组照片 → 取最远档 (国外 > 国内 > 省内 > 市内)."""

    @pytest.fixture
    def home(self):
        return infer_user_home_city("user_demo")

    def test_all_xihu_returns_shi_nei(self, home):
        ctx = get_album_context(
            [(30.26, 120.13), (30.26, 120.13)],
            home,
        )
        assert ctx == "市内"

    def test_xihu_plus_shanghai_returns_guo_nei(self, home):
        """杭州西湖 + 上海 (跨省) → 取最远 = 国内."""
        ctx = get_album_context(
            [(30.26, 120.13), (31.24, 121.49)],
            home,
        )
        assert ctx == "国内"

    def test_xihu_plus_ningbo_returns_sheng_nei(self, home):
        """杭州 + 宁波 (跨市同省) → 取最远 = 省内."""
        ctx = get_album_context(
            [(30.26, 120.13), (29.87, 121.55)],
            home,
        )
        assert ctx == "省内"

    def test_empty_returns_shi_nei(self, home):
        """空相册 → 兜底"市内"."""
        assert get_album_context([], home) == "市内"

    def test_all_none_returns_shi_nei(self, home):
        """全无 GPS → 兜底"市内"."""
        assert get_album_context([None, None, None], home) == "市内"
