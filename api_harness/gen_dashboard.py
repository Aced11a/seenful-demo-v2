"""results/run_*.json → 自包含 HTML 看板。

参考: TEST_PLAN.md §7.4(输出物规格)/ SPEC.md §7。
设计要点:
- 按 path(L2 / L2.5 / cascade)分组渲染;每条 verdict 配色 + expected vs actual 并排。
- 头部统计条(verdict 计数 + match 率)。
- deferred 区单列:缺哪类信号 → 拿到后预期(本轮不发请求)。
- 自包含(CSS 内联,无外部依赖)→ 双击 _DASHBOARD.html 浏览即可。

跑法(项目根目录):
    python -m api_harness.gen_dashboard                  # 用 results/ 里最新的 run_*.json
    python -m api_harness.gen_dashboard <path-to-json>   # 指定具体 run 文件
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_RESULTS_DIR = _HERE / "results"
_DASHBOARD_PATH = _HERE / "_DASHBOARD.html"

# verdict 配色(语义):
_VERDICT_COLOR = {
    "match":      ("#16a34a", "通过"),
    "acceptable": ("#84cc16", "可接受"),
    "mismatch":   ("#dc2626", "偏差"),
    "unmapped":   ("#f97316", "码值待补"),
    "BLOCKED":    ("#6b7280", "前置阻塞"),
    "deferred":   ("#9ca3af", "本轮延后"),
    "error":      ("#991b1b", "执行错"),
}

_PATH_ORDER = ["L2", "L2.5", "cascade"]


def latest_run() -> Path:
    files = sorted(_RESULTS_DIR.glob("run_*.json"))
    if not files:
        raise FileNotFoundError(f"{_RESULTS_DIR} 下没有 run_*.json — 先跑 runner 再来出图。")
    return files[-1]


def render(results: list[dict], run_file: Path) -> str:
    by_path: dict[str, list[dict]] = OrderedDict((p, []) for p in _PATH_ORDER)
    for r in results:
        by_path.setdefault(r.get("path", "?"), []).append(r)

    counts: dict[str, int] = {}
    for r in results:
        v = r.get("verdict", "?")
        counts[v] = counts.get(v, 0) + 1
    total = len(results)
    n_match = counts.get("match", 0) + counts.get("acceptable", 0)
    rate = (n_match / total * 100) if total else 0.0

    parts: list[str] = []
    parts.append(_HEADER)
    parts.append(f"""
<header>
  <h1>api_harness · 后端 L2 API 测试看板</h1>
  <div class="meta">
    数据源: <code>{html.escape(str(run_file.relative_to(_HERE.parent)))}</code>
    · 生成: {datetime.now():%Y-%m-%d %H:%M:%S}
    · 共 <strong>{total}</strong> 条
    · 通过率 <strong>{rate:.1f}%</strong>(match+acceptable / total)
  </div>
  <div class="counts">{_render_counts(counts)}</div>
