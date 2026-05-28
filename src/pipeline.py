"""L2 路径 B + 路径 A orchestrator.

参考: docs/01_architecture.md, docs/04_truth_table_growth.md,
      docs/23_pipeline_cascade_backfill.md (ADR-0017)
"""
from __future__ import annotations

import uuid
from typing import Any

from src.arbitration.merge_results import arbitrate, arbitrate_cascade
from src.candidate_builder.backfill_scan import filter_backfill_candidates
from src.candidate_builder.growth_scan import filter_candidate_albums
from src.contracts import (
    ArbitrationResult,
    Association,
    AssociationDecision,
    BackfillDecision,
    BackfillDecisionLog,
    DecisionLog,
    GrowthDecision,
    GrowthDecisionLog,
    GrowthMergeRecord,
    L1Output,
    MiniAlbumFingerprint,
)
from src.features.assemble import assemble_features
from src.features.growth_features import compute_growth_features
from src.llm.backfill_judge import get_backfill_judge
from src.llm.growth_judge import MockGrowthJudge, get_growth_judge
from src.llm.judge import LLMJudge, get_judge
from src.policy.backfill_engine import apply_backfill_caps
from src.policy.bands import compute_bands
from src.policy.cascade_backfill import cascade_backfill_single
from src.policy.engine import run_post_truth_table, to_association
from src.policy.growth_engine import apply_post_hard_rules, resolve_multi_album_conflict
from src.policy.hard_rules import pre_filter
from src.policy.truth_table import lookup as truth_table_lookup
from src.policy.truth_table_growth import compute_growth_bands, lookup_growth


def run_l2_path_b(
    photos: list[L1Output],
    scenario: str | None = None,
    judge: LLMJudge | None = None,
) -> DecisionLog:
    """跑完整 L2 路径 B, 返回完整 DecisionLog."""
    decision_id = f"dec_{uuid.uuid4().hex[:8]}"
    judge = judge or get_judge()
    stages: dict[str, Any] = {}

    # ─── Step 1 · Candidate Builder (pre-filter) ───────────────
    pf = pre_filter(photos, min_photos=3)
    stages["step1_candidates"] = {
        "path_hint": "full_l2" if pf.passed else "suppress_early_return",
        "photo_count": len(photos),
        "early_return_reason": None if pf.passed else pf.reason,
    }

    if not pf.passed:
        return _build_suppressed_log(
            decision_id=decision_id,
            scenario=scenario,
            photos=photos,
            stages=stages,
            reason=pf.reason,
            decision_source="pre_filter_reject",
        )

    # ─── Step 2 · Feature Assembler ────────────────────────────
    features = assemble_features(photos)
    stages["step2_features"] = features.as_dict()

    # ─── Step 3 Stage 2 · Bands ────────────────────────────────
    bands = compute_bands(features)
    stages["step3_bands"] = bands.model_dump()

    # ─── Step 3 Stage 3 · Truth Table ──────────────────────────
    tt = truth_table_lookup(bands)
    stages["step4_truth_table"] = tt.model_dump()

    # ─── Step 4 · LLM Judge (skip for F1) ──────────────────────
    if tt.matched_pattern == "F1":
        llm = None
        stages["step5_llm"] = {"skipped": True, "reason": "truth_table_f1"}
    else:
        llm = judge.judge(photos, features, bands, tt)
        stages["step5_llm"] = {
            **llm.model_dump(),
            "evidence_count": len(llm.evidence),
        }

    # ─── Stage 4-7 · Policy Engine 后半段 ──────────────────────
    draft = run_post_truth_table(features, bands, tt, llm)
    stages["step6_final"] = {
        "strength": draft.final_strength,
        "type": draft.final_type,
        "display_decision": draft.display_decision,
        "score": draft.score,
        "primary_signal": draft.primary_signal,
    }

    association = to_association(draft)
    final_decision = AssociationDecision(
        association_id=f"assoc_{uuid.uuid4().hex[:8]}",
        photo_ids=[p.photo_id for p in photos],
        association=association,
        decision_source=draft.decision_source,  # type: ignore[arg-type]
    )

    return DecisionLog(
        decision_id=decision_id,
        scenario=scenario,
        path_taken="path_B",
        feature_assembler_plan=features.plan,        # ADR-0018
        stages=stages,
        policy_overrides=draft.policy_overrides,
        decision_source=draft.decision_source,
        final_decision=final_decision,
    )


