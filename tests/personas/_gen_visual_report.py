"""ADR-0020: 测试结果可视化报告生成器.

跑所有 persona scenarios, 收集每个 case 的:
  - 输入 photos + L1 字段
  - 7 维 bands (代码算)
  - 真值表 matched_pattern + bounds
  - LLM 完整输出 (semantic_reason / evidence / counter_evidence)
  - Policy Engine 最终决定
  - Invariants 校验结果

输出 markdown 报告 → 一眼看每个 case LLM 怎么判.

跑:
  python tests/personas/_gen_visual_report.py        # mock mode
  SEENFUL_LLM_MODE=real DASHSCOPE_API_KEY=sk-xxx python tests/personas/_gen_visual_report.py
"""
from __future__ import annotations

import os
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
from src.test_utils.invariants import check_invariants
from tests.personas import load_persona

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"
REPORT_PATH = ROOT / "tests" / "_VISUAL_REPORT.md"


def run_one_scenario(path: Path) -> dict:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    persona = load_persona(spec["persona"])
    test_path = spec["test_path"]
    result = {
        "file": path.stem,
        "name": spec.get("name", ""),
        "behavior_pattern": spec.get("behavior_pattern", "-"),
        "persona": spec["persona"],
        "test_path": test_path,
        "product_intent": spec.get("product_intent", ""),
        "input_photos": [],
        "log": None,
        "error": None,
    }

    try:
        if test_path == "L2":
            ids = spec["input"]["new_photos"]
            photos = persona.get_photos(ids)
            log = run_l2_path_b(photos, scenario=path.stem)
            result["input_photos"] = [(p.photo_id, p.theme_tags) for p in photos]
            result["log"] = log
        elif test_path == "L2.5":
            pid = spec["input"]["new_photo"]
            photo = persona.get_photo(pid)
            albums = [persona.get_album(a) for a in spec["input"].get("old_albums", [])]
            log = run_growth_path(photo, albums, scenario=path.stem)
            result["input_photos"] = [(photo.photo_id, photo.theme_tags)]
            result["log"] = log
        elif test_path == "cascade":
            pid = spec["input"]["new_photo"]
            photo = persona.get_photo(pid)
            pool = persona.get_photos(spec["input"].get("sediment_pool", []))
            log = cascade_backfill_single(photo, pool, scenario=path.stem)
            result["input_photos"] = [(photo.photo_id, photo.theme_tags)]
            result["log"] = log
    except Exception as e:
        result["error"] = str(e)

    return result


