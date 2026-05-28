"""results/run_*.json → 自包含 HTML 看板(白底黑字 / 大字号 / 折叠归因 / verdict 筛选)。

参考: TEST_PLAN.md §7.4 / SPEC.md §7。
Ace 2026-05-28 反馈版:
  - 配色:深色 → 白底黑字(对比度 + 易读)
  - 字号整体放大一档
  - 归因区 / 输入标签区改 `<details>`(点击展开,不再常驻挤压)
  - 头部加 verdict 筛选栏(可点开关 match / mismatch / unmapped 等;空 section 自动隐藏)
  - expected vs actual 表保留常显(核心对照,不折)

跑法(项目根目录):
    python -m api_harness.gen_dashboard                  # 用 results/ 里最新 run_*.json
    python -m api_harness.gen_dashboard <run.json>       # 指定文件
"""
from __future__ import annotations

import argparse
import html
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_RESULTS_DIR = _HERE / "results"
_DASHBOARD_PATH = _HERE / "_DASHBOARD.html"

# verdict 配色(白底语义色,深色调避免刺眼)
_VERDICT_COLOR = OrderedDict([
    ("match",      ("#15803d", "通过")),         # green-700
    ("acceptable", ("#65a30d", "可接受")),        # lime-600
    ("mismatch",   ("#b91c1c", "偏差")),          # red-700
    ("unmapped",   ("#c2410c", "码值待补")),       # orange-700
    ("BLOCKED",    ("#475569", "前置阻塞")),       # slate-600
    ("deferred",   ("#64748b", "本轮延后")),       # slate-500
    ("error",      ("#7f1d1d", "执行错")),         # red-900
])
_VERDICTS_ORDER = list(_VERDICT_COLOR.keys())
_PATH_ORDER = ["L2", "L2.5", "cascade"]


def latest_run() -> Path:
    files = sorted(_RESULTS_DIR.glob("run_*.json"))
    if not files:
        raise FileNotFoundError(f"{_RESULTS_DIR} 下没有 run_*.json — 先跑 runner 再来出图。")
    return files[-1]


# ── 渲染单元 ─────────────────────────────────────────────────────

def _render_filter_bar(counts: dict[str, int]) -> str:
    btns = ['<button class="filter all on" data-v="all">全部 <em>' + str(sum(counts.values())) + '</em></button>']
    for v in _VERDICTS_ORDER:
        n = counts.get(v, 0)
        if n == 0:
            continue
        color, _ = _VERDICT_COLOR[v]
        btns.append(
            f'<button class="filter on" data-v="{v}" style="--vc:{color};">'
            f'{html.escape(v)} <em>{n}</em></button>'
        )
    return f'<div class="filter-bar"><strong>筛选:</strong> {" ".join(btns)}</div>'


def _chip(category: str, value: str) -> str:
    """统一 chip 样式;category ∈ {ai, obj, scene, act, event, anchor, sens}。"""
    return f'<span class="t t-{category}">{html.escape(str(value))}</span>'


def _chip_group(label: str, category: str, values: list[str]) -> str:
    """一组带前缀 label 的 chip;values 为空则不渲染。"""
    if not values:
        return ""
    chips = " ".join(_chip(category, v) for v in values)
    return f'<span class="tag-group"><span class="tg-lbl">{label}</span>{chips}</span>'