def _build_suppressed_log(
    *,
    decision_id: str,
    scenario: str | None,
    photos: list[L1Output],
    stages: dict[str, Any],
    reason: str,
    decision_source: str,
) -> DecisionLog:
    suppressed = Association(
        score=0.0,
        type="weak",
        strength="none",
        primary_signal="pre_filter",
        reason=reason,
        display_decision="suppress",
    )
    final_decision = AssociationDecision(
        association_id=f"assoc_{uuid.uuid4().hex[:8]}",
        photo_ids=[p.photo_id for p in photos],
        association=suppressed,
        decision_source=decision_source,  # type: ignore[arg-type]
    )
    return DecisionLog(
        decision_id=decision_id,
        scenario=scenario,
        path_taken="path_B",
        stages=stages,
        policy_overrides=[],
        decision_source=decision_source,
        final_decision=final_decision,
    )


# ═════════════════════════════════════════════════════════════════
# 路径 A · 动态生长 (L2.5)
# 参考: docs/04_truth_table_growth.md
# ═════════════════════════════════════════════════════════════════

def run_growth_path(
    new_photo: L1Output,
    growing_albums: list[MiniAlbumFingerprint],
    scenario: str | None = None,
    judge=None,
) -> GrowthDecisionLog:
    """对单张新照片跑路径 A.

    流程:
      Step 1 · 候选集筛选 (filter_candidate_albums)
      Step 2 · 对每本候选相册算 4 维 features
      Step 3 · 分档 + 真值表查询
      Step 4 · MockGrowthJudge (v0.1)
      Step 5 · 后置硬规则 (HRG-POST-01..05)
      Step 6 · 多相册冲突仲裁 → 选一本
    """
    decision_id = f"decg_{uuid.uuid4().hex[:8]}"
    judge = judge or get_growth_judge()

    candidates = filter_candidate_albums(new_photo, growing_albums)

    if not candidates:
        return _empty_growth_log(decision_id, scenario, new_photo, [])

    evaluations = []
    all_overrides: list[dict] = []

    for album in candidates:
        features = compute_growth_features(new_photo, album)
        bands = compute_growth_bands(features)
        tt = lookup_growth(bands)

        # G-F1 不调 LLM, 直接 no_merge
        if tt.matched_pattern == "G-F1":
            from src.contracts import GrowthLLMJudgement
            llm_result = GrowthLLMJudgement(
                accept=False, semantic_reason="g_f1_no_signal",
                counter_evidence="", is_mock=True,
            )
        else:
            llm_result = judge.judge(new_photo, album, features, bands, tt)

        result = apply_post_hard_rules(new_photo, album, features, bands, tt, llm_result)
        evaluations.append(result.evaluation)
        all_overrides.extend(result.policy_overrides)

    # 多相册冲突仲裁
    albums_by_id = {a.mini_album_id: a for a in candidates}
    winner = resolve_multi_album_conflict(evaluations, albums_by_id)

    if winner is None:
        final = GrowthDecision(
            growth_decision_id=f"gd_{uuid.uuid4().hex[:8]}",
            new_photo_id=new_photo.photo_id,
            decision_tier="no_merge",
            merge_target_album_id=None,
            primary_signal="none",
            reason="no_eligible_album",
        )
    else:
        final = GrowthDecision(
            growth_decision_id=f"gd_{uuid.uuid4().hex[:8]}",
            new_photo_id=new_photo.photo_id,
            decision_tier=winner.decision_tier,
            merge_target_album_id=winner.album_id,
            primary_signal=winner.primary_signal,
            reason=f"{winner.truth_table_match.matched_pattern}_{winner.decision_tier}",
        )

    return GrowthDecisionLog(
        decision_id=decision_id,
        scenario=scenario,
        path_taken="path_A",
        new_photo_id=new_photo.photo_id,
        candidate_album_ids=[a.mini_album_id for a in candidates],
        per_album_evaluations=evaluations,
        policy_overrides=all_overrides,
        final_decision=final,
    )


