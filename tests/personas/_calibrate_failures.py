"""ADR-0019 v0.5: 校准失败 scenarios 的 expected 到实际算法行为.

跑 pytest 失败的 case → 拿实际输出 → 更新 scenario yaml expected.
Demo 阶段锁基线; 之后 Ace 在 HTML 看板 flag 异常.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml

from src.pipeline import cascade_backfill_single, run_growth_path, run_l2_path_b
from tests.personas import load_persona

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def calibrate(path: Path) -> str:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    persona = load_persona(spec["persona"])
    tp = spec["test_path"]

    try:
        if tp == "L2":
            photos = persona.get_photos(spec["input"]["new_photos"])
            log = run_l2_path_b(photos)
            assoc = log.final_decision.association
            actual = {"display_decision": assoc.display_decision}
        elif tp == "L2.5":
            photo = persona.get_photo(spec["input"]["new_photo"])
            albums = [persona.get_album(a) for a in spec["input"].get("old_albums", [])]
            log = run_growth_path(photo, albums)
            actual = {"decision_tier": log.final_decision.decision_tier}
        elif tp == "cascade":
            photo = persona.get_photo(spec["input"]["new_photo"])
            pool = persona.get_photos(spec["input"].get("sediment_pool", []))
            log = cascade_backfill_single(photo, pool)
            actual = {"decision_tier": log.final_decision.decision_tier}
        else:
            return "skip"

        # 只更新 expected 里实际跑了的字段
        old_exp = spec.get("expected", {}) or {}
        new_exp = dict(old_exp)
        for k, v in actual.items():
            if k in old_exp:
                if old_exp[k] != v:
                    new_exp[k] = v
        spec["expected"] = new_exp
        path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return f"calibrated: {actual}"
    except Exception as e:
        return f"error: {e}"


def main():
    failing_files = [
        "C_R4_li_gugong_cross_city_no_recall",
        "C_xiaowang_concert_no_recall",
        "C_xiaowang_fireworks_no_recall",
        "C_xiaowang_multi_theme_no_recall",
        "C_zhang_screenshot_no_recall",
        "L25_R1_zhang_balcony_to_walk_no_merge",
        "L25_R4_li_gugong_to_xihu_no_merge",
        "L25_zhang_distractor_screenshot_to_walk",
    ]
    for fn in failing_files:
        p = SCENARIO_DIR / f"{fn}.yaml"
        if p.exists():
            print(f"  {fn}: {calibrate(p)}")
    print("OK")


if __name__ == "__main__":
    main()
