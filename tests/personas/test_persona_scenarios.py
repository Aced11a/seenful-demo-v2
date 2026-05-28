"""Persona-based E2E scenarios runner (ADR-0019).

参考: docs/25_persona_e2e_testing.md

读 tests/personas/scenarios/*.yaml, 按 test_path 跑 L2 / L2.5 / cascade.
默认跑 8 条产品红线 invariants 校验.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.pipeline import (
    cascade_backfill_single,
    run_growth_path,
    run_l2_path_b,
)
from src.test_utils.invariants import check_invariants
from tests.personas import load_persona

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def discover_persona_scenarios() -> list[Path]:
    if not SCENARIO_DIR.exists():
        return []
    return sorted(SCENARIO_DIR.glob("*.yaml"))


@pytest.mark.persona
@pytest.mark.parametrize(
    "scenario_path",
    discover_persona_scenarios(),
    ids=lambda p: p.stem,
)
def test_persona_scenario(scenario_path: Path):
    spec = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    persona = load_persona(spec["persona"])
    path = spec["test_path"]

    if path == "L2":
        _run_l2(spec, persona, scenario_path.stem)
    elif path == "L2.5":
        _run_l25(spec, persona, scenario_path.stem)
    elif path == "cascade":
        _run_cascade(spec, persona, scenario_path.stem)
    elif path == "full_l2":
        pytest.skip("ADR-0020 待落地多路径 e2e")
    else:
        raise ValueError(f"unknown test_path: {path}")


def _run_l2(spec, persona, scenario_name):
    photo_ids = spec["input"]["new_photos"]
    photos = persona.get_photos(photo_ids)
    log = run_l2_path_b(photos, scenario=scenario_name)

    exp = spec["expected"]
    fd = log.final_decision
    assoc = fd.association

    def _check(name, actual, expected):
        allowed = expected if isinstance(expected, list) else [expected]
        assert actual in allowed, (
            f"{scenario_name}: {name} got {actual} expected in {allowed}"
        )

    if "display_decision" in exp:
        _check("display_decision", assoc.display_decision, exp["display_decision"])
    if "matched_pattern" in exp:
        got = log.stages["step4_truth_table"]["matched_pattern"]
        _check("matched_pattern", got, exp["matched_pattern"])
    if "final_strength" in exp:
        _check("final_strength", assoc.strength, exp["final_strength"])
    if "bands" in exp:
        bands_snap = log.stages["step3_bands"]
        for dim, expected_band in exp["bands"].items():
            actual = bands_snap.get(dim)
            assert actual == expected_band, (
                f"{scenario_name}: band {dim} got {actual} expected {expected_band}"
            )

    _check_invariants(log, spec, scenario_name)


def _run_l25(spec, persona, scenario_name):
    new_photo = persona.get_photo(spec["input"]["new_photo"])
    album_names = spec["input"].get("old_albums", [])
    albums = [persona.get_album(a) for a in album_names]

    log = run_growth_path(new_photo, albums, scenario=scenario_name)
    exp = spec["expected"]
    fd = log.final_decision

    if "decision_tier" in exp:
        allowed = exp["decision_tier"] if isinstance(exp["decision_tier"], list) else [exp["decision_tier"]]
        assert fd.decision_tier in allowed, (
            f"{scenario_name}: decision_tier got {fd.decision_tier} expected in {allowed}"
        )
    if "target_album_id" in exp:
        expected_album = exp["target_album_id"]
        if expected_album is None:
            assert fd.merge_target_album_id is None, (
                f"{scenario_name}: target got {fd.merge_target_album_id} expected None"
            )
        else:
            if not expected_album.startswith("ma_"):
                expected_album = f"ma_{expected_album}"
            assert fd.merge_target_album_id == expected_album, (
                f"{scenario_name}: target got {fd.merge_target_album_id} expected {expected_album}"
            )
    if "matched_pattern" in exp:
        patterns = [e.truth_table_match.matched_pattern for e in log.per_album_evaluations]
        assert exp["matched_pattern"] in patterns, (
            f"{scenario_name}: matched_pattern {exp['matched_pattern']} not in {patterns}"
        )

    _check_invariants(log, spec, scenario_name)


def _run_cascade(spec, persona, scenario_name):
    new_photo = persona.get_photo(spec["input"]["new_photo"])
    pool_ids = spec["input"].get("sediment_pool", [])
    pool = persona.get_photos(pool_ids)

    log = cascade_backfill_single(new_photo, pool, scenario=scenario_name)
    exp = spec["expected"]
    fd = log.final_decision

    if "decision_tier" in exp:
        allowed = exp["decision_tier"] if isinstance(exp["decision_tier"], list) else [exp["decision_tier"]]
        assert fd.decision_tier in allowed, (
            f"{scenario_name}: decision_tier got {fd.decision_tier} expected in {allowed}"
        )
    if "min_recalled" in exp:
        assert len(fd.recalled_photo_ids) >= exp["min_recalled"]
    if "max_recalled" in exp:
        assert len(fd.recalled_photo_ids) <= exp["max_recalled"]

    _check_invariants(log, spec, scenario_name)


def _check_invariants(log, spec, scenario_name):
    """默认全跑 8 条 invariants; spec 可指定 invariants 列表只跑某几条."""
    only = spec.get("invariants")
    violations = check_invariants(log, only=only)
    assert not violations, f"{scenario_name} invariants:\n  " + "\n  ".join(violations)
