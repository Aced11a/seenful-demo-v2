"""兜底回扫候选 (路径 C · Step 1+2).

参考: docs/05_truth_table_backfill.md + docs/23_pipeline_cascade_backfill.md (ADR-0017)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from src.contracts import L1Output, PriorityRankingEntry
from src.features.location import haversine_km
from src.features.theme import jaccard_multi
from src.policy.config_loader import load_config


def filter_backfill_candidates(
    new_photo: L1Output,
    sedimented_pool: Iterable[L1Output],
    *,
    now: datetime | None = None,
    already_in_album_ids: set[str] | None = None,
    global_excluded_ids: set[str] | None = None,
    apply_max_candidates: bool = True,
) -> list[L1Output]:
    """Step 1 SQL 等价过滤 + Step 2 粗筛 (OR).

    HRC-PRE 前置规则:
      · uploaded_at >= now - lookback_days
      · sensitive_level < medium
      · photo_id NOT IN already_in_album_ids
      · photo_id NOT IN global_excluded_ids (backfill_excluded_global)
    粗筛规则 (任一命中):
      · GPS 距离 < gps_max_km
      · theme_tags Jaccard > theme_jaccard_min
      · event_hint 一致 (非 unknown)

    apply_max_candidates:
      · True (默认, 老入口 run_backfill_path): 截 coarse_filter.max_candidates=5
      · False (cascade_backfill_single, ADR-0017): 不截, 留给 rank_and_pick_top_n
    """
    if new_photo.sensitive_level in ("medium", "high"):
        return []

    cfg = load_config("truth_table_backfill.yaml")
    lookback_days = int(cfg["lookback_days"])
    coarse = cfg["coarse_filter"]
    gps_max_km = float(coarse["gps_max_km"])
    theme_min = float(coarse["theme_jaccard_min"])
    match_event = bool(coarse["match_event_hint"])
    max_candidates = int(coarse["max_candidates"])

    now = now or new_photo.captured_at or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)

    already_in_album_ids = already_in_album_ids or set()
    global_excluded_ids = global_excluded_ids or set()

    pool = list(sedimented_pool)
    eligible: list[L1Output] = []

    for p in pool:
        # 时间窗口 (使用 captured_at 兜底, demo 中 uploaded_at ≈ captured_at)
        captured = p.captured_at
        if captured is not None and captured < cutoff:
            continue
        if p.sensitive_level in ("medium", "high"):
            continue
        if p.photo_id in already_in_album_ids:
            continue
        if p.photo_id in global_excluded_ids:
            continue
        if p.photo_id == new_photo.photo_id:
            continue

        # 粗筛 OR
        if _passes_coarse(new_photo, p, gps_max_km, theme_min, match_event):
            eligible.append(p)
        if apply_max_candidates and len(eligible) >= max_candidates:
            break

    return eligible


def _passes_coarse(
    new: L1Output,
    candidate: L1Output,
    gps_max_km: float,
    theme_min: float,
    match_event: bool,
) -> bool:
    # GPS 距离
    if new.exif_location is not None and candidate.exif_location is not None:
        dist = haversine_km(new.exif_location, candidate.exif_location)
        if dist < gps_max_km:
            return True

    # theme_tags Jaccard
    if new.theme_tags and candidate.theme_tags:
        jac = jaccard_multi([set(new.theme_tags), set(candidate.theme_tags)])
        if jac > theme_min:
            return True

    # event_hint 一致
    if match_event:
        n_hint = new.semantic_facts.event_hint
        c_hint = candidate.semantic_facts.event_hint
        if n_hint == c_hint and n_hint != "unknown":
            return True

    return False


# ═════════════════════════════════════════════════════════════════
# ADR-0017: 维度强度总分排序选 top N
# ═════════════════════════════════════════════════════════════════

def rank_and_pick_top_n(
    new_photo: L1Output,
    candidates: list[L1Output],
    n: int,
    weights: dict[str, float],
) -> tuple[list[L1Output], list[PriorityRankingEntry]]:
    """对粗筛候选按维度强度总分排序, 取 top N.

    参考: docs/23_pipeline_cascade_backfill.md §二.

    score = (gps<1km ? weights.gps : 0)
          + (theme>0.5 ? weights.theme : 0)
          + (event 一致 ? weights.event : 0)

    weights 来自 config/truth_table_backfill.yaml::priority_weight,
    默认 gps=1.0, theme=1.0, event=0.5 (event_hint 封闭枚举降权).

    tie-breaker: 总分相同 → captured_at 倒序 (最近优先).

    返回: (top_n_candidates, all_ranking_entries)
    """
    cfg = load_config("truth_table_backfill.yaml")
    coarse = cfg["coarse_filter"]
    gps_max_km = float(coarse["gps_max_km"])
    theme_min = float(coarse["theme_jaccard_min"])

    scored: list[tuple[L1Output, float, bool, bool, bool]] = []

    for c in candidates:
        is_gps = False
        is_theme = False
        is_event = False

        # gps
        if new_photo.exif_location is not None and c.exif_location is not None:
            dist = haversine_km(new_photo.exif_location, c.exif_location)
            if dist < gps_max_km:
                is_gps = True

        # theme
        if new_photo.theme_tags and c.theme_tags:
            jac = jaccard_multi([set(new_photo.theme_tags), set(c.theme_tags)])
            if jac > theme_min:
                is_theme = True

        # event
        n_hint = new_photo.semantic_facts.event_hint
        c_hint = c.semantic_facts.event_hint
        if n_hint == c_hint and n_hint != "unknown":
            is_event = True

        score = 0.0
        if is_gps:
            score += float(weights["gps"])
        if is_theme:
            score += float(weights["theme"])
        if is_event:
            score += float(weights["event"])

        scored.append((c, score, is_gps, is_theme, is_event))

    # 排序: 总分降序, tie-breaker captured_at 倒序
    def _sort_key(item: tuple[L1Output, float, bool, bool, bool]) -> tuple[float, float]:
        c, s, _, _, _ = item
        ts = c.captured_at.timestamp() if c.captured_at is not None else 0.0
        return (-s, -ts)

    scored.sort(key=_sort_key)

    selected_items = scored[:n]
    selected_ids = {c.photo_id for c, _, _, _, _ in selected_items}

    ranking = [
        PriorityRankingEntry(
            photo_id=c.photo_id,
            gps_within_1km=is_g,
            theme_jaccard_above_0_5=is_t,
            event_match=is_e,
            score=s,
            selected=(c.photo_id in selected_ids),
        )
        for c, s, is_g, is_t, is_e in scored
    ]

    return [c for c, _, _, _, _ in selected_items], ranking


def cap_sediment_pool(
    sedimented_pool: list[L1Output],
    max_size: int,
) -> list[L1Output]:
    """ADR-0017: 沉淀池按 captured_at 倒序截最近 N 张.

    PRD §3.10.10 风险 2: demo v0.1 截 50 张, 真实数据 200+ 才换激进粗筛.
    """
    return sorted(
        sedimented_pool,
        key=lambda p: p.captured_at.timestamp() if p.captured_at else 0.0,
        reverse=True,
    )[:max_size]
