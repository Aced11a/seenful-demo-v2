"""Plan B = L2 1.0 = v1.3 工程规范 §3.2 抄本 (ADR-0018).

7 维度 score-based 算法, schema 适配:
  - scene_type 字段已删 → theme 子信号设 0
  - emotional neutral bug 保留 (5 张 neutral 字面一致 → 0.8 strong)

People 维度复用现 src/features/people.py::compute_people_score
(v0.1 简化版本身就是 v1.3 §3.2.7 实现).

参考: docs/24_feature_assembler_plan_ab.md
"""
from .location import compute_location_score_legacy
from .time import compute_time_score_legacy
from .theme import compute_theme_score_legacy
from .event import compute_event_score_legacy
from .anchor import compute_anchor_score_legacy
from .emotional import compute_emotional_score_legacy

__all__ = [
    "compute_location_score_legacy",
    "compute_time_score_legacy",
    "compute_theme_score_legacy",
    "compute_event_score_legacy",
    "compute_anchor_score_legacy",
    "compute_emotional_score_legacy",
]