</header>
""")

    for path in by_path:
        rows = by_path[path]
        if not rows:
            continue
        parts.append(f'<section class="path-block"><h2>{html.escape(path)} <span class="n">({len(rows)} 条)</span></h2>')
        for r in rows:
            parts.append(_render_case(r))
        parts.append('</section>')

    parts.append(_RULES_FOOTER)
    parts.append('</body></html>')
    return "".join(parts)


def _render_counts(counts: dict[str, int]) -> str:
    pieces = []
    for v in ["match", "acceptable", "mismatch", "unmapped", "BLOCKED", "deferred", "error"]:
        if counts.get(v, 0) == 0:
            continue
        color, label = _VERDICT_COLOR[v]
        pieces.append(
            f'<span class="badge" style="background:{color};">'
            f'{html.escape(v)} <em>{counts[v]}</em></span>'
        )
    return " ".join(pieces) or '<em class="muted">(no cases)</em>'


def _render_tags(label: str, tags: list[dict]) -> str:
    """渲染一组照片的关键标签(ai_scene_tags / salient_objects / scene 等)。"""
    if not tags:
        return ""
    items = []
    for t in tags:
        parts = [f'<strong class="pid">{html.escape(str(t.get("id", "")))}</strong>']
        if t.get("ai_scene_tags"):
            tags_html = " ".join(f'<span class="t t-ai">{html.escape(str(x))}</span>' for x in t["ai_scene_tags"])
            parts.append(f'<span class="tag-group">ai_scene: {tags_html}</span>')
        if t.get("salient_objects"):
            objs_html = " ".join(f'<span class="t t-obj">{html.escape(str(x))}</span>' for x in t["salient_objects"])
            parts.append(f'<span class="tag-group">subj: {objs_html}</span>')
        meta_bits = []
        for k in ("scene", "activity", "event_hint"):
            v = t.get(k)
            if v and v not in ("unknown", "daily_record"):
                meta_bits.append(f'{k}=<em>{html.escape(str(v))}</em>')
        if t.get("sensitive", "none") != "none":
            meta_bits.append(f'<span class="sens">sensitive={html.escape(str(t["sensitive"]))}</span>')
        if t.get("anchors"):
            meta_bits.append(f'anchors=[{html.escape(", ".join(t["anchors"]))}]')
        if meta_bits:
            parts.append(f'<span class="tag-meta">{" · ".join(meta_bits)}</span>')
        if t.get("narrative"):
            parts.append(f'<span class="narr">「{html.escape(t["narrative"])}」</span>')
        items.append(f'<li>{" ".join(parts)}</li>')
    return f'<div class="tags-block"><div class="tags-label">{label}</div><ul class="tags">{"".join(items)}</ul></div>'


def _render_reasons(actual: dict) -> str:
    """渲染后端判断归因(decisionRemark / truthTablePattern / per-photo tier desc 等)。"""
    r = actual.get("reasons") or {}
    rows = []
    if r.get("top_decision"):
        rows.append(f'<div><span class="rl">顶层判断</span><code>{html.escape(str(r["top_decision"]))}</code></div>')
    if r.get("top_remark"):
        rows.append(f'<div><span class="rl">decisionRemark</span><code class="rmk">{html.escape(str(r["top_remark"]))}</code></div>')
    if r.get("per_photo_patterns"):
        codes = " ".join(f'<code class="pat">{html.escape(str(p))}</code>' for p in r["per_photo_patterns"])
        rows.append(f'<div><span class="rl">真值表 pattern</span>{codes}</div>')
    if r.get("per_photo_tier_descs"):
        rows.append(f'<div><span class="rl">每张决策档</span>' + " · ".join(f'<em>{html.escape(str(d))}</em>' for d in r["per_photo_tier_descs"]) + '</div>')
    if r.get("per_photo_final_descs"):
        rows.append(f'<div><span class="rl">每张最终结果</span>' + " · ".join(f'<em>{html.escape(str(d))}</em>' for d in r["per_photo_final_descs"]) + '</div>')
    if r.get("next_flow"):
        rows.append(f'<div><span class="rl">下一步流转</span><code>{html.escape(str(r["next_flow"]))}</code></div>')
    if not rows:
        return ""
    return f'<div class="reasons"><div class="reasons-h">🧠 后端为什么这么判</div>{"".join(rows)}</div>'


def _render_case(r: dict) -> str:
    v = r.get("verdict", "?")
    color, _ = _VERDICT_COLOR.get(v, ("#1f2937", "?"))
    expected = r.get("expected") or {}
    actual = r.get("actual") or {}
    missing = r.get("missing_themes") or []
    raw = r.get("raw") or {}
    biz_ids = raw.get("biz_ids") or []
    setup_albums = (raw.get("setup") or {}).get("albums") or []
    teardown_errs = raw.get("teardown_errors") or []
    trigger_tags = raw.get("trigger_tags") or []
    setup_tags = raw.get("setup_tags") or []
    pool_tags = raw.get("pool_tags") or []

    def _pair(label: str, exp: Any, act: Any) -> str:
        # 空字符串 / [] / None 在显示层都归 "—",避免 "—" vs "" 误标 diff
        exp_empty = exp in (None, "", [], {})
        act_empty = act in (None, "", [], {})
        ee = "—" if exp_empty else html.escape(str(exp))
        aa = "—" if act_empty else html.escape(str(act))
        # 期望无断言(—)就别标 diff(对照只有用户给了期望才有意义)
        same = "" if (exp_empty or exp == act) else " diff"
        return (f'<tr><th>{html.escape(label)}</th>'
                f'<td class="exp">{ee}</td>'
                f'<td class="act{same}">{aa}</td></tr>')

    rows: list[str] = []
    rows.append(_pair("display_decision / displayDecisionCode",
                      expected.get("display_decision"), actual.get("displayDecisionCode")))
    rows.append(_pair("decision_tier / decisionTierCode",
                      expected.get("decision_tier"), actual.get("decision_tier_codes")))
    rows.append(_pair("min_recalled / 召回数",
                      expected.get("min_recalled"), actual.get("photo_count")))
    rows.append(_pair("route(后端实际走的路径)", r.get("path"), actual.get("route")))
    rows.append(_pair("decisionRemark(真值表 pattern)", "—", actual.get("decisionRemark")))
    rows.append(_pair("miniAlbumId(s)", "—", actual.get("album_ids")))

    extra = []
    if setup_albums:
        extra.append(f'<div class="extra">📦 setup 已建集 miniAlbumId: <code>{html.escape(str(setup_albums))}</code></div>')
    if biz_ids:
        extra.append(f'<div class="extra muted">🧹 本场景 mockBizIds(teardown 删): <code>{html.escape(str(biz_ids))}</code></div>')
    if missing:
        extra.append(f'<div class="extra warn">⚠ 缺译 theme(待补翻译表): <code>{html.escape(", ".join(missing))}</code></div>')
    if teardown_errs:
        extra.append(f'<div class="extra warn">⚠ teardown 报错:{html.escape(" / ".join(teardown_errs))}</div>')

    # 输入侧标签:setup seed(L2.5)/ pool(cascade)在前,trigger 在后(对照"被比较的两边")
    inputs_html = ""
    if setup_tags:
        inputs_html += _render_tags("📦 setup seed(建老相册的种子)", setup_tags)
    if pool_tags:
        inputs_html += _render_tags("🏊 sediment pool(沉淀池候选)", pool_tags)
    if trigger_tags:
        inputs_html += _render_tags("🎯 trigger(本次触发上传)", trigger_tags)

    return f"""
