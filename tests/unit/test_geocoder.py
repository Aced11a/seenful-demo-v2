"""Geocoder 单测 (ADR-0016).

覆盖:
  · MockGeocoder 固定 dict 映射
  · AmapGeocoder 接口契约 (用 monkeypatch mock HTTP, 不打真 API)
  · get_geocoder factory
  · 缓存 (gps_to_cache_key + get_admin_cached + None 也缓存)
  · 异常路径
"""
from __future__ import annotations

import os

import pytest

from src.mini_album.geocoder import (
    AmapGeocoder,
    MockGeocoder,
    clear_cache,
    get_admin_cached,
    get_geocoder,
    gps_to_cache_key,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


# ─── gps_to_cache_key ───────────────────────────────────────


class TestCacheKey:
    def test_quantize_4_decimals(self):
        assert gps_to_cache_key(120.13, 30.26) == "120.1300,30.2600"
        assert gps_to_cache_key(120.13456, 30.26789) == "120.1346,30.2679"

    def test_same_quantized_bucket(self):
        # 10m 范围内的两点应该同 key (4 位小数)
        # 30.2600 vs 30.2604 (差 ~ 44m at lat 30) → key 不同
        # 30.2600 vs 30.26009 → 都 round 到 30.2601 (差<10m) → 同 key
        a = gps_to_cache_key(120.1300, 30.2600)
        b = gps_to_cache_key(120.13002, 30.26003)
        assert a == b


# ─── MockGeocoder ───────────────────────────────────────────


class TestMockGeocoder:
    def test_known_hangzhou_xihu(self):
        mg = MockGeocoder()
        admin = mg.get_admin(120.13, 30.26)
        assert admin == {
            "country": "中国", "province": "浙江省",
            "city": "杭州市", "district": "西湖区",
        }

    def test_known_shanghai(self):
        mg = MockGeocoder()
        admin = mg.get_admin(121.49, 31.24)
        assert admin["province"] == "上海市"
        assert admin["city"] == "上海市"

    def test_unknown_returns_none(self):
        mg = MockGeocoder()
        # 北京坐标但不在 fixture 中
        assert mg.get_admin(0.0, 0.0) is None


# ─── get_geocoder factory ───────────────────────────────────


class TestGetGeocoder:
    def test_mock_provider(self):
        g = get_geocoder({"provider": "mock"})
        assert isinstance(g, MockGeocoder)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown geocoder provider"):
            get_geocoder({"provider": "google"})

    def test_amap_without_env_var_raises(self, monkeypatch):
        monkeypatch.delenv("AMAP_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="缺环境变量"):
            get_geocoder({
                "provider": "amap",
                "amap": {
                    "api_key_env": "AMAP_API_KEY",
                    "endpoint": "https://...",
                    "timeout_seconds": 5,
                },
            })


# ─── 缓存 (get_admin_cached) ────────────────────────────────


class TestCached:
    def test_first_call_hits_geocoder(self):
        mg = MockGeocoder()
        result = get_admin_cached(mg, 120.13, 30.26)
        assert result["city"] == "杭州市"

    def test_second_call_hits_cache(self, monkeypatch):
        mg = MockGeocoder()
        call_count = [0]
        original = mg.get_admin

        def counter(lng, lat):
            call_count[0] += 1
            return original(lng, lat)

        monkeypatch.setattr(mg, "get_admin", counter)

        get_admin_cached(mg, 120.13, 30.26)
        get_admin_cached(mg, 120.13, 30.26)
        get_admin_cached(mg, 120.13, 30.26)
        # 同 GPS 多次查只调 1 次 (后续走缓存)
        assert call_count[0] == 1

    def test_none_also_cached(self, monkeypatch):
        mg = MockGeocoder()
        call_count = [0]

        def always_none(lng, lat):
            call_count[0] += 1
            return None

        monkeypatch.setattr(mg, "get_admin", always_none)

        get_admin_cached(mg, 99.0, 99.0)
        get_admin_cached(mg, 99.0, 99.0)
        # 失败结果也缓存, 不重复打 quota
        assert call_count[0] == 1


# ─── AmapGeocoder (用 monkeypatch mock HTTP, 不打真 API) ────


class TestAmapGeocoder:
    def test_init_requires_env_var(self, monkeypatch):
        monkeypatch.delenv("AMAP_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="缺环境变量 AMAP_API_KEY"):
            AmapGeocoder({
                "api_key_env": "AMAP_API_KEY",
                "endpoint": "https://restapi.amap.com/v3/geocode/regeo",
                "timeout_seconds": 5,
            })

    def test_mock_http_success(self, monkeypatch):
        monkeypatch.setenv("AMAP_API_KEY", "test_key")
        ag = AmapGeocoder({
            "api_key_env": "AMAP_API_KEY",
            "endpoint": "https://restapi.amap.com/v3/geocode/regeo",
            "timeout_seconds": 5,
        })

        # mock urlopen 返回固定 JSON
        import io
        import json

        fake_response = {
            "status": "1",
            "regeocode": {
                "addressComponent": {
                    "country": "中国",
                    "province": "浙江省",
                    "city": "杭州市",
                    "district": "西湖区",
                }
            },
        }

        class FakeResp:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps(fake_response).encode("utf-8")

        import src.mini_album.geocoder as geo_mod
        monkeypatch.setattr(geo_mod, "urlopen", lambda req, timeout: FakeResp())

        admin = ag.get_admin(120.13, 30.26)
        assert admin == {
            "country": "中国", "province": "浙江省",
            "city": "杭州市", "district": "西湖区",
        }

    def test_mock_http_failure_returns_none(self, monkeypatch):
        monkeypatch.setenv("AMAP_API_KEY", "test_key")
        ag = AmapGeocoder({
            "api_key_env": "AMAP_API_KEY",
            "endpoint": "https://restapi.amap.com/v3/geocode/regeo",
            "timeout_seconds": 5,
        })

        import src.mini_album.geocoder as geo_mod

        def raise_error(req, timeout):
            raise Exception("network error")

        monkeypatch.setattr(geo_mod, "urlopen", raise_error)

        admin = ag.get_admin(120.13, 30.26)
        assert admin is None

    def test_mock_http_amap_status_0(self, monkeypatch):
        """高德 API 返回 status='0' (失败) 时返回 None."""
        monkeypatch.setenv("AMAP_API_KEY", "test_key")
        ag = AmapGeocoder({
            "api_key_env": "AMAP_API_KEY",
            "endpoint": "https://restapi.amap.com/v3/geocode/regeo",
            "timeout_seconds": 5,
        })

        import io
        import json

        class FakeResp:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"status": "0", "info": "INVALID_PARAMS"}).encode("utf-8")

        import src.mini_album.geocoder as geo_mod
        monkeypatch.setattr(geo_mod, "urlopen", lambda req, timeout: FakeResp())

        assert ag.get_admin(120.13, 30.26) is None
