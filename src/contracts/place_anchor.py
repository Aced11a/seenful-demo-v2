"""Place Anchor (DBCH) 算法契约.

参考:
  docs/10_mini_album_schema.md
  decisions/0005-place-anchor-dbch.md
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .features import BandLevel

Context = Literal["市内", "省内", "国内", "国外"]
MatchTargetType = Literal["cluster", "outlier"]


class Cluster(BaseModel):
    """DBSCAN 成簇的聚集区."""
    cluster_id: str
    member_photo_ids: list[str]
    convex_hull: list[tuple[float, float]] = Field(
        ...,
        description="凸包顶点 [(lat, lng), ...], 闭合环 (首尾相同), 至少 3 个不同点",
    )
    centroid: tuple[float, float] = Field(
        ...,
        description="几何中位数 (lat, lng), 簇代表点",
    )
    is_low_quality: bool = Field(
        default=False,
        description=(
            "高频低质量地点标志 (ADR-0006). "
            "⚠ 实时计算, 不持久化 — `build_place_anchor` 默认 False; "
            "由 `match_against_cluster` 调 `is_low_quality_place` 实时填充. "
            "降档逻辑: 命中 → location band 降一档 (strong→medium→weak→none)."
        ),
    )


class OutlierPoint(BaseModel):
    """未成簇的孤立照片."""
    photo_id: str
    gps: tuple[float, float] = Field(
        ...,
        description="(lat, lng), 该照片的 EXIF GPS",
    )


class MatchResult(BaseModel):
    """match_new_photo 输出 — 直接给真值表消费.

    重要: band 是真值表唯一消费的字段;
    diagnostics 仅用于落痕排查, 不参与决策.
    """
    band: BandLevel
    matched_target_type: MatchTargetType | None = None
    matched_target_id: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(
        default="",
        description="早返原因, 如 'no_gps' / 'empty_anchor'",
    )


class HomeCityRegion(BaseModel):
    """用户常驻城市区域 (ADR-0016 升级: admin dict 4 档主信号).

    v0.1 → v0.2 范式变化:
      v0.1 (ADR-0005/0007): center + radius_km 距离判定
      v0.2 (ADR-0016):      country/province/city/district 行政区比较
    """
    user_id: str

    # ─── ADR-0016 admin 字段 (4 档判定主信号) ────────────
    country: str = Field(default="中国", description="国家名 (例: '中国' / '日本')")
    province: str | None = Field(
        default=None,
        description="省/直辖市/自治区名 (例: '浙江省' / '上海市')",
    )
    city: str | None = Field(default=None, description="市名 (例: '杭州市')")
    district: str | None = Field(
        default=None,
        description="区县名 (例: '西湖区'), 可选, 不参与 4 档判定",
    )

    # ─── 兜底字段 (Geocoder 失败时回退) ──────────────────
    center: tuple[float, float] | None = Field(
        default=None,
        description="(lat, lng) 城市中心. ADR-0016 后**不再是主判定**, 仅 Geocoder 异常时近似回退",
    )
    radius_km: float | None = Field(
        default=None,
        gt=0.0,
        description="常驻半径, 单位 km. 同上仅兜底用",
    )

    # ─── 数据源诊断 ──────────────────────────────────────
    inferred_source: str = Field(
        default="stub",
        description="'stub' (硬编码) / 'amap_frequency' (30 天 GPS 频次推断) / 'amap_direct'",
    )