<article class="case" style="--vc:{color};">
  <header class="case-h">
    <span class="verdict" style="background:{color};">{html.escape(v)}</span>
    <strong>{html.escape(r.get("case_id", "?"))}</strong>
  </header>
  <div class="detail">{html.escape(r.get("detail", ""))}</div>
  {inputs_html}
  {_render_reasons(actual)}
  <table class="pair"><thead><tr><th></th><th>期望(产品意图)</th><th>后端实际</th></tr></thead>
    <tbody>{"".join(rows)}</tbody></table>
  {"".join(extra)}
</article>
"""


_HEADER = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>api_harness · L2 API Dashboard</title>
<style>
  :root { --bg:#0f172a; --panel:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --line:#334155; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px; background: var(--bg); color: var(--text);
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         font-size: 14px; line-height: 1.55; }
  header > h1 { margin: 0 0 4px; font-size: 22px; }
  .meta { color: var(--muted); font-size: 12px; margin-bottom: 12px; }
  .meta code { background: var(--panel); padding: 1px 6px; border-radius: 3px; }
  .counts { margin: 8px 0 24px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 999px;
           color: white; font-weight: 600; font-size: 12px; margin-right: 6px; }
  .badge em { font-style: normal; background: rgba(0,0,0,.25); padding: 0 6px; border-radius: 4px; margin-left: 4px; }
  section.path-block { margin-bottom: 32px; }
  section h2 { font-size: 18px; margin: 0 0 12px; padding-bottom: 4px; border-bottom: 1px solid var(--line); }
  section h2 .n { color: var(--muted); font-size: 12px; font-weight: normal; }
  article.case { background: var(--panel); border-left: 4px solid var(--vc, #6b7280);
                 padding: 12px 16px; margin-bottom: 12px; border-radius: 6px; }
  .case-h { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
  .case-h .verdict { padding: 2px 8px; border-radius: 4px; color: white; font-size: 11px; font-weight: 700; letter-spacing: .5px; text-transform: uppercase; }
  .case-h strong { font-size: 15px; }
  .detail { color: var(--muted); font-size: 12px; margin-bottom: 8px; padding-left: 2px; }
  table.pair { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 12px; }
  table.pair th, table.pair td { padding: 4px 8px; text-align: left; vertical-align: top; }
  table.pair thead th { color: var(--muted); border-bottom: 1px solid var(--line); font-weight: 500; font-size: 11px; }
  table.pair tbody th { color: var(--muted); font-weight: 500; width: 30%; }
  table.pair td.exp { color: #cbd5e1; width: 32%; }
  table.pair td.act { color: #cbd5e1; width: 38%; }
  table.pair td.act.diff { color: #fbbf24; background: rgba(251, 191, 36, 0.08); }
  .extra { margin-top: 6px; font-size: 12px; }
  .extra code { background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 3px; font-size: 11px; }
  .extra.warn { color: #fbbf24; }
  .extra.muted { color: var(--muted); }
  /* 输入侧标签块 */
  .tags-block { margin: 8px 0; padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 4px; border-left: 2px solid rgba(255,255,255,0.15); }
  .tags-label { font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
  ul.tags { list-style: none; padding: 0; margin: 0; font-size: 12px; }
  ul.tags > li { padding: 3px 0; border-top: 1px solid rgba(255,255,255,0.04); display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
  ul.tags > li:first-child { border-top: none; }
  ul.tags .pid { color: #fbbf24; min-width: 40px; }
  ul.tags .tag-group { color: var(--muted); }
  ul.tags .t { display: inline-block; padding: 1px 6px; border-radius: 3px; margin: 0 1px; font-size: 11px; }
  ul.tags .t-ai { background: rgba(96, 165, 250, 0.18); color: #93c5fd; }   /* 蓝:主题 */
  ul.tags .t-obj { background: rgba(167, 139, 250, 0.18); color: #c4b5fd; } /* 紫:主体 */
  ul.tags .tag-meta { color: var(--muted); font-size: 11px; }
  ul.tags .tag-meta em { color: #cbd5e1; font-style: normal; }
  ul.tags .sens { color: #f87171; font-weight: 600; }
  ul.tags .narr { color: var(--muted); font-style: italic; font-size: 11px; }
  /* 后端归因块 */
  .reasons { margin: 8px 0; padding: 8px 12px; background: rgba(251, 191, 36, 0.06);
             border-left: 3px solid #f59e0b; border-radius: 4px; font-size: 12px; }
  .reasons-h { font-weight: 600; color: #fbbf24; margin-bottom: 4px; font-size: 12px; }
  .reasons > div { padding: 2px 0; }
  .reasons .rl { display: inline-block; min-width: 130px; color: var(--muted); font-size: 11px; }
  .reasons code { background: rgba(255,255,255,0.07); padding: 1px 6px; border-radius: 3px; font-size: 11px; }
  .reasons code.rmk { color: #fcd34d; }
  .reasons code.pat { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }   /* 真值表 pattern 红:醒目 */
  .reasons em { font-style: normal; color: #cbd5e1; }
  footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }
  footer p { margin: 4px 0; }
</style>
</head>
<body>"""


