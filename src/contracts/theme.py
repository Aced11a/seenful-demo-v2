"""Theme 语义簇契约 (路径 A theme 维度).

参考:
  decisions/0008-theme-semantic-clustering.md
  docs/14_theme_aggregation.md
  docs/02_data_contracts.md (字段定义)
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SemanticCluster(BaseModel):
    """Theme 语义簇 (ADR-0008).

    由 src.mini_album.theme_aggregation.aggregate_theme_clusters 产出.
    一组同义 tag 合并为一个簇, 簇内频次累加.

    参考: docs/14_theme_aggregation.md §二.
    """
    representative: str = Field(
        ...,
        description="簇代表 = 簇内频次最高的字面 tag",
    )
    members: dict[str, int] = Field(
        ...,
        description="{字面: 该字面频次}, sum(values()) == frequency",
    )
    frequency: int = Field(
        ...,
        ge=1,
        description="簇内总频次, = sum of members.values()",
    )
    centroid: list[float] = Field(
        ...,
        description="加权平均的归一化 embedding 向量 (按字面频次加权)",
    )


class ThemeMatchResult(BaseModel):
    """新照片 vs 老相册 theme_clusters 的匹配结果 (ADR-0008).

    由 src.mini_album.theme_aggregation.match_theme 产出.
    band 字段是真值表唯一消费的输出, 与 location MatchResult 模式对齐.

    参考: docs/14_theme_aggregation.md §四.
    """
    band: Literal["strong", "medium", "weak", "none"]
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="加权和原始分 = sum(per_cluster_max_sim * weight)",
    )
    per_cluster: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "每簇命中诊断, 字段: representative / frequency / weight / "
            "max_sim / matched_by / contribution"
        ),
    )
    reason: str = Field(
        default="",
        description='早返时填: "no_tags" / "empty_clusters"; 否则空',
    )
