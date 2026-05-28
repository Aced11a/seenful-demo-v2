"""场景 runner:串行,每场景维护 mockBizId 账本 + teardown 按 id 级联删除。

参考: SPEC.md §3(隔离 session loop)/ §6(比对层级)/ TEST_PLAN.md §7(执行方案、verdict 分类)。

⚠ 隔离模型存疑(2026-05-28):Ace 转达后端同事说 del = 整库清空,但实测 del(其他id) 不动 X、
   del(X) 才删 X → 实际是 per-mockBizId 级联(删该提交的所有照片+小集)。Ace 回头与后端再核实,
   pending 期间 runner 用 per-id 账本 teardown(两种解释下都正确,SPEC/CLAUDE doc 待最终确认后回改)。

跑法(项目根目录):
    python -m api_harness.runner                      # 跑 cases/ 下全部
    python -m api_harness.runner --filter D2          # 只跑路径含 'D2' 的 case
    python -m api_harness.runner --filter L2/          # 只跑 L2 组
    python -m api_harness.runner --keep                # 不 teardown(联调用,留库便于检查)

verdict: match | acceptable | mismatch | BLOCKED | deferred | error | unmapped
  unmapped = 期望词在 code_map 里还没有对应后端码 → 待补映射(非后端 bug,TEST_PLAN §7.3)。
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

#: 防御性脱敏:requests 的 SSLError 等异常 str 会带完整 URL(含 sign 等 query 鉴权值)。
#: 落盘前一律 mask。CLAUDE 第3条:鉴权值绝不进任何受版控文件,results/ 也已 gitignore,
#: 双层保险。pattern 覆盖 sign / token / signature / *_key 等常见鉴权 query 名。
_SECRET_QUERY_RE = re.compile(r"((?:sign|signature|token|api[_-]?key|secret)=)[^&\s'\"]+", re.IGNORECASE)


def _scrub(s: str) -> str:
    return _SECRET_QUERY_RE.sub(r"\1***", s)

from api_harness import adapter, client

_HERE = Path(__file__).resolve().parent
_CASES_DIR = _HERE / "cases"
_RESULTS_DIR = _HERE / "results"
_CODE_MAP_PATH = _HERE / "reference" / "code_map.json"


@dataclass
class CaseResult:
    case_id: str
    path: str
    verdict: str
    detail: str
    expected: dict[str, Any]
    actual: dict[str, Any] = field(default_factory=dict)
    missing_themes: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id, "path": self.path, "verdict": self.verdict,
            "detail": self.detail, "expected": self.expected, "actual": self.actual,
            "missing_themes": self.missing_themes, "raw": self.raw,
        }


def load_code_map() -> dict[str, Any]:
    return json.loads(_CODE_MAP_PATH.read_text(encoding="utf-8"))


def load_cases(filter_substr: str | None = None) -> list[dict]:
    cases = []
    for p in sorted(_CASES_DIR.rglob("*.yaml")):
        rel = p.relative_to(_CASES_DIR).as_posix()
        if filter_substr and filter_substr not in rel and filter_substr not in p.name:
            continue
        c = yaml.safe_load(p.read_text(encoding="utf-8"))
        c["_file"] = rel
        cases.append(c)
    return cases


# ── 提取后端关键字段 ───────────────────────────────────────────────

def _extract_actual(body: dict[str, Any]) -> dict[str, Any]:
    photos = body.get("photos") or []
    album_ids = sorted({p.get("miniAlbumId") for p in photos if p.get("miniAlbumId")})
    return {
        "status": body.get("status"),
        "route": body.get("route"),
        "displayDecisionCode": body.get("displayDecisionCode"),
        "displayDecisionDesc": body.get("displayDecisionDesc"),
        "nextFlowCode": body.get("nextFlowCode"),
        "decisionRemark": body.get("decisionRemark"),
        "album_ids": album_ids,
        "photo_count": len(photos),
        "final_result_codes": [p.get("finalResultCode") for p in photos],
        "decision_tier_codes": [p.get("decisionTierCode") for p in photos],
        "association_strengths": [p.get("associationStrength") for p in photos],
    }


# ── 比对(§6)──────────────────────────────────────────────────────

def _compare_display_decision(expected: dict, actual: dict, code_map: dict) -> tuple[str, str]:
    exp = expected.get("display_decision")
    if exp is None:
        return "unmapped", "case 未给 display_decision 期望"
    actual_code = actual.get("displayDecisionCode")
    acceptable = code_map.get("display_decision", {}).get(exp, [])
    if not acceptable:
        return "unmapped", f"期望 '{exp}' 在 code_map 尚无后端码映射;实际 displayDecisionCode={actual_code!r} → 待补映射后重判"
    if actual_code in acceptable:
        return "match", f"display_decision '{exp}' == {actual_code!r}"
    return "mismatch", f"期望 '{exp}'→{acceptable},实际 {actual_code!r}"


def _compare_decision_tier(expected: dict, actual: dict, code_map: dict) -> tuple[str, str]:
    """L2.5:expected.decision_tier(可多值)对 photos[].decisionTierCode。"""
    exp = expected.get("decision_tier")
    if exp is None:
        return "unmapped", "case 未给 decision_tier 期望"
    exp_list = exp if isinstance(exp, list) else [exp]
    tiers = actual.get("decision_tier_codes") or []
    accept_codes: set = set()
    for e in exp_list:
        accept_codes.update(code_map.get("decision_tier", {}).get(e, []))
    if not accept_codes:
        return "unmapped", f"期望 {exp_list} 尚无后端码映射;实际 decisionTierCode={tiers!r} → 待补映射"
    if any(t in accept_codes for t in tiers):
        return "match", f"decision_tier ∈ {exp_list} 命中 {tiers!r}"
    return "mismatch", f"期望 {exp_list}→{sorted(accept_codes)},实际 {tiers!r}"


def _compare_recall(expected: dict, actual: dict) -> tuple[str, str]:
    """cascade:落入同一 miniAlbumId 的张数 ≥ min_recalled。"""
    min_recalled = expected.get("min_recalled")
    n = actual.get("photo_count", 0)
    album_ids = actual.get("album_ids") or []
    if min_recalled is None:
        return "unmapped", f"case 未给 min_recalled;实际 album_ids={album_ids}, photo_count={n} → 待补映射/码值"
    # 落入同一集的最大张数(简化:有 album 即用 photo_count;精确计数待 pilot 摸 photos 结构)
    if album_ids and n >= min_recalled:
        return "match", f"召回 {n} ≥ {min_recalled}(album={album_ids})"
    return "mismatch", f"期望召回 ≥ {min_recalled},实际 album_ids={album_ids}, photo_count={n}"


def compare(case: dict, actual: dict, code_map: dict) -> tuple[str, str]:
    """按 expected 里实际给的字段逐项断言,聚合 verdict。
    任一 mismatch → mismatch;有 unmapped 无 mismatch → unmapped;全 match → match。
    """
    expected = case.get("expected", {})
    checks: list[tuple[str, str]] = []
    if "display_decision" in expected:
        checks.append(_compare_display_decision(expected, actual, code_map))
    if "decision_tier" in expected:
        checks.append(_compare_decision_tier(expected, actual, code_map))
    if "min_recalled" in expected:
        checks.append(_compare_recall(expected, actual))
    if not checks:
        return "unmapped", f"case 无可断言的 expected 字段 (path={case.get('path')!r})"
    verdicts = [v for v, _ in checks]
    if "mismatch" in verdicts:
        return "mismatch", " | ".join(d for v, d in checks if v == "mismatch")
    if "unmapped" in verdicts:
        ok = [d for v, d in checks if v == "match"]
        unmaps = [d for v, d in checks if v == "unmapped"]
        msg = " | ".join(unmaps)
        if ok:
            msg += f"  [其余已 match: {' / '.join(ok)}]"
        return "unmapped", msg
    return "match", " | ".join(d for _, d in checks)


# ── 执行单场景(§3 loop)────────────────────────────────────────────

def _photos_for(persona_id: str, ids: list[str], theme_map, sample, missing) -> list[dict]:
    pool = adapter.load_persona_photos(persona_id)
    specs = [pool[i] for i in ids]
    return adapter.build_photo_list(specs, theme_map=theme_map, sample=sample, missing=missing)


def run_case(case: dict, *, theme_map, sample, code_map, do_teardown: bool = True) -> CaseResult:
    """单场景隔离 session(§3 loop):setup → trigger → 取结果 → 比对 → teardown 逐个删 mockBizId。"""
    cid = case.get("id", case.get("_file", "?"))
    path = case.get("path", "?")
    expected = case.get("expected", {})
    persona = case["persona"]
    verdict_flag = case.get("verdict", "runnable")
    res = CaseResult(case_id=cid, path=path, verdict="error", detail="", expected=expected)

    if verdict_flag == "deferred":
        res.verdict = "deferred"
        res.detail = f"⛔ {case.get('defer_reason', 'loc/time')} 信号缺失,本轮不发请求"
        return res

    missing: set[str] = set()
    biz_ids: list[int] = []   # 本场景账本(teardown 用)
    try:
        # ── setup ──
        setup = case.get("setup") or {}
        if path == "L2.5":
            seeds = setup.get("seed_photos") or []
            if not seeds:
                res.verdict = "BLOCKED"; res.detail = "L2.5 缺 seed_photos"; return res
            seed_photos = _photos_for(persona, seeds, theme_map, sample, missing)
            sub = client.submit(seed_photos)
            if sub.mock_biz_id is not None:
                biz_ids.append(sub.mock_biz_id)
            seed_body = client._unwrap(client.poll_result(sub.mock_biz_id))
            seed_albums = sorted({p.get("miniAlbumId") for p in (seed_body.get("photos") or []) if p.get("miniAlbumId")})
            res.raw["setup"] = {"submit": sub.raw, "albums": seed_albums, "mockBizId": sub.mock_biz_id}
            if not seed_albums:
                res.verdict = "BLOCKED"
                res.detail = f"前置建集失败:seed {seeds} 未成集(无 miniAlbumId)→ 非 mismatch"
                return res
        elif path == "cascade":
            pool_ids = setup.get("pool_photos") or []
            if pool_ids:
                pool_photos = _photos_for(persona, pool_ids, theme_map, sample, missing)
                sub = client.submit(pool_photos)
                if sub.mock_biz_id is not None:
                    biz_ids.append(sub.mock_biz_id)
                client.poll_result(sub.mock_biz_id)
                res.raw["setup"] = {"pool_submit": sub.raw, "mockBizId": sub.mock_biz_id}

        # ── trigger ──
        trig_ids = (case.get("trigger") or {}).get("photos") or []
        trig_photos = _photos_for(persona, trig_ids, theme_map, sample, missing)
        sub = client.submit(trig_photos)
        if sub.mock_biz_id is None:
            res.verdict = "error"; res.detail = "trigger 未拿到 mockBizId"; res.raw["trigger"] = sub.raw
            return res
        biz_ids.append(sub.mock_biz_id)
        body = client._unwrap(client.poll_result(sub.mock_biz_id))
        res.raw["trigger"] = body
        res.actual = _extract_actual(body)
        res.missing_themes = sorted(missing)

        # ── 比对 ──
        res.verdict, res.detail = compare(case, res.actual, code_map)
    except Exception as e:  # noqa: BLE001 — 单场景失败不中断全量
        res.verdict = "error"
        res.detail = _scrub(f"{type(e).__name__}: {e}")
    finally:
        # ── teardown:逐个删本场景所有 mockBizId(per-id 级联 / 两种模式都对)──
        if do_teardown:
            teardown_errs: list[str] = []
            for mid in biz_ids:
                try:
                    client.delete_submission(mid)
                except Exception as e:  # noqa: BLE001
                    teardown_errs.append(_scrub(f"del({mid}): {type(e).__name__}: {e}"))
            if teardown_errs:
                res.raw["teardown_errors"] = teardown_errs
        res.raw["biz_ids"] = biz_ids
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default=None, help="只跑路径/文件名含该子串的 case")
    ap.add_argument("--keep", action="store_true", help="跳过 teardown(留库便于检查,慎用)")
    args = ap.parse_args()

    theme_map = adapter.load_theme_map()
    sample = adapter.load_sample()
    code_map = load_code_map()
    cases = load_cases(args.filter)

    print("=" * 72)
    print(f"runner · {datetime.now():%Y-%m-%d %H:%M:%S} · {len(cases)} case(s) · BASE={client.config.BASE_URL}")
    if args.keep:
        print("⚠ --keep:不 teardown,本场景的 mockBizId 残留库里(联调用)")
    print("=" * 72)

    results: list[CaseResult] = []
    for c in cases:
        print(f"\n▶ {c.get('id')} [{c.get('path')}] ({c['_file']})")
        r = run_case(c, theme_map=theme_map, sample=sample, code_map=code_map, do_teardown=not args.keep)
        results.append(r)
        mark = {"match": "✓", "acceptable": "≈", "mismatch": "✗", "BLOCKED": "▣",
                "deferred": "⊘", "error": "!", "unmapped": "?"}.get(r.verdict, "?")
        print(f"  {mark} {r.verdict}: {r.detail}")
        if r.actual:
            a = r.actual
            print(f"    route={a.get('route')} displayDecisionCode={a.get('displayDecisionCode')!r} "
                  f"decisionRemark={a.get('decisionRemark')!r} album_ids={a.get('album_ids')}")
        if r.missing_themes:
            print(f"    ⚠ 缺译 theme: {r.missing_themes}")

    _RESULTS_DIR.mkdir(exist_ok=True)
    out = _RESULTS_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2), encoding="utf-8")

    counts: dict[str, int] = {}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    print("\n" + "=" * 72)
    print("汇总: " + " · ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"结果落: {out.relative_to(_HERE.parent)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