def _empty_growth_log(
    decision_id: str,
    scenario: str | None,
    new_photo: L1Output,
    candidate_ids: list[str],
) -> GrowthDecisionLog:
    final = GrowthDecision(
        growth_decision_id=f"gd_{uuid.uuid4().hex[:8]}",
        new_photo_id=new_photo.photo_id,
        decision_tier="no_merge",
        merge_target_album_id=None,
        primary_signal="none",
        reason="no_candidate_albums",
    )
    return GrowthDecisionLog(
        decision_id=decision_id,
        scenario=scenario,
        path_taken="path_A",
        new_photo_id=new_photo.photo_id,
        candidate_album_ids=candidate_ids,
        per_album_evaluations=[],
        policy_overrides=[],
        final_decision=final,
    )


# ═════════════════════════════════════════════════════════════════
# 路径 C · 兜底回扫 (P0.5)
# 参考: docs/05_truth_table_backfill.md
# ═════════════════════════════════════════════════════════════════

def run_backfill_path(
    new_photo: L1Output,
    sedimented_pool: list[L1Output],
    scenario: str | None = None,
    judge=None,
) -> BackfillDecisionLog:
    """对单张新照片跑路径 C.

    流程:
      Step 1 · SQL 等价过滤 (30 天 / 非敏感 / 不在任何相册)
      Step 2 · 粗筛 (GPS/theme/event 任一命中)
      Step 3 · 复用主真值表 + LLM
      Step 4 · 兜底封顶 (三条 cap 全过才 create_new_album)
    """
    decision_id = f"decb_{uuid.uuid4().hex[:8]}"
    judge = judge or get_backfill_judge()

    candidates = filter_backfill_candidates(new_photo, sedimented_pool)

    # 早返: 召回不足
    if len(candidates) < 1:
        from src.contracts import BackfillCap as _C
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
            coarse_filter_candidates=[],
            main_truth_table_match=None,
            llm_judgement=None,
            backfill_caps_applied=[
                _C(rule="BACKFILL-CAP-03-recall_count", passed=False,
                   detail="coarse filter returned 0"),
            ],
            final_decision=final,
        )

    # 复用主真值表流程: 把 new_photo + 召回 视作 photos 列表
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

    return BackfillDecisionLog(
        decision_id=decision_id,
        scenario=scenario,
        new_photo_id=new_photo.photo_id,
        coarse_filter_candidates=[p.photo_id for p in candidates],
        main_truth_table_match=tt,
        llm_judgement=llm,
        backfill_caps_applied=result.caps,
        final_decision=result.decision,
    )


# ═════════════════════════════════════════════════════════════════
# 完整 L2 (上传张数分流 + C 真兜底 + 仲裁)
# 参考: docs/01_architecture.md, docs/09_arbitration.md
# ═════════════════════════════════════════════════════════════════

def run_full_l2(
    new_photos: list[L1Output],
    growing_albums: list[MiniAlbumFingerprint] | None = None,
    sedimented_pool: list[L1Output] | None = None,
    scenario: str | None = None,
) -> ArbitrationResult:
    """完整 L2 (ADR-0017 三路分流).

    流程 (参考 docs/23_pipeline_cascade_backfill.md):
      N=1: P → A → cascade_C → 沉淀
      N=2: light_judge (PRD §3.2.2, demo v0.1 不写测试)
      N≥3: B 整批 → 失败拆 N 张, 每张独立 A → cascade_C

    输入语义:
      · new_photos 本次窗口新照片
      · growing_albums 用户名下 is_growing=true 的相册指纹
      · sedimented_pool 30 天内沉淀单图
    """
    growing_albums = growing_albums or []
    sedimented_pool = sedimented_pool or []

    if not new_photos:
        raise ValueError("at least one new photo required")

    N = len(new_photos)

    # ═══════════════════════════════════════════════════════
    # N=1: 单张 → A → cascade_C → 沉淀
    # ═══════════════════════════════════════════════════════
    if N == 1:
        return _run_single_photo(new_photos[0], growing_albums, sedimented_pool, scenario)

    # ═══════════════════════════════════════════════════════
    # N=2: light_judge (PRD §3.2.2)
    # ═══════════════════════════════════════════════════════
    if N == 2:
        l2_log = run_l2_path_b(new_photos, scenario=scenario)
        return arbitrate(None, l2_log, None, scenario=scenario)

    # ═══════════════════════════════════════════════════════
    # N≥3: B 整批, 失败拆 N 张
    # ═══════════════════════════════════════════════════════
    return _run_multi_photo(new_photos, growing_albums, sedimented_pool, scenario)


