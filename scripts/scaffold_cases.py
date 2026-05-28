"""把 tests/personas/scenarios/*.yaml → api_harness/cases/{L2,L2.5,cascade}/*.yaml。

参考: TEST_PLAN §3-§4 / SPEC §3 case schema。
- L2:trigger = scenario.input.new_photos;无 setup。
- L2.5:setup.seed_photos 按 album → seed group 映射(SEED_MAP);trigger = input.new_photo。
- cascade:全部标 verdict=deferred + defer_reason=cascade_pending(2026-05-28 实证后端 cascade 路径疑似缺失)。
- ⛔ scenarios:verdict=deferred + defer_reason ∈ {loc, time, loc+time, hfp}。
- 🟡/✅ scenarios:verdict=runnable。expected 取原 yaml,合并 acceptable 进列表。

跑法(项目根目录):
    python scripts/scaffold_cases.py            # 覆盖式生成所有 case
    python scripts/scaffold_cases.py --dry      # 只打印计划,不写文件
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = REPO / "tests" / "personas" / "scenarios"
CASES_DIR = REPO / "api_harness" / "cases"

# ── 每条场景的判定(stem → verdict + defer_reason)──
# 来自 TEST_PLAN §3 / §4 + 2026-05-28 Ace 拍的边界(T7 ⛔→🟡)
VERDICT_MAP: dict[str, tuple[str, str | None]] = {
    # ── L2 ✅ runnable (16) ──
    "D2_zhang_hospital_sensitive": ("runnable", None),
    "FP_A1_zhang_breakfast_daily": ("runnable", None),
    "FP_A6_xiaowang_cafe_multi_subject": ("runnable", None),
    "FP_B1_zhang_stoplist_loophole": ("runnable", None),
    "FP_B2_li_th0_reverse": ("runnable", None),
    "FP_B3_zhang_event_activity_walk_drill": ("runnable", None),
    "A6_zhang_plant_growth_30d": ("runnable", None),
    "ANC1_li_anchor_multi_granularity": ("runnable", None),
    "B5_li_business_plus_travel": ("runnable", None),
    "C4_xiaowang_steak_5_angles": ("runnable", None),
    "C8_xiaowang_cafe_multi_subject": ("runnable", None),
    "D1_zhang_screenshot_in_gathering": ("runnable", None),
    "EV1_zhang_event_signal_conflict": ("runnable", None),
    "T13_xiaowang_citywalk_uniform_low": ("runnable", None),
    "TH1_li_theme_granularity_mix": ("runnable", None),
    "TH2_xiaowang_multi_strong_theme": ("runnable", None),
    # ── L2 🟡 partial (6) ──
    "C3_xiaowang_photo_wall": ("partial", None),
    "C7_xiaowang_concert_burst": ("partial", None),
    "T7_li_around_landmark_small_loop": ("partial", None),
    "T15_xiaowang_fireworks_newyear": ("partial", None),
    "T18_xiaowang_checkin_multi_spot": ("partial", None),
    "T22_li_camping_crossday_event": ("partial", None),
    # ── L2 ⛔ deferred (24) ──
    "FP_A2_zhang_daily_record_pretend": ("deferred", "loc"),
    "FP_A3_zhang_cross_season_park": ("deferred", "time"),
    "FP_A5_zhang_repeat_hotpot": ("deferred", "time"),
    "FP_B4_zhang_outing_walk_cheat": ("deferred", "loc"),
    "FP_B5_zhang_burst_3_events": ("deferred", "time"),
    "FP_B7_zhang_location_buffer_edge": ("deferred", "loc"),
    "FP_B11_zhang_hfp_mismarked": ("deferred", "loc"),
    "A1_zhang_insurance_burst": ("deferred", "time"),
    "A2_zhang_weekly_park_walk": ("deferred", "time"),
    "A5_zhang_shopping_subzone": ("deferred", "loc"),
    "B1_li_burst_plus_one": ("deferred", "loc"),
    "B2_li_xihu_overnight": ("deferred", "time"),
    "B3_li_one_day_long_break": ("deferred", "time"),
    "B6_li_airport_farewell": ("deferred", "loc"),
    "B7_li_pick_grandkid_routine": ("deferred", "loc"),
    "C6_xiaowang_hike_gps_drift": ("deferred", "loc"),
    "D9_zhang_high_freq_strong_event": ("deferred", "hfp"),
    "T1_li_xihu_loop_15km": ("deferred", "loc+time"),
    "T3_li_pedestrian_street_uneven": ("deferred", "loc"),
    "T4_xiaowang_hike_sparse_dense": ("deferred", "loc+time"),
    "T12_li_one_day_multi_spot_70km": ("deferred", "loc+time"),
    "T19_li_marathon_10_spots": ("deferred", "loc+time"),
    "T20_li_resort_lazy_3days": ("deferred", "loc+time"),
    "T21_xiaowang_burst_plus_gap": ("deferred", "time"),
    # ── L2.5 ✅ runnable (12) ──
    "A4_zhang_granddaughter_grab": ("runnable", None),
    "L25_li_camping_to_xihu_no_merge": ("runnable", None),
    "L25_li_multi_anchor_to_xihu": ("runnable", None),
    "L25_li_th_granularity_细颗粒_to_xihu": ("runnable", None),
    "L25_R1_zhang_balcony_to_walk_no_merge": ("runnable", None),
    "L25_R2_zhang_walk_to_walk_auto_merge": ("runnable", None),
    "L25_R3_li_xihu_new_to_xihu_auto": ("runnable", None),
    "L25_xiaowang_concert_to_walk_no_merge": ("runnable", None),
    "L25_xiaowang_multi_theme_to_walk_no_merge": ("runnable", None),
    "L25_zhang_distractor_screenshot_to_walk": ("runnable", None),
    "L25_zhang_event_conflict_to_album": ("runnable", None),
    "L25_zhang_sensitive_to_any_no_merge": ("runnable", None),
    # ── L2.5 🟡 partial (1) ──
    "L25_zhang_high_freq_birthday_celebration": ("partial", None),
    # ── L2.5 ⛔ deferred (2) ──
    "L25_R4_li_gugong_to_xihu_no_merge": ("deferred", "loc"),
    "L25_li_pick_grandkid_high_freq": ("deferred", "loc"),
    # ── cascade 全部 deferred (15, Ace 2026-05-28 拍"先去测试 L2/L2.5,回滚有问题")──
    "CB_01_li_shanghai_oneday_recall": ("deferred", "cascade_pending"),
    "CB_02_li_overnight_xihu_recall": ("deferred", "cascade_pending"),
    "CB_03_li_resort_lazy_empty": ("deferred", "cascade_pending"),
    "CB_04_li_th_granularity_xihu_recall": ("deferred", "cascade_pending"),
    "CB_05_zhang_balcony_recall": ("deferred", "cascade_pending"),
    "CB_06_zhang_empty_pool_insufficient": ("deferred", "cascade_pending"),
    "CB_07_li_xihu_recall": ("deferred", "cascade_pending"),
    "CB_08_li_gugong_cross_city_no_backfill": ("deferred", "cascade_pending"),
    "CB_09_zhang_event_conflict_empty": ("deferred", "cascade_pending"),
    "CB_10_xiaowang_checkin_no_backfill": ("deferred", "cascade_pending"),
    "CB_11_xiaowang_concert_cross_city": ("deferred", "cascade_pending"),
    "CB_12_xiaowang_fireworks_no_recall": ("deferred", "cascade_pending"),
    "CB_13_xiaowang_multi_theme_no_recall": ("deferred", "cascade_pending"),
    "CB_14_zhang_screenshot_no_recall": ("deferred", "cascade_pending"),
    "CB_15_zhang_sensitive_no_recall": ("deferred", "cascade_pending"),
}

# album → seed photos(persona group 直接对应,scaffolder 会过滤掉 trigger 重复)
SEED_MAP: dict[str, list[str]] = {
    "past_xihu_album":          ["l01", "l02", "l03", "l04", "l05", "l06"],          # lake_overnight 全 6
    "pick_grandkid_album":      ["l34", "l35", "l36", "l37", "l38"],                  # pick_grandkid_routine 全 5
    "weekly_park_walk_album":   ["z07", "z09", "z14", "z17", "z22", "z26"],           # weekly_park_walk 前 6
    "granddaughter_album":      ["z38", "z39", "z40", "z41", "z42", "z43"],           # granddaughter_birthday_at_home 全 6
}

DEFER_HUMAN: dict[str, str] = {
    "loc": "GPS / 位置信号缺失,本轮无法触发该判定面",
    "time": "captured_at / 时间信号缺失",
    "loc+time": "GPS + 时间双信号缺失",
    "hfp": "高频地点信号缺失",
    "cascade_pending": "后端 cascade 路径疑似缺失(2026-05-28 探针),先搁置",
}


def normalize_expected(exp: dict[str, Any] | None) -> dict[str, Any]:
    """合并 acceptable 进主字段,展平成 list(便于 runner 多值匹配)。"""
    if not exp:
        return {}
    out: dict[str, Any] = {}
    accept = exp.get("acceptable") or {}
    for key in ("display_decision", "decision_tier"):
        v = exp.get(key)
        if v is None:
            continue
        v_list = v if isinstance(v, list) else [v]
        av = accept.get(key)
        if av:
            av_list = av if isinstance(av, list) else [av]
            v_list = v_list + [x for x in av_list if x not in v_list]
        out[key] = v_list if len(v_list) > 1 else v_list[0]
    # 其余原样搬(min_recalled / max_recalled 等)
    for key in ("min_recalled", "max_recalled", "matched_pattern", "final_strength", "target_album"):
        if key in exp:
            out[key] = exp[key]
    return out


def scaffold_one(scenario_path: Path) -> tuple[Path, dict] | None:
    s = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    stem = scenario_path.stem
    if stem not in VERDICT_MAP:
        print(f"⚠ 未在 VERDICT_MAP 登记:{stem} → 跳过")
        return None
    verdict, defer_reason = VERDICT_MAP[stem]
    path = s.get("test_path") or "?"
    persona = s.get("persona") or "?"
    inp = s.get("input") or {}

    case: dict[str, Any] = {
        "id": stem,
        "source_scenario": f"{stem}.yaml",
        "persona": persona,
        "path": path,
        "verdict": "deferred" if verdict == "deferred" else "runnable",
    }
    if defer_reason:
        case["defer_reason"] = defer_reason
        case["defer_reason_human"] = DEFER_HUMAN.get(defer_reason, defer_reason)

    if verdict != "deferred":
        # 装 setup / trigger
        if path == "L2":
            case["setup"] = {}
            case["trigger"] = {"photos": inp.get("new_photos") or []}
        elif path == "L2.5":
            old_albums = inp.get("old_albums") or []
            trigger_id = inp.get("new_photo")
            seeds: list[str] = []
            rationale_lines: list[str] = []
            for album in old_albums:
                seed_ids = SEED_MAP.get(album, [])
                if not seed_ids:
                    rationale_lines.append(f"⚠ {album}: SEED_MAP 未配置")
                    continue
                # 过滤掉与 trigger 重叠的(trigger 不应同时在 seed 里)
                seed_ids = [s for s in seed_ids if s != trigger_id]
                seeds.extend([s for s in seed_ids if s not in seeds])
                rationale_lines.append(f"{album} ← {seed_ids}")
            if old_albums and not seeds:
                # 老相册指针有但 SEED_MAP 没配 → 这场景跑不起来
                case["verdict"] = "deferred"
                case["defer_reason"] = "no_seed_mapping"
                case["defer_reason_human"] = f"SEED_MAP 未为 {old_albums} 配置成员 → 标 deferred 等 Ace 指定"
            else:
                case["setup"] = {"seed_photos": seeds}
                if rationale_lines:
                    case["setup"]["setup_rationale"] = " | ".join(rationale_lines)
                if not old_albums:
                    case["setup"]["setup_rationale"] = "(原 scenario 无 old_albums → 跑后端默认 → 预期可能 no_candidate_album)"
                case["trigger"] = {"photos": [trigger_id] if trigger_id else []}
        # cascade 不到这分支(已 deferred)

    case["expected"] = normalize_expected(s.get("expected"))
    if s.get("invariants"):
        case["invariants"] = s["invariants"]
    if s.get("notes"):
        case["notes"] = s["notes"]
    if s.get("product_intent"):
        case["product_intent"] = s["product_intent"]

    # 输出路径:用原 test_path 分目录
    target_dir = CASES_DIR / path
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{stem}.yaml"
    return target, case


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印计划,不写文件")
    args = ap.parse_args()

    # 清空旧 cases(避免老 pilot 名残留)
    if not args.dry and CASES_DIR.exists():
        for sub in ("L2", "L2.5", "cascade"):
            d = CASES_DIR / sub
            if d.exists():
                for f in d.glob("*.yaml"):
                    f.unlink()
        print(f"已清空旧 cases/{{L2,L2.5,cascade}}/")

    counts: dict[str, int] = {"runnable": 0, "deferred": 0, "unknown": 0}
    by_path: dict[str, int] = {}
    for sp in sorted(SCENARIOS_DIR.glob("*.yaml")):
        result = scaffold_one(sp)
        if not result:
            counts["unknown"] += 1
            continue
        target, case = result
        verdict = case["verdict"]
        counts[verdict] = counts.get(verdict, 0) + 1
        by_path[case["path"]] = by_path.get(case["path"], 0) + 1
        if args.dry:
            print(f"  [{verdict:8s}] {target.relative_to(REPO)}  setup={('seed=' + str(len((case.get('setup') or {}).get('seed_photos') or [])) if case.get('path')=='L2.5' else '-')}")
        else:
            target.write_text(
                yaml.safe_dump(case, allow_unicode=True, sort_keys=False, width=140),
                encoding="utf-8",
            )

    print(f"\n=== 完成 ===")
    print(f"  按 verdict: {counts}")
    print(f"  按 path:    {by_path}")
    print(f"  总: {sum(counts.values())} 条 case")


if __name__ == "__main__":
    main()
