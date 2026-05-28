"""一键演示: 跑全套场景 + 完整 L2 三路汇合.

用法:
  python scripts/run_demo.py                # 跑全部场景
  python scripts/run_demo.py <scenario>     # 跑指定场景 (例: full_case3_backfill)
  python scripts/run_demo.py --list         # 列出所有场景
  python scripts/run_demo.py --summary      # 只打摘要,不打完整决策日志
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Windows 控制台 UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from src.contracts import MiniAlbumFingerprint                           # noqa: E402
from src.pipeline import (                                                # noqa: E402
    run_backfill_path,
    run_full_l2,
    run_growth_path,
    run_l2_path_b,
)
from tests.conftest import load_photo, load_photos                       # noqa: E402

SCENARIO_DIR = ROOT / "tests" / "scenarios"
ALBUM_DIR = ROOT / "tests" / "fixtures" / "albums"


def banner(text: str, char: str = "─") -> str:
    line = char * 70
    return f"\n{line}\n  {text}\n{line}"


def _load_album(name: str) -> MiniAlbumFingerprint:
    path = ALBUM_DIR / f"{name}.json"
    return MiniAlbumFingerprint.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


def run(target: str | None = None, summary_only: bool = False) -> None:
    scenarios = sorted(SCENARIO_DIR.glob("*.yaml"))
    if target:
        scenarios = [p for p in scenarios if p.stem == target]
        if not scenarios:
            print(f"未找到场景: {target}")
            print("可用场景:")
            for p in sorted(SCENARIO_DIR.glob("*.yaml")):
                print(f"  · {p.stem}")
            return

    for scenario_path in scenarios:
        spec = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        trigger = spec.get("trigger", "batch_upload")

        print(banner(f"Scenario · {scenario_path.stem}", char="═"))
        print(f"  trigger     : {trigger}")
        print(f"  name        : {spec['name']}")

        if trigger == "dynamic_growth":
            _run_growth(spec, summary_only)
        elif trigger == "backfill_scan":
            _run_backfill(spec, summary_only)
        elif trigger == "full_l2":
            _run_full(spec, summary_only)
        else:
            _run_l2(spec, summary_only)


def _run_l2(spec: dict, summary_only: bool) -> None:
    photos = load_photos([p["fixture"] for p in spec["photos"]])
    log = run_l2_path_b(photos, scenario=spec.get("name"))
    assoc = log.final_decision.association
    print("\n  --- 路径 B · L2 主路径 ---")
    print(f"  display          : {assoc.display_decision}")
    print(f"  matched_pattern  : {log.stages['step4_truth_table']['matched_pattern']}")
    print(f"  final_strength   : {assoc.strength}")
    print(f"  final_type       : {assoc.type}")
    print(f"  composite_score  : {assoc.score:.3f}  (监控用)")
    print(f"  policy_overrides : {len(log.policy_overrides)}")
    if not summary_only:
        print("\n  --- decision_log ---")
        print(_pretty(log))


def _run_growth(spec: dict, summary_only: bool) -> None:
    new_photo = load_photo(spec["new_photo"]["fixture"])
    albums = [_load_album(a["fixture"]) for a in spec["candidate_albums"]]
    log = run_growth_path(new_photo, albums, scenario=spec.get("name"))
    fd = log.final_decision
    print("\n  --- 路径 A · 动态生长 ---")
    print(f"  new_photo        : {fd.new_photo_id}")
    print(f"  candidates       : {log.candidate_album_ids}")
    print(f"  decision_tier    : {fd.decision_tier}")
    print(f"  merge_target     : {fd.merge_target_album_id}")
    for ev in log.per_album_evaluations:
        print(f"    · {ev.album_id} → {ev.truth_table_match.matched_pattern} → {ev.decision_tier}")
    if not summary_only:
        print("\n  --- growth_decision_log ---")
        print(_pretty(log))


def _run_backfill(spec: dict, summary_only: bool) -> None:
    new_photo = load_photo(spec["new_photo"]["fixture"])
    pool = [load_photo(p["fixture"]) for p in spec.get("sedimented_pool", [])]
    log = run_backfill_path(new_photo, pool, scenario=spec.get("name"))
    fd = log.final_decision
    print("\n  --- 路径 C · 兜底回扫 ---")
    print(f"  new_photo        : {fd.new_photo_id}")
    print(f"  coarse_filter    : {log.coarse_filter_candidates}")
    print(f"  matched_pattern  : {log.main_truth_table_match.matched_pattern if log.main_truth_table_match else 'none'}")
    print(f"  decision_tier    : {fd.decision_tier}")
    print(f"  recalled         : {fd.recalled_photo_ids}")
    print("  caps:")
    for cap in log.backfill_caps_applied:
        mark = "✓" if cap.passed else "✗"
        print(f"    {mark} {cap.rule}: {cap.detail}")
    if not summary_only:
        print("\n  --- backfill_decision_log ---")
        print(_pretty(log))


def _run_full(spec: dict, summary_only: bool) -> None:
    new_photos = [load_photo(p["fixture"]) for p in spec.get("new_photos", [])]
    albums = [_load_album(a["fixture"]) for a in spec.get("growing_albums", [])]
    pool = [load_photo(p["fixture"]) for p in spec.get("sedimented_pool", [])]
    result = run_full_l2(new_photos, albums, pool, scenario=spec.get("name"))
    print("\n  --- 完整 L2 · 三路 + 仲裁 ---")
    print(f"  case             : {result.case_matched}")
    print(f"  arbitration_win  : {result.arbitration_winner}")
    print(f"  ending           : {result.ending}")
    print(f"  target_album     : {result.target_album_id}")
    print(f"  discarded        : {result.discarded_paths}")
    print(f"  喜宝话术         : {result.user_facing_message or '(无, 无感处理)'}")

    print("\n  --- 三路原始日志 ---")
    print(f"  路径 A: {'命中' if result.growth_log else '未触发'}", end="")
    if result.growth_log:
        print(f" → {result.growth_log.final_decision.decision_tier}")
    else:
        print()
    print(f"  路径 B: {'命中' if result.l2_log else '未触发'}", end="")
    if result.l2_log:
        print(f" → {result.l2_log.final_decision.association.display_decision}")
    else:
        print()
    print(f"  路径 C: {'命中' if result.backfill_log else '未触发'}", end="")
    if result.backfill_log:
        print(f" → {result.backfill_log.final_decision.decision_tier}")
    else:
        print()

    if not summary_only:
        print("\n  --- arbitration_result (full) ---")
        print(_pretty(result))


def _pretty(model) -> str:
    return json.dumps(json.loads(model.model_dump_json()), ensure_ascii=False, indent=2)


def list_scenarios() -> None:
    print("\n可用场景:\n")
    by_trigger: dict[str, list[Path]] = {}
    for p in sorted(SCENARIO_DIR.glob("*.yaml")):
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        trigger = spec.get("trigger", "batch_upload")
        by_trigger.setdefault(trigger, []).append(p)

    for trigger in sorted(by_trigger.keys()):
        print(f"  ── {trigger} ──")
        for p in by_trigger[trigger]:
            spec = yaml.safe_load(p.read_text(encoding="utf-8"))
            print(f"  · {p.stem:35s}  {spec['name']}")
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    summary_only = "--summary" in args

    # ADR-0018: --plan a/b CLI flag, 覆盖 config/feature_assembler.yaml
    plan_flag = None
    for i, a in enumerate(args):
        if a == "--plan" and i + 1 < len(args):
            v = args[i + 1].lower()
            if v in ("a", "l2_2.0"):
                plan_flag = "L2_2.0"
            elif v in ("b", "l2_1.0"):
                plan_flag = "L2_1.0"

    if plan_flag is not None:
        # 通过环境变量传递, 让 config_loader 检测
        import os
        os.environ["SEENFUL_FEATURE_ASSEMBLER_PLAN"] = plan_flag
        print(f"  ⚙ ADR-0018 plan override: {plan_flag}")

    # 过滤所有 -- 开头的 flag
    args = [a for a in args if not a.startswith("--")]
    # 过滤 plan flag 的 value (跟在 --plan 后的下一个 arg)
    filtered = []
    skip_next = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        filtered.append(a)
    args = filtered

    if "--list" in sys.argv:
        list_scenarios()
    else:
        target = args[0] if args else None
        run(target=target, summary_only=summary_only)
