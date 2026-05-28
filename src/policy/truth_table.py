"""主真值表查询.

参考:
  docs/03_truth_table_main.md  (28 条规则)
  config/truth_table_main.yaml (配置驱动)
  docs/12_open_questions.md OQ-002 / OQ-004

实现:DSL 解释器,不在代码里硬编码任何规则.
"""
from __future__ import annotations

from typing import Any, cast

from src.contracts import Bands, TruthTableMatch
from src.contracts.decision import BoundsLevel
from src.contracts.features import BandLevel

from .config_loader import load_config

# 强度排序 (high → low) 用于 ge 比较
LEVEL_ORDER: dict[BandLevel, int] = {"strong": 3, "medium": 2, "weak": 1, "none": 0}
MAIN_SIGNALS = ("location", "theme", "event", "people")
AUX_SIGNALS = ("anchor", "emotional")


def _level_ge(level: BandLevel, threshold: BandLevel) -> bool:
    return LEVEL_ORDER[level] >= LEVEL_ORDER[threshold]


def _eval(when: str, bands: Bands) -> bool:
    """评估 DSL 表达式.

    支持的原语:
      eq(band, level)                  band == level
      any_main_ge(level)               存在主载体 >= level
      any_main_eq(level)               存在主载体 == level
      count_main_eq(level, op, N)      主载体中等于 level 的个数 op N
      count_aux_ge(level, op, N)       辅证中 >= level 的个数 op N
      other_mains_weak_or_none(focus)  除 focus 外所有主载体 ∈ {weak, none}
      true                             永真
    """
    if when.strip() == "true":
        return True

    namespace: dict[str, Any] = {
        # 字面量注入: 维度名 + 强度名
        **{name: name for name in MAIN_SIGNALS + AUX_SIGNALS + ("time",)},
        **{lvl: lvl for lvl in ("strong", "medium", "weak", "none")},
        # DSL 函数
        "eq": lambda b, lvl: _get_band(bands, b) == lvl,
        "any_main_ge": lambda lvl: any(
            _level_ge(_get_band(bands, m), lvl) for m in MAIN_SIGNALS
        ),
        "any_main_eq": lambda lvl: any(
            _get_band(bands, m) == lvl for m in MAIN_SIGNALS
        ),
        "count_main_eq": lambda lvl, op, n: _compare(
            sum(1 for m in MAIN_SIGNALS if _get_band(bands, m) == lvl), op, n,
        ),
        "count_aux_ge": lambda lvl, op, n: _compare(
            sum(1 for a in AUX_SIGNALS if _level_ge(_get_band(bands, a), lvl)),
            op, n,
        ),
        "other_mains_weak_or_none": lambda focus: all(
            _get_band(bands, m) in ("weak", "none")
            for m in MAIN_SIGNALS if m != focus
        ),
    }

    safe_globals = {"__builtins__": {}}
    return bool(eval(when, safe_globals, namespace))  # noqa: S307


def _get_band(bands: Bands, name: str) -> BandLevel:
    return cast(BandLevel, getattr(bands, name))


def _compare(lhs: int, op: str, rhs: int) -> bool:
    if op == ">=":
        return lhs >= rhs
    if op == ">":
        return lhs > rhs
    if op == "<=":
        return lhs <= rhs
    if op == "<":
        return lhs < rhs
    if op == "==":
        return lhs == rhs
    raise ValueError(f"unsupported op: {op}")


def lookup(bands: Bands) -> TruthTableMatch:
    """按 config/truth_table_main.yaml 的 priority_order 逐条匹配."""
    cfg = load_config("truth_table_main.yaml")
    order: list[str] = cfg["priority_order"]
    rules: dict[str, dict[str, Any]] = {r["id"]: r for r in cfg["rules"]}

    for rule_id in order:
        rule = rules[rule_id]
        if _eval(rule["when"], bands):
            bounds = rule["bounds"]
            return TruthTableMatch(
                matched_pattern=rule_id,
                type=rule["type"],
                bounds_min=cast(BoundsLevel, bounds[0]),
                bounds_max=cast(BoundsLevel, bounds[1]),
                bands_snapshot=bands,   # ★ 输入快照, 见 docs/02 §TruthTableMatch
            )

    # 理论上不可达 (F1 是兜底 when=true)
    raise RuntimeError("truth table did not match F1 fallback — config corrupted")