def _render_tags_summary(label: str, tags: list[dict]) -> str:
    """折叠区里的标签详情。所有维度都用 chip 高亮(蓝主题 / 紫主体 / 绿场景 / 橙活动 / 粉事件 / 青锚点 / 红敏感)。"""
    if not tags:
        return ""
    items = []
    for t in tags:
        parts = [f'<strong class="pid">{html.escape(str(t.get("id", "")))}</strong>']
        parts.append(_chip_group("ai_scene", "ai", t.get("ai_scene_tags") or []))
        parts.append(_chip_group("subj", "obj", t.get("salient_objects") or []))
        # scene / activity / event_hint:单值,unknown / daily_record 不显
        scene = t.get("scene")
        if scene and scene != "unknown":
            parts.append(_chip_group("scene", "scene", [scene]))
        activity = t.get("activity")
        if activity and activity != "unknown":
            parts.append(_chip_group("activity", "act", [activity]))
        event = t.get("event_hint")
        if event and event != "daily_record":
            parts.append(_chip_group("event", "event", [event]))
        # anchors:多值,每个一片
        if t.get("anchors"):
            parts.append(_chip_group("anchors", "anchor", t["anchors"]))
        if t.get("sensitive", "none") != "none":
            parts.append(_chip_group("sensitive", "sens", [t["sensitive"]]))
        if t.get("narrative"):
            parts.append(f'<span class="narr">「{html.escape(t["narrative"])}」</span>')
        items.append(f'<li>{" ".join(p for p in parts if p)}</li>')
    summary_hint = f"{len(tags)} 张"
    # 摘出 ai_scene_tags 的前 3-4 个 token 作 summary 速览
    preview_tokens: list[str] = []
    for t in tags:
        for x in t.get("ai_scene_tags", []):
            if x not in preview_tokens:
                preview_tokens.append(x)
                if len(preview_tokens) >= 5:
                    break
        if len(preview_tokens) >= 5:
            break
    preview = "  ·  " + " / ".join(html.escape(x) for x in preview_tokens) if preview_tokens else ""
    return (f'<details class="fold tags-fold">'
            f'<summary>{label} <span class="count">{summary_hint}</span>'
            f'<span class="preview">{preview}</span></summary>'
            f'<ul class="tags">{"".join(items)}</ul></details>')


def _render_reasons(actual: dict) -> str:
    r = actual.get("reasons") or {}
    if not any(r.values()):
        return ""

    explained = r.get("patterns_explained") or []  # 每条:{pattern, trigger(人话), decision_tier}

    # summary 速览:pattern + 人话触发条件
    summary_bits: list[str] = []
    if explained:
        for e in explained:
            summary_bits.append(
                f'<code class="pat">{html.escape(e["pattern"])}</code>'
                f' <span class="pat-trigger">{html.escape(e["trigger"])}</span>'
                f' → <em>{html.escape(e["decision_tier"])}</em>'
            )
    elif r.get("per_photo_patterns"):
        for p in r["per_photo_patterns"]:
            summary_bits.append(f'<code class="pat">{html.escape(str(p))}</code>')
    elif r.get("top_remark"):
        summary_bits.append(f'<code class="rmk">{html.escape(str(r["top_remark"]))}</code>')
    summary_html = "  ".join(summary_bits) if summary_bits else "(点开查看)"

    rows = []
    if r.get("top_decision"):
        rows.append(f'<div><span class="rl">顶层判断</span><code>{html.escape(str(r["top_decision"]))}</code></div>')
    if r.get("top_remark"):
        rows.append(f'<div><span class="rl">decisionRemark</span><code class="rmk">{html.escape(str(r["top_remark"]))}</code></div>')
    if explained:
        for e in explained:
            rows.append(
                f'<div><span class="rl">真值表 pattern</span>'
                f'<code class="pat">{html.escape(e["pattern"])}</code> '
                f'<span class="pat-trigger">{html.escape(e["trigger"])}</span> '
                f'→ <em class="tier">{html.escape(e["decision_tier"])}</em></div>'
            )
    elif r.get("per_photo_patterns"):
        codes = " ".join(f'<code class="pat">{html.escape(str(p))}</code>' for p in r["per_photo_patterns"])
        rows.append(f'<div><span class="rl">真值表 pattern</span>{codes}</div>')
    if r.get("per_photo_tier_descs"):
        rows.append(f'<div><span class="rl">每张决策档</span>' + " · ".join(f'<em>{html.escape(str(d))}</em>' for d in r["per_photo_tier_descs"]) + '</div>')
    if r.get("per_photo_final_descs"):
        rows.append(f'<div><span class="rl">每张最终结果</span>' + " · ".join(f'<em>{html.escape(str(d))}</em>' for d in r["per_photo_final_descs"]) + '</div>')
    if r.get("next_flow"):
        rows.append(f'<div><span class="rl">下一步流转</span><code>{html.escape(str(r["next_flow"]))}</code></div>')

    return (f'<details class="fold reasons-fold">'
            f'<summary>🧠 后端为什么这么判 <span class="reason-summary">{summary_html}</span></summary>'
            f'<div class="reasons-body">{"".join(rows)}</div></details>')