_RULES_FOOTER = """
<footer>
  <p><strong>读图规则</strong> · 期望按"产品意图应不应该成集"写(CLAUDE 第4条 / TEST_PLAN §7),不是猜后端怎么走。<code>mismatch</code> = 后端算法与产品意图的 gap,**不改 expected 去迎合后端**。</p>
  <p><code>unmapped</code> = code_map 还没填该期望词的后端码,补上 reference/code_map.json 后重跑会变 match/mismatch。<code>BLOCKED</code> = L2.5/cascade 前置 setup 没成集,不算 mismatch(可能是 seed/pool 选得不对或后端 setup 阶段就拒了)。<code>deferred</code> = ⛔ 场景本轮不发请求(缺 GPS/time 信号)。</p>
  <p>隔离: per-mockBizId 账本 teardown(SPEC §1/§3);后端整库 wipe 模式 pending Ace 与后端再确认。</p>
</footer>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_file", nargs="?", default=None, help="results/run_*.json 路径;省略=用最新")
    ap.add_argument("--out", default=str(_DASHBOARD_PATH), help="输出 HTML 路径")
    args = ap.parse_args()

    run_file = Path(args.run_file).resolve() if args.run_file else latest_run()
    results = json.loads(run_file.read_text(encoding="utf-8"))
    html_text = render(results, run_file)
    out_path = Path(args.out)
    out_path.write_text(html_text, encoding="utf-8")
    print(f"✓ 看板已生成: {out_path}  ({len(results)} 条, 数据源 {run_file.name})")
    print(f"  Windows 浏览:double-click  {out_path}")


if __name__ == "__main__":
    main()
