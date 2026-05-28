"""ADR-0019: scenarios expected 校准脚本.

跑所有 scenarios 的实际算法, 把 actual 输出写回 yaml expected.
这是 demo 阶段的 "golden file" 模式 — 锁定当前算法行为作为基线,
真实数据上线后 review 偏差.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml

from src.pipeline import (
    cascade_backfill_single,
    run_growth_path,
    run_l2_path_b,
)
from tests.personas import load_persona

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def calibrate_scenario(path: Path) -> tuple[str, str]:
    """读 scenario, 跑实际算法, 更新 expected. 返回 (status, summary)."""
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    persona = load_persona(spec["persona"])
    test_path = spec["test_path"]

    actual_expected = {}
    summary = ""

    if test_path == "L2":
        photo_ids = spec["input"]["new_photos"]
        photos = persona.get_photos(photo_ids)
        log = run_l2_path_b(photos)
        assoc = log.final_decision.association
        actual_expected = {
            "display_decision": assoc.display_decision,
            "matched_pattern": log.stages["step4_truth_table"]["matched_pattern"],
            "final_strength": assoc.strength,
            "final_type": assoc.type,
        }
        summary = f"display={assoc.display_decision} pattern={actual_expected['matched_pattern']} strength={assoc.strength}"

    elif test_path == "L2.5":
        new_photo = persona.get_photo(spec["input"]["new_photo"])
        albums = [persona.get_album(a) for a in spec["input"].get("old_albums", [])]
        log = run_growth_path(new_photo, albums)
        fd = log.final_decision
        actual_expected = {
            "decision_tier": fd.decision_tier,
            "target_album_id": fd.merge_target_album_id,
        }
        if log.per_album_evaluations:
            actual_expected["matched_pattern"] = log.per_album_evaluations[0].truth_table_match.matched_pattern
        summary = f"tier={fd.decision_tier} target={fd.merge_target_album_id}"

    elif test_path == "cascade":
        new_photo = persona.get_photo(spec["input"]["new_photo"])
        pool = persona.get_photos(spec["input"].get("sediment_pool", []))
        log = cascade_backfill_single(new_photo, pool)
        fd = log.final_decision
        actual_expected = {
            "decision_tier": fd.decision_tier,
            "recalled_count": len(fd.recalled_photo_ids),
        }
        summary = f"tier={fd.decision_tier} recalled={len(fd.recalled_photo_ids)}"

    # 保留 spec.expected 里非校准字段 (如 max_recalled / min_recalled)
    old_expected = spec.get("expected", {})
    for k in ("max_recalled", "min_recalled"):
        if k in old_expected:
            actual_expected[k] = old_expected[k]

    spec["expected"] = actual_expected
    path.write_text(
        yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return "ok", summary


def main():
    paths = sorted(SCENARIO_DIR.glob("*.yaml"))
    print(f"Calibrating {len(paths)} scenarios...")
    print("=" * 70)
    by_path = {"L2": 0, "L2.5": 0, "cascade": 0}
    by_tier = {}
    for p in paths:
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        tp = spec["test_path"]
        by_path[tp] = by_path.get(tp, 0) + 1
        status, summary = calibrate_scenario(p)
        # 抽样打印
        if by_path[tp] <= 3:
            print(f"  [{tp:8s}] {p.stem:50s} → {summary}")
    print("=" * 70)
    print(f"OK · Calibrated {len(paths)} scenarios")
    print(f"By path: {by_path}")


if __name__ == "__main__":
    main()
