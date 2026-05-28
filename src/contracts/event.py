"""Event 三级分层契约 (路径 A event 维度).

参考:
  decisions/0009-event-aggregation.md
  docs/15_event_aggregation.md
  docs/02_data_contracts.md (字段定义)
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EventAggregation(BaseModel):
    """小集级 event 三级分层 (ADR-0009).

    由 src.mini_album.event_aggregation.aggregate_event 产出.
    把单值 event 扩展为分布 + 三级分层 (primary/secondary/tertiary),
    使 1 张新照片 vs 小集匹配可输出 4 档而非 2 档.

    参考: docs/15_event_aggregation.md §二.
    """
    primary: str | None = Field(
        default=None,
        description="主导 event (占比 ≥ primary_threshold, 唯一); 无主导时为 None",
    )
    secondary: list[str] = Field(
        default_factory=list,
        description="次主导 event 列表 (占比 ≥ secondary_threshold, 不含 primary)",
    )
    tertiary: list[str] = Field(
        default_factory=list,
        description="历史稀少 event 列表 (count ≥ tertiary_min_count, 不达 secondary)",
    )
    distribution: dict[str, int] = Field(
        default_factory=dict,
        description="{event: count} 完整分布 (诊断用)",
    )
    total_events: int = Field(
        default=0,
        ge=0,
        description="剔除 unknown 后的总照片数",
    )


class EventMatchResult(BaseModel):
    """新照片 event vs 老相册 event_agg 的匹配结果 (ADR-0009).

    由 src.mini_album.event_aggregation.match_event 产出.
    band 字段是真值表唯一消费的输出, 与 location MatchResult / theme ThemeMatchResult 模式对齐.

    参考: docs/15_event_aggregation.md §四.
    """
    band: Literal["strong", "medium", "weak", "none"]
    matched_tier: Literal["primary", "secondary", "tertiary", "none"] | None = Field(
        default=None,
        description="命中的层级; none 表示完全不沾",
    )
    diagnostics: dict[str, Any] = Field(
        default_factory=dict,
        description="诊断字段: new_event / primary / secondary / tertiary",
    )
    reason: str = Field(
        default="",
        description='早返时填: "unknown_event" / "empty_aggregation"; 否则空',
    )
