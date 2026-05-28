"""ADR-0017: Cascade Backfill (单张 P · PRD §3.10 校准).

参考:
  docs/23_pipeline_cascade_backfill.md (设计文档)
  decisions/0017-pipeline-cascade-backfill.md (ADR)
  Pipeline_Cascade_Backfill_Spec.md v0.3 (原始 spec)

跟老入口 `pipeline.run_backfill_path` 差别:
  · 粗筛不截 5 张 (apply_max_candidates=False)
  · 加 rank_and_pick_top_n 选 top max_recall_photos (PRD §3.10.5 = 4)
  · sediment 池入口截最近 max_sediment_size 张 (PRD §3.10.10)
  · BackfillDecisionLog 含 priority_ranking 字段 (审计 + OQ-28f 调优)

一致部分:
  · apply_backfill_caps **完全沿用** (PRD §3.10.5 strong-only)
  · 主真值表查表 / LLM judge 复用 path B
"""
from __future__ import annotations

import uuid

from src.candidate_builder.backfill_scan import (
    cap_sediment_pool,
    filter_backfill_candidates,
    rank_and_pick_top_n,
)
from src.contracts import (
    BackfillCap,
    BackfillDecision,
    BackfillDecisionLog,
    L1Output,
)
from src.features.assemble import assemble_features
from src.llm.backfill_judge import get_backfill_judge
from src.policy.backfill_engine import apply_backfill_caps
from src.policy.bands import compute_bands
from src.policy.config_loader import load_config
from src.policy.truth_table import lookup as truth_table_lookup


def cascade_backfill_single(
    new_photo: L1Output,
    sediment_pool: list[L1Output],
    scenario: str | None = None,
    judge=None,
) -> BackfillDecisionLog:
    """单张 P 跑 PRD §3.10 校准的 cascade backfill.

    流程:
      Step 1 · 沉淀池规模上限 (PRD §3.10.10, max_sediment_size=50)
      Step 2 · OR 粗筛 (PRD §3.10.5, 不截 5)
      Step 3 · 维度强度总分排序选 top 4 (ADR-0017, event 权重 0.5)
      Step 4 · 现 apply_backfill_caps (PRD §3.10.5 strong-only)
      Step 5 · 组装 BackfillDecisionLog (含 priority_ranking)
    """
    decision_id = f"decb_{uuid.uuid4().hex[:8]}"
    judge = judge or get_backfill_judge()

    cfg = load_config("truth_table_backfill.yaml")
    max_sediment = int(cfg["candidate_pool"]["max_sediment_size"])
    max_recall = int(cfg["max_recall_photos"])
    weights = cfg["priority_weight"]

    # ─── Step 1 · 沉淀池规模上限 ───
    sediment_capped = cap_sediment_pool(sediment_pool, max_sediment)

    # ─── Step 2 · OR 粗筛 (不截 5) ───
    candidates_raw = filter_backfill_candidates(
        new_photo,
        sediment_capped,
        apply_max_candidates=False,
    )

    # ─── Step 3 · 维度强度总分排序选 top 4 ───
    candidates, ranking = rank_and_pick_top_n(
        new_photo,
        candidates_raw,
        n=max_recall,
        weights=weights,
    )

    # 早返: 召回 < 1 张直接 insufficient_candidates (没东西可调 caps)
    if not candidates:
        final = BackfillDecision(
            backfill_decision_id=f"bd_{uuid.uuid4().hex[:8]}",
            new_photo_id=new_photo.photo_id,
            decision_tier="insufficient_candidates",
            recalled_photo_ids=[],
            primary_signal="none",
            reason="no_coarse_candidates",
        )
        return BackfillDecisionLog(
            decision_id=decision_id,
            scenario=scenario,
            new_photo_id=new_photo.photo_id,
            coarse_filter_candidates=[p.photo_id for p in candidates_raw],
            priority_ranking=ranking,
            main_truth_table_match=None,
            llm_judgement=None,
            backfill_caps_applied=[
                BackfillCap(
                    rule="BACKFILL-CAP-03-recall_count",
                    passed=False,
                    detail="coarse filter returned 0",
                ),
            ],
            final_decision=final,
        )

    # ─── Step 4 · 复用主真值表 + LLM + apply_backfill_caps ───
    photos_for_l2 = [new_photo, *candidates]
    features = assemble_features(photos_for_l2)
    bands = compute_bands(features)
    tt = truth_table_lookup(bands)

    if tt.matched_pattern == "F1":
        llm = None
    else:
        llm = judge.judge(photos_for_l2, features, bands, tt)

    result = apply_backfill_caps(new_photo, candidates, tt, llm)
    result.decision.backfill_decision_id = f"bd_{uuid.uuid4().hex[:8]}"

    # ─── Step 5 · BackfillDecisionLog ───
    return BackfillDecisionLog(
        decision_id=decision_id,
        scenario=scenario,
        new_photo_id=new_photo.photo_id,
        coarse_filter_candidates=[p.photo_id for p in candidates_raw],
        priority_ranking=ranking,
        main_truth_table_match=tt,
        llm_judgement=llm,
        backfill_caps_applied=result.caps,
        final_decision=result.decision,
    )
