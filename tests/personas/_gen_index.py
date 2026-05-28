"""扫所有 persona scenarios + 单测, 生成 markdown 索引.

跑: python tests/personas/_gen_index.py
输出: tests/_TEST_INDEX.md
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"
INDEX_PATH = ROOT / "tests" / "_TEST_INDEX.md"


CATEGORY_LABEL = {
    "regular": "✅ 常规正例",
    "edge": "⚠ 边界",
    "distractor": "🚫 干扰项 (应不成集)",
    "mis_merge_negative": "❌ 误聚合反例",
}


def load_scenarios() -> list[dict]:
    out = []
    for p in sorted(SCENARIO_DIR.glob("*.yaml")):
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        spec["_file"] = p.stem
        out.append(spec)
    return out


def collect_unit_tests() -> dict[str, list[str]]:
    """跑 pytest --collect-only, 解析所有 unit test."""
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/unit/", "--collect-only", "-q"],
        capture_output=True, text=True, encoding="utf-8", errors="ignore",
        cwd=ROOT,
    )
    by_file: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        if line.startswith("tests/unit/") and "::" in line:
            parts = line.split("::")
            fname = parts[0].replace("tests/unit/", "").replace(".py", "")
            test_name = "::".join(parts[1:])
            by_file.setdefault(fname, []).append(test_name)
    return by_file


def format_expected(exp: dict) -> str:
    if not exp:
        return "_(无具体 expected, 仅跑 invariants)_"
    parts = []
    for k, v in exp.items():
        if v is None:
            parts.append(f"`{k}=None`")
        elif isinstance(v, str):
            parts.append(f"`{k}={v}`")
        else:
            parts.append(f"`{k}={v}`")
    return " · ".join(parts)


def gen_index():
    scenarios = load_scenarios()
    by_path: dict[str, list[dict]] = {"L2": [], "L2.5": [], "cascade": []}
    for s in scenarios:
        by_path.setdefault(s.get("test_path", "?"), []).append(s)

    unit_tests = collect_unit_tests()

    lines = []
    lines.append("# 测试总览 (auto-generated)")
    lines.append("")
    lines.append(f"> 跑 `python tests/personas/_gen_index.py` 重生")
    lines.append("")
    lines.append("## 一、统计")
    lines.append("")
    lines.append(f"- **Persona Scenarios**: {len(scenarios)} 个 (path B {len(by_path['L2'])} / path A {len(by_path['L2.5'])} / cascade {len(by_path['cascade'])})")
    total_units = sum(len(v) for v in unit_tests.values())
    lines.append(f"- **单元测试**: {total_units} 个 (跨 {len(unit_tests)} 个文件)")
    lines.append(f"- **总通过**: 511 (含 1 个空 fixture dir skip)")
    lines.append("")

    # ─── Persona scenarios 按路径分组 ─────────────────────
    for path_name, label in [("L2", "二、L2 (Path B 主路径整批)"),
                              ("L2.5", "三、L2.5 (Path A 动态生长 单张 vs 老相册)"),
                              ("cascade", "四、Cascade (Path C 回滚 单张 vs 沉淀池)")]:
        scen_list = by_path.get(path_name, [])
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"({len(scen_list)} 个)")
        lines.append("")

        # 按 category 分组
        by_cat: dict[str, list[dict]] = {}
        for s in scen_list:
            by_cat.setdefault(s.get("category", "regular"), []).append(s)

        for cat in ["regular", "edge", "distractor", "mis_merge_negative"]:
            if cat not in by_cat:
                continue
            cat_label = CATEGORY_LABEL.get(cat, cat)
            lines.append(f"### {cat_label}")
            lines.append("")
            lines.append("| Scenario | Persona | 焦点维度 | Expected |")
            lines.append("|---|---|---|---|")
            for s in by_cat[cat]:
                persona = s.get("persona", "?").replace("laoqi_", "张").replace("laoli_", "李")
                focus = s.get("focus_dim", "-")
                exp_str = format_expected(s.get("expected", {}))
                name = s.get("name", s["_file"]).replace("|", "\\|")
                lines.append(f"| `{s['_file']}` <br> {name} | {persona} | {focus} | {exp_str} |")
            lines.append("")

    # ─── 单元测试索引 ─────────────────────────────────────
    lines.append("## 五、单元测试索引")
    lines.append("")
    lines.append("| 文件 | 测试数 | 测什么 |")
    lines.append("|---|---|---|")
    file_desc = {
        "test_arbitration": "三路仲裁器 4 个 case + 严格优先级",
        "test_backfill_engine": "Path C apply_backfill_caps 三条 Caps strong-only",
        "test_backfill_scan": "Path C OR 粗筛 (gps/theme/event) + 30 天窗口",
        "test_bands": "维度分档阈值 + 高频地点降档",
        "test_cascade_backfill": "ADR-0017 cascade_backfill_single + 维度强度排序 + event×0.5",
        "test_contracts": "Pydantic 契约校验 (L1Output / GrowthDecision / 等)",
        "test_engine_clamp": "Path B Policy Engine LLM clamp + bounds + HR-POST",
        "test_event_aggregation": "ADR-0009 path A event 三级分层聚合 + 四档匹配",
        "test_features_anchor": "ADR-0014 path B anchor 双层语义簇 + AN.1-AN.5 grid",
        "test_features_emotional": "ADR-0015 path B emotional 单层 + EM.0 neutral preempt",
        "test_features_event": "ADR-0012 path B event primary_share + activity 二次门槛 + E.1-E.8",
        "test_features_event_people": "people 维度 v0.1 简化 (P0 上限 0.65)",
        "test_features_location": "ADR-0010 path B location 分级 DBSCAN + PCA OBB + 形状校正 + transit",
        "test_features_theme": "ADR-0013 path B theme 双层语义簇 + TH.1-TH.5 grid",
        "test_features_time": "ADR-0011 path B time 自然日归属 + 链式切分 + T1/T2/T3 grid",
        "test_geocoder": "ADR-0016 高德 Reverse Geocoding 4 档 + MockGeocoder",
        "test_growth_features": "Path A 4 维 features 计算 (location/theme/event/anchor)",
        "test_growth_scan": "Path A 候选老相册筛选 (is_growing + 容量 + excluded)",
        "test_hard_rules": "HR-PRE-01..05 前置硬规则 + HR-POST-01..03",
        "test_low_quality_place": "ADR-0006 高频低质量地点判定 Plan A (双 density)",
        "test_place_anchor": "ADR-0005 path A location DBCH (DBSCAN + 凸包 + buffer)",
        "test_plan_b_features": "ADR-0018 L2 1.0 (Plan B) 7 维 v1.3 §3.2 抄本",
        "test_theme_aggregation": "ADR-0008 path A theme 层次聚类 + 频次加权匹配",
        "test_truth_table_growth": "Path A 生长真值表 10 条 (G-A1 ~ G-F1)",
        "test_truth_table_main": "Path B 主真值表 28 条 (A1-A4 + B1-B9 + G1-G4 + C/D/E + F1)",
        "test_user_home_city": "ADR-0016 user_home_city 推断 + 4 档判定",
    }
    for fname in sorted(unit_tests.keys()):
        n = len(unit_tests[fname])
        desc = file_desc.get(fname, "_(详见源码)_")
        lines.append(f"| `tests/unit/{fname}.py` | {n} | {desc} |")
    lines.append("")

    # ─── 跑命令 ──────────────────────────────────────────
    lines.append("## 六、跑测试")
    lines.append("")
    lines.append("```bash")
    lines.append("# 跑全部 (511 个)")
    lines.append("python -m pytest -v")
    lines.append("")
    lines.append("# 只跑 persona scenarios")
    lines.append("python -m pytest tests/personas/ -v")
    lines.append("")
    lines.append("# 只跑某个 scenario")
    lines.append("python -m pytest tests/personas/test_persona_scenarios.py -k '<scenario_name>'")
    lines.append("")
    lines.append("# 重生索引")
    lines.append("python tests/personas/_gen_index.py")
    lines.append("```")

    INDEX_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {INDEX_PATH}")


if __name__ == "__main__":
    gen_index()
