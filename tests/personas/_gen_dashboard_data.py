"""ADR-0019 v0.4: HTML 看板数据收集器.

跑所有 scenarios, 收集完整 (用户记忆 + 输入 + 算法输出 + 期望对比 + 状态),
dump 到 tests/_dashboard_data.json 给 HTML 看板加载.

数据结构稳定, 可扩展 (后续加字段不破前端).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml

from src.pipeline import (
    cascade_backfill_single,
    run_growth_path,
    run_l2_path_b,
)
from src.test_utils.invariants import check_invariants
from tests.personas import load_persona

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"
PERSONA_DIR = Path(__file__).resolve().parent
DATA_PATH = ROOT / "tests" / "_dashboard_data.json"


def get_user_memory(persona_id: str) -> dict:
    """提取 persona 的 4 层记忆 mock 数据."""
    raw = yaml.safe_load((PERSONA_DIR / f"{persona_id}.yaml").read_text(encoding="utf-8"))
    return {
        "identity": raw.get("identity", {}),
        "user_model": raw.get("user_model", {}),
        "active_state": raw.get("active_state", {}),
        "event_log_count": len(raw.get("event_log", [])),
        "daily_digests_count": len(raw.get("daily_digests", [])),
    }


def serialize_photo(photo) -> dict:
    """L1Output 序列化为简洁 dict."""
    return {
        "id": photo.photo_id,
        "captured_at": photo.captured_at.isoformat() if photo.captured_at else None,
        "gps": list(photo.exif_location) if photo.exif_location else None,
        "theme_tags": list(photo.theme_tags),
        "main_subjects": list(photo.semantic_facts.main_subjects),
        "event_hint": photo.semantic_facts.event_hint,
        "emotional_tone": photo.emotional_tone,
        "meaning_anchors": list(photo.meaning_anchors),
        "narrative": photo.individual_title,
        "sensitive_level": photo.sensitive_level,
        "is_high_frequency_place": photo.is_high_frequency_place,
    }


def serialize_bands_with_reason(log_stages, log_features=None) -> dict:
    """7 维 bands + 每维的量化原因 (供前端点击展开)."""
    bands = log_stages.get("step3_bands", {})
    features = log_stages.get("step2_features", {})

    result = {}
    for dim, band in bands.items():
        score = features.get(f"{dim}_score") if isinstance(features, dict) else None
        # 加 dim 子结构数据 (location/time/theme/etc 完整 Feature)
        dim_data = features.get(dim) if isinstance(features, dict) else None
        result[dim] = {
            "band": band,
            "score": score,
            "detail": dim_data,    # 完整 Feature 数据, 含 rule_fired / shape / 聚类诊断 等
        }
    return result


def run_one(scenario_path: Path) -> dict:
    spec = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    persona_id = spec["persona"]
    persona = load_persona(persona_id)
    test_path = spec["test_path"]

    result = {
        "id": scenario_path.stem,
        "name": spec.get("name", ""),
        "behavior_pattern": spec.get("behavior_pattern", "-"),
        "category": spec.get("category", "未分类"),
        "test_type": spec.get("test_type", "robustness"),    # ADR-0019 v0.5
        "persona": persona_id,
        "test_path": test_path,
        "product_intent": spec.get("product_intent", ""),
        "input_photos": [],
        "user_memory": get_user_memory(persona_id),
        "algorithm_output": None,
        "expected": spec.get("expected", {}),
        "invariants_checked": spec.get("invariants"),
        "match": None,
        "violations": [],
        "error": None,
        "tested_at": datetime.now().isoformat(),
    }

    try:
        if test_path == "L2":
            ids = spec["input"]["new_photos"]
            photos = persona.get_photos(ids)
            result["input_photos"] = [serialize_photo(p) for p in photos]
            log = run_l2_path_b(photos, scenario=scenario_path.stem)

            stages = log.stages
            assoc = log.final_decision.association
            bands_with_reason = serialize_bands_with_reason(stages)
            tt = stages.get("step4_truth_table", {})
            llm = stages.get("step5_llm", {})

            result["algorithm_output"] = {
                "bands": bands_with_reason,
                "truth_table": {
                    "matched_pattern": tt.get("matched_pattern"),
                    "type": tt.get("type"),
                    "bounds_min": tt.get("bounds_min"),
                    "bounds_max": tt.get("bounds_max"),
                },
                "llm": {
                    "skipped": llm.get("skipped", False),
                    "proposed_strength": llm.get("proposed_strength"),
                    "proposed_type": llm.get("proposed_type"),
                    "semantic_reason": llm.get("semantic_reason"),
                    "evidence": [
                        {"photo_id": e.get("photo_id"), "evidence": e.get("evidence")}
                        for e in llm.get("evidence", [])
                    ] if not llm.get("skipped") else [],
                    "counter_evidence": llm.get("counter_evidence"),
                    "is_mock": llm.get("is_mock", True),
                },
                "policy_overrides": log.policy_overrides,
                "final_decision": {
                    "display_decision": assoc.display_decision,
                    "strength": assoc.strength,
                    "type": assoc.type,
                    "primary_signal": assoc.primary_signal,
                    "score": assoc.score,
                    "reason": assoc.reason,
                },
                "feature_assembler_plan": log.feature_assembler_plan,
            }

            # 3 档: 主期望严格 (match) / acceptable 字段兜底 (acceptable) / 都不中 (mismatch)
            exp = spec.get("expected") or {}
            acc_map = exp.get("acceptable") or {}
            match = None if not exp else "match"
            details = []
            for k, v in exp.items():
                if k == "acceptable":
                    continue
                if k == "display_decision":
                    actual = assoc.display_decision
                elif k == "matched_pattern":
                    actual = tt.get("matched_pattern")
                elif k == "final_strength":
                    actual = assoc.strength
                else:
                    continue
                allowed = v if isinstance(v, list) else [v]
                acc_v = acc_map.get(k) if isinstance(acc_map, dict) else None
                acceptable = (acc_v if isinstance(acc_v, list) else [acc_v]) if acc_v else []
                if actual in allowed:
                    pass
                elif actual in acceptable:
                    if match == "match":
                        match = "acceptable"
                else:
                    match = "mismatch"
                    details.append(f"{k}: expected {allowed}, acceptable {acceptable}, actual={actual}")
            result["match"] = match
            if details:
                result["mismatch_details"] = details

        elif test_path == "L2.5":
            pid = spec["input"]["new_photo"]
            photo = persona.get_photo(pid)
            albums = [persona.get_album(a) for a in spec["input"].get("old_albums", [])]
            result["input_photos"] = [serialize_photo(photo)]
            result["candidate_albums"] = [
                {"id": a.mini_album_id, "title": a.title,
                 "theme_clusters": [c.representative for c in a.theme_clusters],
                 "event_primary": a.event_agg.primary,
                 "anchors_set": list(a.anchors_set),
                 "place_anchor_gps": list(a.place_anchor.clusters[0].centroid) if a.place_anchor.clusters else None,
                 "photo_count": a.photo_count}
                for a in albums
            ]
            log = run_growth_path(photo, albums, scenario=scenario_path.stem)
            fd = log.final_decision
            result["algorithm_output"] = {
                "candidates_evaluated": len(log.per_album_evaluations),
                "per_album": [
                    {
                        "album_id": e.album_id,
                        "matched_pattern": e.truth_table_match.matched_pattern,
                        "decision_tier": e.decision_tier,
                        "bands": e.bands.model_dump(),
                        "features": e.features.model_dump() if e.features else None,
                        "llm_accept": e.llm.accept if e.llm else None,
                        "llm_reason": e.llm.semantic_reason if e.llm else None,
                    } for e in log.per_album_evaluations
                ],
                "final_decision": {
                    "decision_tier": fd.decision_tier,
                    "target_album_id": fd.merge_target_album_id,
                    "primary_signal": fd.primary_signal,
                    "reason": fd.reason,
                },
                "policy_overrides": log.policy_overrides,
            }
            # 3 档: 主期望 (match) / acceptable (acceptable) / mismatch
            exp = spec.get("expected") or {}
            acc_map = exp.get("acceptable") or {}
            match = None if not exp else "match"
            details = []
            for k, v in exp.items():
                if k == "acceptable":
                    continue
                if k == "decision_tier":
                    allowed = v if isinstance(v, list) else [v]
                    acc_v = acc_map.get("decision_tier") if isinstance(acc_map, dict) else None
                    acceptable = (acc_v if isinstance(acc_v, list) else [acc_v]) if acc_v else []
                    if fd.decision_tier in allowed:
                        pass
                    elif fd.decision_tier in acceptable:
                        if match == "match":
                            match = "acceptable"
                    else:
                        match = "mismatch"
                        details.append(f"decision_tier: expected {allowed}, acceptable {acceptable}, actual={fd.decision_tier}")
            result["match"] = match
            if details:
                result["mismatch_details"] = details

        elif test_path == "cascade":
            pid = spec["input"]["new_photo"]
            photo = persona.get_photo(pid)
            pool = persona.get_photos(spec["input"].get("sediment_pool", []))
            result["input_photos"] = [serialize_photo(photo)]
            result["sediment_pool"] = [serialize_photo(p) for p in pool]
            log = cascade_backfill_single(photo, pool, scenario=scenario_path.stem)
            fd = log.final_decision
            result["algorithm_output"] = {
                "coarse_filter_candidates": log.coarse_filter_candidates,
                "priority_ranking": [r.model_dump() for r in log.priority_ranking],
                "main_truth_table": (
                    log.main_truth_table_match.model_dump() if log.main_truth_table_match else None
                ),
                "llm": (
                    {
                        "proposed_strength": log.llm_judgement.proposed_strength,
                        "semantic_reason": log.llm_judgement.semantic_reason,
                        "is_mock": log.llm_judgement.is_mock,
                    } if log.llm_judgement else None
                ),
                "caps": [c.model_dump() for c in log.backfill_caps_applied],
                "final_decision": {
                    "decision_tier": fd.decision_tier,
                    "recalled_photo_ids": fd.recalled_photo_ids,
                    "target_album_strength": fd.target_album_strength,
                    "reason": fd.reason,
                },
            }
            # 3 档: 主期望 (match) / acceptable (acceptable) / mismatch
            exp = spec.get("expected") or {}
            acc_map = exp.get("acceptable") or {}
            match = None if not exp else "match"
            details = []
            for k, v in exp.items():
                if k == "acceptable":
                    continue
                if k == "decision_tier":
                    allowed = v if isinstance(v, list) else [v]
                    acc_v = acc_map.get("decision_tier") if isinstance(acc_map, dict) else None
                    acceptable = (acc_v if isinstance(acc_v, list) else [acc_v]) if acc_v else []
                    if fd.decision_tier in allowed:
                        pass
                    elif fd.decision_tier in acceptable:
                        if match == "match":
                            match = "acceptable"
                    else:
                        match = "mismatch"
                        details.append(f"decision_tier: expected {allowed}, acceptable {acceptable}, actual={fd.decision_tier}")
            result["match"] = match
            if details:
                result["mismatch_details"] = details

        # Invariants 校验
        if test_path in ("L2", "L2.5", "cascade"):
            spec_invs = spec.get("invariants")
            violations = check_invariants(log, only=spec_invs)
            result["violations"] = violations

    except Exception as e:
        result["error"] = str(e)
        import traceback
        result["traceback"] = traceback.format_exc()[:500]

    return result


def main():
    paths = sorted(SCENARIO_DIR.glob("*.yaml"))
    print(f"Collecting dashboard data for {len(paths)} scenarios...")

    scenarios = []
    for p in paths:
        scenarios.append(run_one(p))

    data = {
        "version": "v0.4",
        "generated_at": datetime.now().isoformat(),
        "total_scenarios": len(scenarios),
        "by_category": {},
        "by_path": {},
        "by_persona": {},
        "scenarios": scenarios,
    }

    # 统计
    for s in scenarios:
        bp = s.get("behavior_pattern", "-")
        cat = bp.split(".")[0] if "." in bp else bp
        data["by_category"].setdefault(cat, 0)
        data["by_category"][cat] += 1
        data["by_path"].setdefault(s.get("test_path", "?"), 0)
        data["by_path"][s.get("test_path", "?")] += 1
        data["by_persona"].setdefault(s.get("persona", "?"), 0)
        data["by_persona"][s.get("persona", "?")] += 1

    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"OK: {DATA_PATH} ({len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
