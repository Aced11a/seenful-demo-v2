"""Geocoder · GPS → 行政区 (ADR-0016).

参考:
  docs/22_location_geocoder.md
  decisions/0016-location-geocoder-4tier.md
  config/geocoder.yaml

提供:
  · Geocoder 协议 (MockGeocoder / AmapGeocoder 鸭子类型)
  · MockGeocoder       — 固定 dict 映射 (CI 测试用)
  · AmapGeocoder       — 高德 Reverse Geocoding API (v0.1 demo + 生产)
  · get_geocoder(cfg)  — factory
  · 进程内缓存 + GPS 量化 (~ 10m)

⚠ 默认 provider="mock" 安全 (无 AMAP_API_KEY 也跑).
⚠ Ace 2026-05-18 拍板: POI 高德 + 4 档 + 国内 + v0.1 直接接入.
"""
from __future__ import annotations

import json
import os
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ─── 缓存 (进程内 dict, demo 阶段不需 TTL) ────────────────────


_CACHE: dict[str, dict | None] = {}


def gps_to_cache_key(lng: float, lat: float) -> str:
    """GPS 量化 4 位小数 (~ 10m) 作 cache key."""
    return f"{lng:.4f},{lat:.4f}"


def clear_cache() -> None:
    """测试用: 清缓存."""
    _CACHE.clear()


# ─── Geocoder 协议 ────────────────────────────────────────────


class Geocoder(Protocol):
    """Geocoder 协议 (鸭子类型). 实现 MockGeocoder / AmapGeocoder."""

    def get_admin(self, lng: float, lat: float) -> dict | None:
        """GPS → admin dict.

        返回:
          {"country": str, "province": str|None, "city": str|None, "district": str|None}
          或 None (失败 / 海外 / GPS 异常)
        """
        ...


# ─── MockGeocoder (CI 测试用) ────────────────────────────────


class MockGeocoder:
    """v0.1 demo CI 测试用. 固定 dict 映射, 不打真 API.

    跟测试 fixtures 的 GPS 配套. 量化 4 位小数 (~ 10m).
    新增 fixture 时同步更新 _FIXTURE 映射.
    """

    _FIXTURE: dict[str, dict] = {
        # ─── 杭州市 (Seenful 测试主场) ──────────────────
        "120.1300,30.2600": {"country": "中国", "province": "浙江省",
                              "city": "杭州市", "district": "西湖区"},
        "120.4300,30.2300": {"country": "中国", "province": "浙江省",
                              "city": "杭州市", "district": "萧山区"},
        "119.7200,30.2300": {"country": "中国", "province": "浙江省",
                              "city": "杭州市", "district": "临安区"},
        # ─── 浙江省其他市 (跨市同省 = 省内) ─────────────
        "121.5500,29.8700": {"country": "中国", "province": "浙江省",
                              "city": "宁波市", "district": "鄞州区"},
        # ─── 跨省 (国内) ─────────────────────────────────
        "121.4900,31.2400": {"country": "中国", "province": "上海市",
                              "city": "上海市", "district": "黄浦区"},
        "120.7400,31.3000": {"country": "中国", "province": "江苏省",
                              "city": "苏州市", "district": "工业园区"},
        "116.3970,39.9160": {"country": "中国", "province": "北京市",
                              "city": "北京市", "district": "东城区"},
        "117.7000,39.0400": {"country": "中国", "province": "天津市",
                              "city": "天津市", "district": "滨海新区"},
        "114.0600,22.5400": {"country": "中国", "province": "广东省",
                              "city": "深圳市", "district": "福田区"},
        # ─── 国外 ────────────────────────────────────────
        # 高德 API 海外 GPS 返回 None, Mock 不打 API 这里返回 None 模拟
    }

    def get_admin(self, lng: float, lat: float) -> dict | None:
        return self._FIXTURE.get(gps_to_cache_key(lng, lat))


# ─── AmapGeocoder (高德 API, v0.1 demo + 生产) ────────────────


class AmapGeocoder:
    """高德 Reverse Geocoding API (ADR-0016).

    端点: https://restapi.amap.com/v3/geocode/regeo
    免费 quota: 30 万次/天 (个人开发者 key)
    QPS: 30 (demo 阶段不撞顶)

    申请 key: lbs.amap.com/dev/key/app
    """

    def __init__(self, cfg: dict):
        env_var = cfg["api_key_env"]
        self.api_key = os.environ.get(env_var)
        if not self.api_key:
            raise RuntimeError(
                f"AmapGeocoder: 缺环境变量 {env_var}. "
                f"申请 key: lbs.amap.com/dev/key/app, "
                f"然后 export {env_var}=<key>"
            )
        self.endpoint = cfg["endpoint"]
        self.timeout = float(cfg["timeout_seconds"])

    def get_admin(self, lng: float, lat: float) -> dict | None:
        try:
            params = {
                "key": self.api_key,
                "location": f"{lng:.6f},{lat:.6f}",
                "extensions": "base",     # 不返回 POI 列表, 更快
            }
            url = f"{self.endpoint}?{urlencode(params)}"
            req = Request(url, headers={"User-Agent": "seenful-l2-engine/0.1"})
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") != "1":
                return None
            ac = data.get("regeocode", {}).get("addressComponent", {})
            return {
                "country": str(ac.get("country") or "中国"),
                "province": str(ac["province"]) if ac.get("province") else None,
                "city": str(ac["city"]) if ac.get("city") else None,
                "district": str(ac["district"]) if ac.get("district") else None,
            }
        except Exception:
            # 任何异常 (网络/超时/解析) 都返回 None, 不阻断
            return None


# ─── factory ────────────────────────────────────────────────


def get_geocoder(cfg: dict) -> Geocoder:
    """按 config 选择 geocoder.

    cfg 是 geocoder 段 dict (已下钻一层).
    """
    provider = cfg.get("provider", "mock")
    if provider == "mock":
        return MockGeocoder()
    if provider == "amap":
        return AmapGeocoder(cfg["amap"])
    raise ValueError(
        f"Unknown geocoder provider: {provider!r}. "
        f"Allowed: mock / amap."
    )


# ─── 高层入口 (带缓存) ──────────────────────────────────────


def get_admin_cached(geocoder: Geocoder, lng: float, lat: float) -> dict | None:
    """GPS → admin dict, 带进程内字典缓存.

    None 也缓存 (避免重复打 quota 在失败 GPS 上).
    """
    key = gps_to_cache_key(lng, lat)
    if key not in _CACHE:
        _CACHE[key] = geocoder.get_admin(lng, lat)
    return _CACHE[key]