def _render_case(r: dict, idx: int) -> str:
    """idx = 1-based 全局序号(跨 path 连续,便于沟通"#7 那条 mismatch")。"""
    v = r.get("verdict", "?")
    color, _ = _VERDICT_COLOR.get(v, ("#334155", "?"))
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
        exp_empty = exp in (None, "", [], {})
        act_empty = act in (None, "", [], {})
        ee = "—" if exp_empty else html.escape(str(exp))
        aa = "—" if act_empty else html.escape(str(act))
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
    rows.append(_pair("decisionRemark", None, actual.get("decisionRemark")))
    rows.append(_pair("miniAlbumId(s)", None, actual.get("album_ids")))

    extras: list[str] = []
    if setup_albums:
        extras.append(f'<div class="extra">📦 setup 已建集 miniAlbumId: <code>{html.escape(str(setup_albums))}</code></div>')
    if biz_ids:
        extras.append(f'<div class="extra muted">🧹 mockBizIds(teardown 已删): <code>{html.escape(str(biz_ids))}</code></div>')
    if missing:
        extras.append(f'<div class="extra warn">⚠ 缺译 theme: <code>{html.escape(", ".join(missing))}</code></div>')
    if teardown_errs:
        extras.append(f'<div class="extra warn">⚠ teardown 报错:{html.escape(" / ".join(teardown_errs))}</div>')

    inputs_html = ""
    if setup_tags:
        inputs_html += _render_tags_summary("📦 setup seed(建老相册的种子)", setup_tags)
    if pool_tags:
        inputs_html += _render_tags_summary("🏊 sediment pool(沉淀池候选)", pool_tags)
    if trigger_tags:
        inputs_html += _render_tags_summary("🎯 trigger(本次触发上传)", trigger_tags)

    return f"""
<article class="case" data-verdict="{html.escape(v)}" data-num="{idx}" style="--vc:{color};">
  <header class="case-h">
    <span class="case-num">#{idx:02d}</span>
    <span class="verdict" style="background:{color};">{html.escape(v)}</span>
    <strong class="cid">{html.escape(r.get("case_id", "?"))}</strong>
  </header>
  <div class="detail">{html.escape(r.get("detail", ""))}</div>
  <table class="pair"><thead><tr><th class="pair-lbl">字段</th><th>期望(产品意图)</th><th>后端实际</th></tr></thead>
    <tbody>{"".join(rows)}</tbody></table>
  {inputs_html}
  {_render_reasons(actual)}
  {"".join(extras)}
</article>
"""


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

    parts: list[str] = [_HEADER]
    parts.append(f"""
<header class="page-h">
  <h1>api_harness · 后端 L2 API 测试看板</h1>
  <div class="meta">
    数据源: <code>{html.escape(str(run_file.relative_to(_HERE.parent) if _HERE.parent in run_file.parents else run_file.name))}</code>
    · 生成 {datetime.now():%Y-%m-%d %H:%M:%S}
    · 共 <strong>{total}</strong> 条
    · 通过率 <strong>{rate:.1f}%</strong>
  </div>
  {_render_filter_bar(counts)}
</header>
""")

    n = 0
    for path in by_path:
        rows = by_path[path]
        if not rows:
            continue
        parts.append(f'<section class="path-block" data-path="{html.escape(path)}"><h2>{html.escape(path)} <span class="n">({len(rows)} 条)</span></h2>')
        for r in rows:
            n += 1
            parts.append(_render_case(r, n))
        parts.append('</section>')

    parts.append(_FOOTER)
    parts.append(_JS)
    parts.append('</body></html>')
    return "".join(parts)


