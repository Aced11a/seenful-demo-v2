"""User home_city 推断 + 4 档判定 (ADR-0016).

参考:
  docs/22_location_geocoder.md
  decisions/0016-location-geocoder-4tier.md
  decisions/0010-path-b-location-dbch-pca-shape.md (path B 已删 LocationContext, 不影响)

v0.1 demo:
  · infer_user_home_city: 从 config 读硬编码 admin dict (跟 ADR-0005 stub 同思路, 但字段升级)
  · get_context_for_photo: 4 档判定 (市内/省内/国内/国外) 用 Geocoder 返回的 admin dict
  · get_album_context: 一组照片取最严档

v0.2 OQ-010 §10c 真接入: 用户最近 30 天 GPS 频次 → Geocoder → city 频次最高 = home_city
"""
from __future__ import annotations

from src.contracts import Context, HomeCityRegion
from src.mini_album.geocoder import get_admin_cached, get_geocoder
from src.policy.config_loader import load_config


# ─── User home_city 推断 (v0.1 stub) ─────────────────────────


def infer_user_home_city(user_id: str) -> HomeCityRegion:
    """v0.1 demo stub: 从 config 读硬编码 admin dict.

    生产 (OQ-010 §10c, v0.2): 查用户最近 30 天 GPS 频次 → Geocoder → city 频次最高 = home_city.
    """
    cfg = load_config("place_anchor.yaml")
    stubs = cfg.get("demo_home_city_stub", {})
    s = stubs.get(user_id)
    if s is not None:
        return HomeCityRegion(
            user_id=user_id,
            country=s.get("country", "中国"),
            province=s.get("province"),
            city=s.get("city"),
            district=s.get("district"),
            center=tuple(s["center"]) if s.get("center") else None,  # type: ignore[arg-type]
            radius_km=s.get("radius_km"),
            inferred_source="stub",
        )
    # fallback: 默认杭州 (Seenful 早期用户场景)
    return HomeCityRegion(
        user_id=user_id,
        country="中国",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        center=(30.26, 120.13),
        radius_km=30.0,
        inferred_source="stub",
    )


# ─── 4 档判定 (ADR-0016 核心) ────────────────────────────────


def get_context_for_photo(
    photo_gps: tuple[float, float] | None,
    user_home: HomeCityRegion,
) -> Context:
    """每张照片独立判定 4 档 (ADR-0016).

    流程:
      1. photo_gps is None → 兜底"市内" (跟 OQ-005 保守一致)
      2. Geocoder 查 photo_admin (provider 走 yaml)
      3. photo_admin is None (API 失败 / 海外失败) → 兜底"国外" if user 在国内, 否则"市内"
      4. country/province/city 三级比较 → 4 档

    Args:
      photo_gps: (lat, lng) - 注意 lat 在前 lng 在后 (Seenful 内部约定)
      user_home: 用户家 admin dict
    """
    if photo_gps is None:
        return "市内"  # OQ-005 保守

    # photo_gps 是 (lat, lng); Geocoder 接受 (lng, lat) GPS 顺序
    lat, lng = photo_gps
    geocoder_cfg = load_config("geocoder.yaml")["geocoder"]
    geocoder = get_geocoder(geocoder_cfg)
    photo_admin = get_admin_cached(geocoder, lng, lat)

    if photo_admin is None:
        # Geocoder 失败 / 海外 GPS: 兜底为"国外" (跟 country 不同触发条件一致)
        return "国外"

    # 4 档判定
    user_country = user_home.country
    user_province = user_home.province
    user_city = user_home.city

    photo_country = photo_admin.get("country")
    photo_province = photo_admin.get("province")
    photo_city = photo_admin.get("city")

    if photo_country != user_country:
        return "国外"
    if photo_province != user_province:
        return "国内"
    if photo_city != user_city:
        return "省内"
    return "市内"


def get_album_context(
    photo_gps_list: list[tuple[float, float] | None],
    user_home: HomeCityRegion,
) -> Context:
    """对一组照片 (一本相册) 判 context, 取最严 (最远) 档.

    严格度排序: 国外 > 国内 > 省内 > 市内
    (国外严格度最高 = 用户离家最远 = 阈值最松).
    """
    severity = {"市内": 0, "省内": 1, "国内": 2, "国外": 3}
    contexts: list[Context] = [
        get_context_for_photo(p, user_home)
        for p in photo_gps_list if p is not None
    ]
    if not contexts:
        return "市内"
    # 取最严 (severity 最大 = 最远 = 最松距离阈值)
    return max(contexts, key=lambda c: severity[c])
