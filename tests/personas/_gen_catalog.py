"""ADR-0019 v0.2: Photo Catalog 自动生成器.

扫 3 个 persona yaml, 生成易读 markdown 索引表
回答你 #2 戳的: "编号找不到对应标签"
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml

PERSONA_DIR = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "tests" / "_PHOTO_CATALOG.md"


def gen():
    lines = []
    lines.append("# Persona Photo Catalog (auto-generated)")
    lines.append("")
    lines.append("> 跑 `python tests/personas/_gen_catalog.py` 重生")
    lines.append("> 每张照片 unique 标签, 同 group 内有内在共性 (语义簇可识别)")
    lines.append("")

    total = 0
    for pid in ["laoqi_zhang", "laoli_youke", "xiaowang"]:
        path = PERSONA_DIR / f"{pid}.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        identity = raw.get("identity", {})
        photos = raw.get("photos", [])
        groups = raw.get("groups", {})
        total += len(photos)

        lines.append(f"## {identity.get('name', pid)} (`{pid}`) · {len(photos)} 张")
        lines.append("")
        lines.append(f"- 年龄 {identity.get('age')} · {identity.get('city')} · {identity.get('life_stage')}")
        lines.append(f"- 偏好: {identity.get('photo_style_preference')}, content: {identity.get('content_topics')}")
        lines.append("")

        # 按 group 分组
        by_group: dict[str, list[dict]] = {}
        for p in photos:
            by_group.setdefault(p.get("group", "其他"), []).append(p)

        for gname, ps in by_group.items():
            g_meta = groups.get(gname, {})
            pattern = g_meta.get("behavior_pattern", "-")
            desc = g_meta.get("description", "")
            lines.append(f"### {gname} · {pattern} ({len(ps)} 张)")
            lines.append(f"_{desc}_")
            lines.append("")
            lines.append("| ID | 时间 | GPS | 主题 | event | tone | anchors | narrative |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for p in ps:
                ts = str(p.get("ts", "")).replace("T", " ")[:16]
                gps = p.get("gps", [])
                gps_str = f"[{gps[0]:.3f}, {gps[1]:.3f}]" if gps else "-"
                hf = " 🏠" if p.get("hf") else ""
                sensitive = " ⚠" if p.get("sensitive") else ""
                theme = ", ".join(p.get("theme", []))
                event = p.get("event", "-")
                tone = p.get("tone", "-")
                anchors = ", ".join(p.get("anchors", []))
                narrative = p.get("narrative", "")
                lines.append(f"| `{p['id']}` | {ts} | {gps_str}{hf}{sensitive} | {theme} | {event} | {tone} | {anchors} | {narrative} |")
            lines.append("")

        lines.append("")

    lines.insert(2, f"**总计: {total} 张照片 (跨 3 persona)**")
    lines.insert(3, "")

    CATALOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {CATALOG_PATH}  ({total} photos)")


if __name__ == "__main__":
    gen()