def _run_single_photo(
    P: L1Output,
    growing_albums: list[MiniAlbumFingerprint],
    sedimented_pool: list[L1Output],
    scenario: str | None,
) -> ArbitrationResult:
    """N=1: P → Path A → cascade_C (ADR-0017)."""
    growth_log: GrowthDecisionLog | None = None
    if growing_albums:
        growth_log = run_growth_path(P, growing_albums, scenario=scenario)

    a_succeeded = (
        growth_log is not None
        and growth_log.final_decision.decision_tier in ("auto_merge", "ask_user")
    )

    # A 命中 → 直接走 A
    if a_succeeded:
        return arbitrate(growth_log, None, None, scenario=scenario)

    # A 失败 → cascade_C
    backfill_log: BackfillDecisionLog | None = None
    if sedimented_pool:
        backfill_log = cascade_backfill_single(P, sedimented_pool, scenario=scenario)

    return arbitrate(growth_log, None, backfill_log, scenario=scenario)


def _run_multi_photo(
    new_photos: list[L1Output],
    growing_albums: list[MiniAlbumFingerprint],
    sedimented_pool: list[L1Output],
    scenario: str | None,
) -> ArbitrationResult:
    """N≥3: Path B 整批 → 失败拆 N 张, 每张独立 A → cascade_C (ADR-0017)."""

    # ─── Path B 整批 ───
    l2_log = run_l2_path_b(new_photos, scenario=scenario)
    b_succeeded = (
        l2_log.final_decision.association.display_decision == "show_mini_album"
    )

    # B 命中: 整批成集, 不拆
    if b_succeeded:
        return arbitrate(None, l2_log, None, scenario=scenario)

    # B 失败 → 拆 N 张, 每张独立 A → C
    growth_merges: list[GrowthMergeRecord] = []
    cascade_albums: list[Association] = []
    settled_photo_ids: list[str] = []
    cascade_logs: list[BackfillDecisionLog] = []
    working_sediment = list(sedimented_pool)        # 拷贝, 动态增减

    for P_i in new_photos:
        # Path A (vs 老相册)
        g_log = None
        if growing_albums:
            g_log = run_growth_path(P_i, growing_albums, scenario=scenario)

        a_hit = (
            g_log is not None
            and g_log.final_decision.decision_tier in ("auto_merge", "ask_user")
        )
        if a_hit:
            growth_merges.append(GrowthMergeRecord(
                photo_id=P_i.photo_id,
                target_album_id=g_log.final_decision.merge_target_album_id or "",
                decision_tier=g_log.final_decision.decision_tier,  # type: ignore[arg-type]
            ))
            continue

        # Path C (cascade_backfill_single)
        b_log = cascade_backfill_single(P_i, working_sediment, scenario=scenario)
        cascade_logs.append(b_log)

        if b_log.final_decision.decision_tier == "create_new_album":
            recalled_ids = set(b_log.final_decision.recalled_photo_ids)
            cascade_albums.append(_album_from_backfill(P_i, b_log))
            working_sediment = [
                p for p in working_sediment if p.photo_id not in recalled_ids
            ]
        else:
            settled_photo_ids.append(P_i.photo_id)
            working_sediment.append(P_i)            # 进沉淀, 后续 P_j 可召回

    return arbitrate_cascade(
        l2_log=l2_log,
        growth_merges=growth_merges,
        cascade_albums=cascade_albums,
        settled_photo_ids=settled_photo_ids,
        cascade_logs=cascade_logs,
        scenario=scenario,
    )


def _album_from_backfill(P_i: L1Output, b_log: BackfillDecisionLog) -> Association:
    """从 BackfillDecision 派生 Association (ADR-0017 多产物 cascade_albums)."""
    decision = b_log.final_decision
    return Association(
        score=0.0,
        type="mixed",
        strength=decision.target_album_strength or "strong",
        primary_signal=decision.primary_signal,
        reason=decision.reason,
        display_decision="show_mini_album",
    )