def fmt_one(r: dict) -> list[str]:
    lines = []
    lines.append(f"## {r['file']}")
    lines.append("")
    lines.append(f"**{r['name']}**")
    lines.append("")
    lines.append(f"- Pattern: `{r['behavior_pattern']}` · Path: `{r['test_path']}` · Persona: `{r['persona']}`")
    lines.append(f"- 产品意图: {r['product_intent']}")
    lines.append("")
    lines.append("### 输入照片")
    for pid, tags in r["input_photos"]:
        lines.append(f"- `{pid}`: {', '.join(tags)}")
    lines.append("")

    if r["error"]:
        lines.append(f"❌ **跑失败**: {r['error']}")
        lines.append("")
        return lines

    log = r["log"]
    if log is None:
        lines.append("(无 log)")
        return lines

    # 取决于 path 不同, log 结构不同
    if r["test_path"] == "L2":
        # DecisionLog
        bands = log.stages.get("step3_bands", {})
        tt = log.stages.get("step4_truth_table", {})
        llm = log.stages.get("step5_llm", {})
        final = log.final_decision
        assoc = final.association
        lines.append("### 算法行为")
        lines.append(f"- 7 维 bands: {bands}")
        lines.append(f"- 真值表: `{tt.get('matched_pattern')}` · bounds=[{tt.get('bounds_min')}, {tt.get('bounds_max')}]")
        if llm.get("skipped"):
            lines.append(f"- **LLM 跳过** (F1 兜底)")
        else:
            lines.append(f"- **LLM 输出**:")
            lines.append(f"  - proposed_strength: {llm.get('proposed_strength')}")
            lines.append(f"  - proposed_type: {llm.get('proposed_type')}")
            lines.append(f"  - semantic_reason: {llm.get('semantic_reason')}")
            ev = llm.get('evidence', [])
            if ev:
                lines.append(f"  - evidence ({len(ev)}):")
                for e in ev[:3]:
                    lines.append(f"    - `{e.get('photo_id')}`: {e.get('evidence')}")
            lines.append(f"  - counter_evidence: {llm.get('counter_evidence')}")
            lines.append(f"  - is_mock: {llm.get('is_mock')}")
        lines.append("")
        lines.append("### Policy Engine 最终")
        lines.append(f"- final_strength: **{assoc.strength}**")
        lines.append(f"- final_type: **{assoc.type}**")
        lines.append(f"- display_decision: **{assoc.display_decision}**")
        lines.append(f"- composite_score: {assoc.score:.3f}")
        lines.append(f"- policy_overrides: {len(log.policy_overrides)}")
    elif r["test_path"] == "L2.5":
        # GrowthDecisionLog
        final = log.final_decision
        lines.append("### 算法行为")
        lines.append(f"- 候选老相册: {log.candidate_album_ids}")
        lines.append(f"- per_album_evaluations: {len(log.per_album_evaluations)}")
        for e in log.per_album_evaluations:
            lines.append(f"  - album `{e.album_id}`: pattern=`{e.truth_table_match.matched_pattern}`, tier=`{e.decision_tier}`")
            if e.llm:
                lines.append(f"    - LLM accept={e.llm.accept}, reason: {e.llm.semantic_reason}")
        lines.append(f"- **最终 decision_tier**: `{final.decision_tier}`")
        lines.append(f"- target_album: {final.merge_target_album_id}")
    elif r["test_path"] == "cascade":
        # BackfillDecisionLog
        final = log.final_decision
        lines.append("### 算法行为")
        lines.append(f"- 粗筛后候选: {log.coarse_filter_candidates}")
        lines.append(f"- 维度排序选 top 4: {final.recalled_photo_ids}")
        lines.append(f"- 真值表: `{log.main_truth_table_match.matched_pattern if log.main_truth_table_match else 'N/A'}`")
        if log.llm_judgement:
            lines.append(f"- LLM: strength=`{log.llm_judgement.proposed_strength}`, reason: {log.llm_judgement.semantic_reason}")
        lines.append(f"- caps: {[(c.rule, c.passed) for c in log.backfill_caps_applied]}")
        lines.append(f"- **最终 decision_tier**: `{final.decision_tier}`")
    lines.append("")

    # invariants check
    spec_invs = yaml.safe_load(Path(SCENARIO_DIR / f"{r['file']}.yaml").read_text(encoding="utf-8")).get("invariants")
    violations = check_invariants(log, only=spec_invs)
    if violations:
        lines.append(f"### ❌ Invariant 违反 ({len(violations)})")
        for v in violations:
            lines.append(f"- {v}")
    else:
        lines.append(f"### ✅ Invariants 全过 ({', '.join(spec_invs) if spec_invs else 'all 8'})")
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def main():
    mode = os.environ.get("SEENFUL_LLM_MODE", "mock")
    print(f"Running visual report in {mode} mode...")

    paths = sorted(SCENARIO_DIR.glob("*.yaml"))
    results = [run_one_scenario(p) for p in paths]

    lines = []
    lines.append(f"# Persona Scenarios Visual Report ({mode} mode)")
    lines.append("")
    lines.append(f"- LLM mode: **{mode}** (env var `SEENFUL_LLM_MODE`)")
    lines.append(f"- 跑了 {len(results)} 个 scenarios")
    lines.append(f"- 跑命令: `SEENFUL_LLM_MODE=real DASHSCOPE_API_KEY=xxx python tests/personas/_gen_visual_report.py` 切真")
    lines.append("")
    lines.append("> 每个 case 含: 输入照片 + 7 维 bands + 真值表 + LLM 输出 + Policy 决定 + Invariants 校验")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 按 path 分组
    by_path: dict[str, list[dict]] = {"L2": [], "L2.5": [], "cascade": []}
    for r in results:
        by_path.setdefault(r["test_path"], []).append(r)

    for path_name, label in [("L2", "L2 (整批 path B)"), ("L2.5", "L2.5 (path A 生长)"), ("cascade", "Cascade (path C 回滚)")]:
        rs = by_path.get(path_name, [])
        if not rs:
            continue
        lines.append(f"# {label} · {len(rs)} 个 scenarios")
        lines.append("")
        for r in rs:
            lines.extend(fmt_one(r))

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {REPORT_PATH}")


if __name__ == "__main__":
    main()
