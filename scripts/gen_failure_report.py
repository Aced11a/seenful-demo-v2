"""生成失败分类报告(md):按机制归类 mismatch/BLOCKED/deferred,每类列对应 case。

跑法(项目根目录):
    python scripts/gen_failure_report.py                   # 用最新 results/run_*.json
    python scripts/gen_failure_report.py <run.json>        # 指定文件
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO / 'api_harness' / 'results'


def trig_tags_str(r: dict) -> str:
    tags = (r.get('raw') or {}).get('trigger_tags') or []
    if not tags:
        return '(无)'
    parts = []
    for t in tags[:4]:
        scene = ' '.join((t.get('ai_scene_tags') or [])[:4])
        parts.append(f"{t.get('id')}: {scene}")
    suf = f' + 共 {len(tags)} 张' if len(tags) > 4 else ''
    return ' | '.join(parts) + suf


def setup_tags_str(r: dict) -> str:
    tags = (r.get('raw') or {}).get('setup_tags') or []
    if not tags:
        return '(无)'
    parts = []
    for t in tags[:3]:
        scene = ' '.join((t.get('ai_scene_tags') or [])[:3])
        parts.append(f"{t.get('id')}: {scene}")
    suf = f' + 共 {len(tags)} 张' if len(tags) > 3 else ''
    return ' | '.join(parts) + suf


def actual_brief(r: dict) -> str:
    a = r.get('actual') or {}
    pattern = a.get('decisionRemark') or ','.join(p for p in (a.get('truth_table_patterns') or []) if p)
    code = a.get('displayDecisionCode') or (a.get('decision_tier_codes') or ['(无)'])
    return f"`{code}` · pattern `{pattern}` · album_ids `{a.get('album_ids') or '[]'}`"


def expected_brief(r: dict) -> str:
    exp = r.get('expected') or {}
    bits = []
    for k in ('display_decision', 'decision_tier', 'min_recalled'):
        if exp.get(k) is not None:
            bits.append(f"`{k} = {exp[k]}`")
    return ' · '.join(bits) or '(无)'


CATEGORIES = [
    {
        'id': 'A1',
        'title': 'L2 阈值偏严 → 主题分散判 F1 suppress(应成集没成)',
        'summary': '后端 L2 主路径对多元主题集合容忍度低,5 张露营 / 3 张 citywalk / 3 张网红打卡都被 truth_table_final_F1 拒了。产品意图允许「一次行程多场景」成集,后端不行。',
        'match': lambda r: r['verdict'] == 'mismatch' and r['path'] == 'L2'
                 and (r.get('actual') or {}).get('decisionRemark', '') == 'truth_table_final_F1',
    },
    {
        'id': 'A2',
        'title': 'L2 → show_inline_hint(轻提示,应成集只给了轻提示)',
        'summary': '后端判 D3 / E2 给轻提示,产品意图希望直接成集。可能是中间档判定阈值偏严。',
        'match': lambda r: r['verdict'] == 'mismatch' and r['path'] == 'L2'
                 and (r.get('actual') or {}).get('displayDecisionCode', '') == 'show_inline_hint',
    },
    {
        'id': 'B1',
        'title': 'L2.5 候选筛选阶段失败(G-F1 / no_candidate_album)',
        'summary': 'setup 成功建了 album,但 trigger 来时后端在候选筛选中没匹配到该 album → G-F1 不命中以上 → no_merge。可能是主题匹配阈值或老相册可见性问题。',
        'match': lambda r: r['verdict'] == 'mismatch' and r['path'] == 'L2.5'
                 and any(p in ((r.get('actual') or {}).get('truth_table_patterns') or [])
                         for p in ('G-F1', 'no_candidate_album')),
    },
    {
        'id': 'B2',
        'title': 'L2.5 后端比期望激进(应 ask_user 但 auto_merge)',
        'summary': 'event 冲突 / 多义性场景产品意图希望 ask_user 让用户判,后端直接 auto_merge 合了。后端可能缺少冲突检测维度。',
        'match': lambda r: r['verdict'] == 'mismatch' and r['path'] == 'L2.5'
                 and 'auto_merge' in ((r.get('actual') or {}).get('decision_tier_codes') or [])
                 and 'auto_merge' not in (
                     (r.get('expected') or {}).get('decision_tier') if isinstance((r.get('expected') or {}).get('decision_tier'), list)
                     else [(r.get('expected') or {}).get('decision_tier')]
                 ),
    },
    {
        'id': 'B3',
        'title': 'L2.5 sensitive 返回新码值 not_applicable',
        'summary': '敏感照片在 L2.5 走的不是 no_merge,而是新码 not_applicable + pattern photo_sensitive_medium_or_high。语义疑似 = 敏感照片绕过 L2.5,等价 no_merge。需后端确认。',
        'match': lambda r: r['verdict'] == 'mismatch'
                 and 'not_applicable' in ((r.get('actual') or {}).get('decision_tier_codes') or []),
    },
    {
        'id': 'C1',
        'title': 'BLOCKED · seed 主题分散 / 张数不足(后端拒成集)',
        'summary': 'L2.5 setup 阶段需要用 seed 重建老相册,但后端 L2 阈值偏严导致 seed 没形成 album → trigger 无前置可加入 → BLOCKED。这是 A.1 的下游影响 + 我们 SEED_MAP 选张策略问题。',
        'match': lambda r: r['verdict'] == 'BLOCKED' and '前置建集失败' in (r.get('detail') or ''),
    },
    {
        'id': 'C2',
        'title': 'BLOCKED · 原 scenario old_albums 列表空',
        'summary': '原 persona 设计这两个 case 就是「无前置 album 时」的 L2.5 行为测试。台子目前需要 seed 才能跑,这两个直接 BLOCKED。需要重设为 trigger 单独提交看 no_candidate_album,或标 deferred。',
        'match': lambda r: r['verdict'] == 'BLOCKED' and '缺 seed_photos' in (r.get('detail') or ''),
    },
    {
        'id': 'D1',
        'title': 'Deferred · 后端 cascade 路径疑似缺失(全部搁置)',
        'summary': '15 个 cascade case 全部搁置。探针实证:池中单张孤立提交永远 no_candidate_album,后端目前只有 L2.5(加入已成集老相册),没真正的 cascade(召回散张沉淀组团)。待后端核实。',
        'match': lambda r: r['verdict'] == 'deferred' and r.get('path') == 'cascade',
    },
    {
        'id': 'D2',
        'title': 'Deferred · 本轮缺 GPS / time / HFP 信号',
        'summary': '26 个 L2 / L2.5 case 期望根本性靠位置 / 时间 / 高频地点,微信小程序环境拿不到 → 整条 defer 等将来补 EXIF 信号。',
        'match': lambda r: r['verdict'] == 'deferred' and r.get('path') != 'cascade',
    },
]


def build_report(arr: list, run_file: Path) -> str:
    total = len(arr)
    by_v: dict = defaultdict(list)
    for r in arr:
        by_v[r['verdict']].append(r)

    classified = {c['id']: [] for c in CATEGORIES}
    uncategorized = []
    for r in arr:
        if r['verdict'] == 'match':
            continue
        hit = False
        for c in CATEGORIES:
            try:
                if c['match'](r):
                    classified[c['id']].append(r)
                    hit = True
                    break
            except Exception:
                continue
        if not hit and r['verdict'] in ('mismatch', 'BLOCKED', 'error'):
            uncategorized.append(r)

    lines = []
    lines.append('# api_harness 失败归类报告')
    lines.append('')
    lines.append(f'- **生成**: {datetime.now():%Y-%m-%d %H:%M:%S}')
    lines.append(f'- **数据源**: `{run_file.relative_to(REPO)}`')
    lines.append(f'- **总 case**: {total}')
    lines.append(f"- **分布**: ✓ match={len(by_v['match'])} · ✗ mismatch={len(by_v['mismatch'])} · ▣ BLOCKED={len(by_v['BLOCKED'])} · ⊘ deferred={len(by_v['deferred'])}")
    lines.append('')
    lines.append('> 按「产品意图原则」(CLAUDE 第4条):expected 是「产品该不该成集」的判断,**不改 expected 迎合后端**。')
    lines.append('> mismatch / BLOCKED 不是台子 bug,是后端实现与产品意图的 gap,正是测试要暴露的核心信号。')
    lines.append('')
    lines.append('---')
    lines.append('')

    lines.append('## 1. 失败类别速览')
    lines.append('')
    lines.append('| 编号 | 类别 | 数量 | case |')
    lines.append('|---|---|---|---|')
    for c in CATEGORIES:
        cases = classified[c['id']]
        if not cases:
            continue
        case_ids = ', '.join(r['case_id'].replace('_', r'\_') for r in cases[:5])
        if len(cases) > 5:
            case_ids += f', ... ({len(cases) - 5} 更多)'
        lines.append(f"| **{c['id']}** | {c['title']} | {len(cases)} | {case_ids} |")
    if uncategorized:
        lines.append(f"| ?? | 未归类(检查脚本规则) | {len(uncategorized)} | {', '.join(r['case_id'] for r in uncategorized[:3])} |")
    lines.append('')
    lines.append('---')
    lines.append('')

    lines.append('## 2. 逐类详情')
    lines.append('')
    for c in CATEGORIES:
        cases = classified[c['id']]
        if not cases:
            continue
        lines.append(f"### {c['id']}. {c['title']}")
        lines.append('')
        lines.append(f'**数量**: {len(cases)} 条')
        lines.append('')
        lines.append(f"**为什么**: {c['summary']}")
        lines.append('')
        lines.append('**对应 case**:')
        lines.append('')
        for r in cases:
            cid = r['case_id']
            path = r.get('path')
            v = r['verdict']
            if v == 'mismatch':
                lines.append(f'- **{cid}** ({path})')
                lines.append(f'  - 产品意图: {expected_brief(r)}')
                lines.append(f'  - 后端实际: {actual_brief(r)}')
                trig = trig_tags_str(r)
                if trig != '(无)':
                    lines.append(f'  - trigger 主题: {trig}')
                seed = setup_tags_str(r)
                if seed != '(无)':
                    lines.append(f'  - setup seed: {seed}')
            elif v == 'BLOCKED':
                lines.append(f'- **{cid}** ({path})')
                lines.append(f"  - 阻塞原因: {r.get('detail', '')}")
                seed = setup_tags_str(r)
                if seed != '(无)':
                    lines.append(f'  - setup seed 主题: {seed}')
            elif v == 'deferred':
                lines.append(f"- **{cid}** ({path}) — {r.get('detail', '')}")
            lines.append('')
        lines.append('---')
        lines.append('')

    lines.append('## 3. 整体建议')
    lines.append('')
    lines.append('### 3.1 给后端同事(系统性 gap,需要排查/确认)')
    lines.append('')
    lines.append('1. **L2 阈值偏严(A.1 + A.2 共 5 条)**:后端把「多元同行程」判 suppress 或 show_inline_hint,产品意图允许成集(露营 / citywalk / 地标 都该成「行程集」)。truth_table_final_F1 / D3 / E2 命中过早,主题分散度容忍度需要松一档。')
    lines.append('2. **L2.5 event 冲突维度未识别(B.2 共 1 条)**:`L25_zhang_event_conflict_to_album` 家宴+生日 event 冲突,期望 ask_user 让用户判,后端 auto_merge 直接合 → 后端缺 event 冲突检测维度。')
    lines.append('3. **L2.5 sensitive 返回新码 `not_applicable`(B.3 共 1 条)**:`L25_zhang_sensitive_to_any` 后端用 `not_applicable` + pattern `photo_sensitive_medium_or_high`,语义疑似 = 敏感照片绕过 L2.5。**请后端确认是否等价 no_merge**,若是 → 加入 code_map 兼容。')
    lines.append('4. **cascade 路径疑似缺失(D.1 共 15 条)**:池单张提交永远 no_candidate_album。后端目前只有 L2.5,没真正的 cascade(召回散张沉淀组团)。需确认是否在 roadmap / 当前未启用。')
    lines.append('5. **truth pattern 偏 event-driven**:L25_R3 lake / L25_high_freq_birthday 等 theme 驱动 case 命中 G-B2(event=强)而非 G-B1(theme=强)→ 后端把 theme dominant 误识别为 event dominant。')
    lines.append('6. **route 字段不准**:大多数 case 包括 L2 主路径的 D2 sensitive 都返回 route=`L2_5`。路径分类逻辑 buggy。')
    lines.append('')
    lines.append('### 3.2 给我们自己(台子改进)')
    lines.append('')
    lines.append('1. **L25_R2_zhang_walk_to_walk** BLOCKED:trigger z07 与 SEED 重叠后 seed 仅剩 2 张不够。可在 SEED_MAP 加第 3 张 garden 主题备份,或接受台子限制。')
    lines.append('2. **L25_li_multi_anchor_to_xihu BLOCKED 偶发**:同 seed(l01-l06 5 张)在 L25_R3 ✓ 这条 ✗ → 后端时序竞态。可延长 _SETUP_INDEX_DELAY_S 或加重试。')
    lines.append('3. **L25_xiaowang_concert / multi_theme** BLOCKED:原 scenario 设计 old_albums=[]。台子可改为「无 setup 直接 trigger,期望 no_candidate_album = no_merge」。')
    lines.append('4. **缺译 theme**:跑期间日志有若干新缺译 token(boba_dessert / oriental_tower / camping / starry_sky / shikumen_alley 等),可按需补 theme_tag_zh_map.json 提升主题匹配精度。')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('配套:`api_harness/_DASHBOARD.html` 看 76 case 完整视图(filter 选 mismatch / BLOCKED 直接定位)。')
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('run_file', nargs='?', default=None, help='results/run_*.json 路径;省略=用最新')
    args = ap.parse_args()

    if args.run_file:
        run_file = Path(args.run_file).resolve()
    else:
        files = sorted(RESULTS_DIR.glob('run_*.json'))
        if not files:
            print('no run files found')
            sys.exit(1)
        run_file = files[-1]

    arr = json.loads(run_file.read_text(encoding='utf-8'))
    md = build_report(arr, run_file)

    stem = run_file.stem.replace('run_', '')
    out = RESULTS_DIR / f'failure_report_{stem}.md'
    out.write_text(md, encoding='utf-8')
    print(f'✓ 失败归类报告: {out}')
    print(f'  数据源: {run_file.name}, 共 {len(arr)} case')


if __name__ == '__main__':
    main()