# ── HTML 头/尾/CSS/JS ──────────────────────────────────────────

_HEADER = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>api_harness · L2 API Dashboard</title>
<style>
  :root {
    --bg: #f8fafc; --paper: #ffffff; --text: #0f172a; --muted: #64748b;
    --line: #e2e8f0; --soft: #f1f5f9; --warn-bg: #fef3c7; --warn-border: #f59e0b;
    --ai-bg: #dbeafe;    --ai-fg: #1e40af;     /* 蓝:ai_scene_tags 主题 */
    --obj-bg: #ede9fe;   --obj-fg: #5b21b6;    /* 紫:salient_objects 主体 */
    --scene-bg: #d1fae5; --scene-fg: #065f46;  /* 绿:scene 场景 */
    --act-bg: #ffedd5;   --act-fg: #9a3412;    /* 橙:activity 活动 */
    --event-bg: #fce7f3; --event-fg: #9d174d;  /* 粉:event_hint 事件 */
    --anchor-bg: #ccfbf1; --anchor-fg: #115e59; /* 青:meaning_anchors 锚点 */
    --sens-bg: #fee2e2;  --sens-fg: #991b1b;   /* 红:sensitive 敏感 */
    --pat-bg: #fee2e2;   --pat-fg: #991b1b;
    --rmk-bg: #fef3c7;   --rmk-fg: #92400e;
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 28px 36px; background: var(--bg); color: var(--text);
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         font-size: 16px; line-height: 1.6; }

  /* 页头 */
  header.page-h h1 { margin: 0 0 6px; font-size: 30px; color: #0f172a; }
  .meta { color: var(--muted); font-size: 14px; margin-bottom: 16px; }
  .meta code { background: var(--soft); padding: 2px 8px; border-radius: 4px; font-size: 13px; color: #334155; }
  .meta strong { color: #0f172a; }

  /* 筛选栏 */
  .filter-bar { padding: 10px 14px; background: var(--paper); border: 1px solid var(--line);
                border-radius: 8px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
                margin-bottom: 24px; font-size: 14px; }
  .filter-bar strong { color: var(--muted); font-weight: 500; margin-right: 4px; }
  .filter { padding: 6px 14px; border: 1.5px solid var(--line); background: var(--paper);
            border-radius: 999px; cursor: pointer; font-size: 14px; font-weight: 500;
            color: var(--muted); transition: all .15s; }
  .filter em { font-style: normal; background: var(--soft); color: #64748b; padding: 1px 7px;
               border-radius: 999px; font-size: 12px; margin-left: 4px; }
  .filter:hover { border-color: var(--vc, #94a3b8); }
  .filter.on { background: var(--vc, #475569); color: white; border-color: var(--vc, #475569); }
  .filter.on em { background: rgba(255,255,255,.25); color: white; }
  .filter.all.on { background: #1e293b; border-color: #1e293b; }

  /* 路径分组 */
  section.path-block { margin-bottom: 28px; }
  section h2 { font-size: 22px; margin: 0 0 14px; padding-bottom: 6px;
               border-bottom: 2px solid var(--line); color: #0f172a; }
  section h2 .n { color: var(--muted); font-size: 14px; font-weight: normal; margin-left: 6px; }

  /* 单条 case */
  article.case { background: var(--paper); border-left: 5px solid var(--vc, #94a3b8);
                 border-top: 1px solid var(--line); border-right: 1px solid var(--line); border-bottom: 1px solid var(--line);
                 padding: 14px 18px; margin-bottom: 14px; border-radius: 6px;
                 box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
  .case-h { display: flex; gap: 12px; align-items: center; margin-bottom: 6px; }
  .case-h .case-num { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 20px;
                      font-weight: 700; color: #94a3b8; min-width: 48px;
                      background: var(--soft); padding: 2px 10px; border-radius: 6px;
                      letter-spacing: -0.5px; }
  .case-h .verdict { padding: 3px 10px; border-radius: 4px; color: white; font-size: 12px;
                     font-weight: 700; letter-spacing: .5px; text-transform: uppercase; }
  .case-h .cid { font-size: 17px; color: #0f172a; }
  .detail { color: #334155; font-size: 14px; margin-bottom: 10px; }

  /* expected vs actual 表(常显) */
  table.pair { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 14px; }
  table.pair th, table.pair td { padding: 6px 10px; text-align: left; vertical-align: top; }
  table.pair thead th { color: var(--muted); border-bottom: 1px solid var(--line);
                        font-weight: 600; font-size: 13px; background: var(--soft); }
  table.pair tbody th { color: var(--muted); font-weight: 500; width: 30%;
                        border-bottom: 1px solid var(--soft); }
  table.pair td.exp { color: #334155; width: 32%; border-bottom: 1px solid var(--soft); }
  table.pair td.act { color: #334155; width: 38%; border-bottom: 1px solid var(--soft); }
  table.pair td.act.diff { color: #92400e; background: var(--rmk-bg); font-weight: 500; }

  /* 折叠区(标签 + 归因) */
  details.fold { margin-top: 10px; border: 1px solid var(--line); border-radius: 6px;
                 background: var(--paper); }
  details.fold > summary { padding: 8px 14px; cursor: pointer; font-size: 14px;
                           font-weight: 500; color: #0f172a; user-select: none;
                           list-style: none; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
  details.fold > summary::before { content: "▶"; color: var(--muted); font-size: 10px; margin-right: 6px;
                                    transition: transform .15s; }
  details.fold[open] > summary::before { transform: rotate(90deg); }
  details.fold > summary:hover { background: var(--soft); }
  details.fold[open] > summary { border-bottom: 1px solid var(--line); background: var(--soft); }
  details.fold .count { color: var(--muted); font-size: 12px; font-weight: 400; }
  details.fold .preview { color: var(--muted); font-size: 13px; font-weight: 400; }

  /* 输入标签 */
  ul.tags { list-style: none; padding: 8px 14px 12px; margin: 0; font-size: 14px; }
  ul.tags > li { padding: 6px 0; border-top: 1px solid var(--soft);
                 display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; }
  ul.tags > li:first-child { border-top: none; padding-top: 8px; }
  ul.tags .pid { color: #b45309; min-width: 48px; font-size: 14px; font-weight: 700; }
  ul.tags .tag-group { color: var(--muted); }
  ul.tags .tag-group .tg-lbl { color: var(--muted); font-size: 12px; margin-right: 4px; }
  ul.tags .t { display: inline-block; padding: 2px 8px; border-radius: 4px;
               margin: 0 2px 0 0; font-size: 13px; font-weight: 500; }
  ul.tags .t-ai      { background: var(--ai-bg);     color: var(--ai-fg); }
  ul.tags .t-obj     { background: var(--obj-bg);    color: var(--obj-fg); }
  ul.tags .t-scene   { background: var(--scene-bg);  color: var(--scene-fg); }
  ul.tags .t-act     { background: var(--act-bg);    color: var(--act-fg); }
  ul.tags .t-event   { background: var(--event-bg);  color: var(--event-fg); }
  ul.tags .t-anchor  { background: var(--anchor-bg); color: var(--anchor-fg); }
  ul.tags .t-sens    { background: var(--sens-bg);   color: var(--sens-fg); font-weight: 700; }
  ul.tags .narr { color: #475569; font-style: italic; font-size: 13px; }

  /* 后端归因区(折叠后内容) */
  details.reasons-fold > summary { background: var(--warn-bg); border-radius: 6px; }
  details.reasons-fold[open] > summary { border-radius: 6px 6px 0 0; border-bottom: 1px solid var(--warn-border); }
  details.reasons-fold .reason-summary { color: #475569; font-size: 13px; }
  details.reasons-fold .reason-summary code.pat { background: var(--pat-bg); color: var(--pat-fg);
                                                   padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 13px; }
  details.reasons-fold .reason-summary code.rmk { background: var(--rmk-bg); color: var(--rmk-fg);
                                                   padding: 2px 8px; border-radius: 4px; font-size: 13px; }
  details.reasons-fold .reason-summary em { color: #334155; font-style: normal; font-weight: 600; }
  /* pattern 人话(从 truth_table.json 注入)*/
  .pat-trigger { color: #334155; font-size: 13px; font-style: italic; }
  .reasons-body em.tier { font-weight: 700; color: #1e293b; }
  .reasons-body { padding: 10px 14px; }
  .reasons-body > div { padding: 4px 0; font-size: 14px; }
  .reasons-body .rl { display: inline-block; min-width: 140px; color: var(--muted); font-size: 13px; }
  .reasons-body code { background: var(--soft); padding: 2px 8px; border-radius: 4px; font-size: 13px; color: #334155; }
  .reasons-body code.rmk { background: var(--rmk-bg); color: var(--rmk-fg); font-weight: 500; }
  .reasons-body code.pat { background: var(--pat-bg); color: var(--pat-fg); font-weight: 600; }
  .reasons-body em { color: #334155; font-style: normal; }

  /* 额外信息(底栏小字)*/
  .extra { margin-top: 8px; font-size: 13px; color: #475569; }
  .extra code { background: var(--soft); padding: 2px 7px; border-radius: 4px; font-size: 12px; color: #334155; }
  .extra.warn { color: #b45309; }
  .extra.muted { color: var(--muted); }

  /* 页脚 */
  footer.page-f { margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--line);
                  color: var(--muted); font-size: 13px; }
  footer.page-f p { margin: 6px 0; }
  footer.page-f code { background: var(--soft); padding: 1px 6px; border-radius: 3px; color: #334155; font-size: 12px; }
  footer.page-f strong { color: #0f172a; }
</style>
</head>
<body>"""


_FOOTER = """
<footer class="page-f">
  <p><strong>读图规则</strong> · 期望按"产品意图应不应该成集"写(CLAUDE 第4条 / TEST_PLAN §7),不是猜后端怎么走。<code>mismatch</code> = 后端算法与产品意图的 gap,**不改 expected 去迎合后端**。</p>
  <p><code>unmapped</code> = code_map 还没填该期望词的后端码,补 <code>reference/code_map.json</code> 后重跑会变 match/mismatch。<code>BLOCKED</code> = L2.5/cascade 前置 setup 没成集(可能 seed/pool 选得不对或后端 setup 阶段就拒了)。<code>deferred</code> = ⛔ 场景本轮不发请求(缺 GPS/time 信号)。</p>
  <p>隔离: per-mockBizId 账本 teardown(SPEC §1/§3);后端整库 wipe 模式 pending Ace 与后端再确认。</p>
</footer>"""


_JS = """
<script>
(function () {
  const VERDICTS = ["match","acceptable","mismatch","unmapped","BLOCKED","deferred","error"];
  let active = new Set(VERDICTS);
  function apply() {
    document.querySelectorAll("article.case").forEach(el => {
      el.style.display = active.has(el.dataset.verdict) ? "" : "none";
    });
    document.querySelectorAll("section.path-block").forEach(sec => {
      const visible = Array.from(sec.querySelectorAll("article.case"))
                           .filter(c => c.style.display !== "none").length;
      sec.style.display = visible ? "" : "none";
    });
    document.querySelectorAll(".filter[data-v]").forEach(b => {
      const v = b.dataset.v;
      if (v === "all") {
        b.classList.toggle("on", active.size === VERDICTS.length);
      } else {
        b.classList.toggle("on", active.has(v));
      }
    });
  }
  document.querySelectorAll(".filter[data-v]").forEach(b => {
    b.addEventListener("click", () => {
      const v = b.dataset.v;
      if (v === "all") {
        active = (active.size === VERDICTS.length) ? new Set() : new Set(VERDICTS);
      } else {
        if (active.has(v)) active.delete(v); else active.add(v);
      }
      apply();
    });
  });
})();
</script>"""


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
