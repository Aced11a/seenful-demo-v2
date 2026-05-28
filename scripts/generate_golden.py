"""根据当前 pipeline 输出生成/刷新 golden file.

用法:
  python scripts/generate_golden.py           # 刷新全部场景
  python scripts/generate_golden.py NAME      # 仅刷新指定场景

⚠️ 刷新 golden 必须能在 PR 描述里说明原因 (CLAUDE.md §测试驱动收尾).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json as _json

from src.contracts import MiniAlbumFingerprint                              # noqa: E402
from src.pipeline import (                                                    # noqa: E402
    run_backfill_path,
    run_full_l2,
    run_growth_path,
    run_l2_path_b,
)
from tests.conftest import load_photo, load_photos                            # noqa: E402

SCENARIO_DIR = ROOT / "tests" / "scenarios"
GOLDEN_DIR = ROOT / "tests" / "golden"
ALBUM_DIR = ROOT / "tests" / "fixtures" / "albums"


def _load_album(name: str) -> MiniAlbumFingerprint:
    return MiniAlbumFingerprint.model_validate(
        _json.loads((ALBUM_DIR / f"{name}.json").read_text(encoding="utf-8"))
    )


def regenerate(target: str | None = None) -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    for scenario_path in sorted(SCENARIO_DIR.glob("*.yaml")):
        if target and scenario_path.stem != target:
            continue
        spec = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        trigger = spec.get("trigger", "batch_upload")

        if trigger == "dynamic_growth":
            new_photo = load_photo(spec["new_photo"]["fixture"])
            albums = [_load_album(a["fixture"]) for a in spec["candidate_albums"]]
            log = run_growth_path(new_photo, albums, scenario=scenario_path.stem)
            data = json.loads(log.model_dump_json())
            data.pop("decision_id", None)
            if "final_decision" in data:
                data["final_decision"].pop("growth_decision_id", None)
        elif trigger == "backfill_scan":
            new_photo = load_photo(spec["new_photo"]["fixture"])
            pool = [load_photo(p["fixture"]) for p in spec.get("sedimented_pool", [])]
            log = run_backfill_path(new_photo, pool, scenario=scenario_path.stem)
            data = json.loads(log.model_dump_json())
            data.pop("decision_id", None)
            if "final_decision" in data:
                data["final_decision"].pop("backfill_decision_id", None)
        elif trigger == "full_l2":
            new_photos = [load_photo(p["fixture"]) for p in spec.get("new_photos", [])]
            albums = [_load_album(a["fixture"]) for a in spec.get("growing_albums", [])]
            pool = [load_photo(p["fixture"]) for p in spec.get("sedimented_pool", [])]
            result = run_full_l2(new_photos, albums, pool, scenario=scenario_path.stem)
            data = json.loads(result.model_dump_json())
            data.pop("arbitration_id", None)
            # 内部三路日志的 id 也清掉
            for key in ("growth_log", "l2_log", "backfill_log"):
                if isinstance(data.get(key), dict):
                    data[key].pop("decision_id", None)
        else:
            photos = load_photos([p["fixture"] for p in spec["photos"]])
            log = run_l2_path_b(photos, scenario=scenario_path.stem)
            data = json.loads(log.model_dump_json())
            data.pop("decision_id", None)
            if "final_decision" in data:
                data["final_decision"].pop("association_id", None)

        out_path = GOLDEN_DIR / f"{scenario_path.stem}.expected.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    regenerate(target)
