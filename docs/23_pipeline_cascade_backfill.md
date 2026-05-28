# 23 · Pipeline 流程分流 + Cascade Backfill (PRD §3.10 校准实施)

> Pipeline `run_full_l2` 三路分流 + 多张 B 失败拆 N 张 cascade 实施规范.
> 算法依据: [ADR-0017](../decisions/0017-pipeline-cascade-backfill.md).
> 原始 spec: [Pipeline_Cascade_Backfill_Spec.md](../Pipeline_Cascade_Backfill_Spec.md) v0.3 (实施完后归档).
> PRD 依据: 登场识图知意 PRD v1.1 §3.10 (兜底回扫机制).

---

## 一、流程总览

### 1.1 · 三路分流决策树

```
用户上传 N 张照片
  │
  ├─ N=1 (单张):
  │   P → Path A (vs 老相册)
  │     ├─ auto_merge / ask_user → 加入老相册 ✓
  │     └─ no_merge → Path C cascade_backfill_single (vs 30 天 sediment)
  │                    ├─ create_new_album → 新建相册 ✓
  │                    └─ no_backfill / insufficient → P 沉淀
  │
  ├─ N=2 (双张):
  │   Path B light_judge (PRD §3.2.2)
  │     ├─ show_inline_hint → 对话轻提示 (不进相册)
  │     └─ suppress → 沉淀
  │   ⚠ demo v0.1 不写场景测试
  │
  └─ N ≥ 3 (多张):
      Path B 整批
        ├─ show_mini_album → 创建新相册 (N 张全成集) ✓
        ├─ show_inline_hint → 对话轻提示
        └─ suppress / F1 → 失败, 拆 N 张
              │
              ▼
            for each P_i in N 张 (顺序无所谓):
              Path A
                ├─ auto_merge / ask_user → P_i 加入老相册 ✓
                └─ no_merge → cascade_backfill_single(P_i, working_sediment)
                                ├─ create_new_album → P_i 起新相册, 召回的 sediment 退出池
                                └─ failed → P_i 进 sediment, 后续 P_j 可召回
```

### 1.2 · 沉淀池自然承接

多张拆 N 张时, **不需要显式"失败兄弟"机制**. P_i 走 C 失败进 sediment → P_j 处理时 P_i 已经在池里, 自然被 P_j 的 30 天扫描召回.

```
拆 5 张, sediment 池初始 0 张:
  P1 走 C: 粗筛 0 张 (池空) → P1 进沉淀, 池 = [P1]
  P2 走 C: 粗筛 [P1] → 1 张 (<2 不足) → P2 进沉淀, 池 = [P1, P2]
  P3 走 C: 粗筛 [P1, P2] → 2 张 ≥2, strong → create_new_album {P3, P1, P2}, 池 = []
  P4 走 C: 粗筛 0 张 → P4 进沉淀, 池 = [P4]
  P5 走 C: 粗筛 [P4] → 1 张 (<2) → P5 进沉淀, 池 = [P4, P5]

结果: cascade_albums = [{P3,P1,P2}], settled = [P4, P5]
```

---

## 二、cascade_backfill_single 算法

### 2.1 · 完整流程

```python
def cascade_backfill_single(
    new_photo: L1Output,
    sediment_pool: list[L1Output],
    scenario: str | None = None,
) -> BackfillDecisionLog:
    """单张 P 跑 PRD §3.10 标准 cascade backfill."""
    cfg = load_config("truth_table_backfill.yaml")

    # Step 1 · 池规模上限 (demo v0.1 最近 50 张)
    sediment_capped = sorted(
        sediment_pool, key=lambda p: p.captured_at, reverse=True
    )[:cfg["candidate_pool"]["max_sediment_size"]]

    # Step 2 · OR 粗筛 (PRD §3.10.5, 不在此截 5)
    # GPS<1km OR theme>0.5 OR event 一致 (非 unknown)
    candidates_raw = filter_backfill_or_coarse(new_photo, sediment_capped, cfg)

    # Step 3 · 维度强度总分排序选 top 4
    candidates, ranking = rank_and_pick_top_n(
        new_photo, candidates_raw,
        n=cfg["max_recall_photos"],            # 4 (PRD §3.10.5)
        weights=cfg["priority_weight"],        # gps=1.0, theme=1.0, event=0.5
    )

    # Step 4 · 现 apply_backfill_caps (不动, PRD §3.10.5 strong-only)
    truth_table, llm = evaluate_main_table(new_photo, candidates)
    caps_result = apply_backfill_caps(new_photo, candidates, truth_table, llm)

    # Step 5 · BackfillDecisionLog (加 priority_ranking)
    return BackfillDecisionLog(
        decision_id=...,
        new_photo_id=new_photo.photo_id,
        coarse_filter_candidates=[p.photo_id for p in candidates_raw],
        priority_ranking=ranking,                  # ← ADR-0017 新增
        main_truth_table_match=truth_table,
        llm_judgement=llm,
        backfill_caps_applied=caps_result.caps,
        final_decision=caps_result.decision,
    )
```

### 2.2 · 维度强度总分排序

```python
def rank_and_pick_top_n(new_photo, candidates, n, weights):
    """对粗筛候选按维度强度总分排序, 取 top N.

    score = gps(1.0) + theme(1.0) + event(0.5)

    event 权重 0.5 因为 event_hint 是封闭 10 枚举 (daily_record / outing /
    meal 占绝大多数), 命中"event 一致"概率高但语义关联强度弱.
    """
    scored = []
    for c in candidates:
        score = 0.0
        is_gps = gps_within_km(new_photo, c, 1.0)
        is_theme = theme_jaccard(new_photo, c) > 0.5
        is_event = event_match(new_photo, c)

        if is_gps: score += weights["gps"]
        if is_theme: score += weights["theme"]
        if is_event: score += weights["event"]

        scored.append((c, score, is_gps, is_theme, is_event))

    # 总分降序, tie-breaker = captured_at 倒序 (最近优先)
    scored.sort(key=lambda x: (-x[1], -x[0].captured_at.timestamp()))

    selected = scored[:n]
    selected_ids = {c.photo_id for c, _, _, _, _ in selected}

    # 落痕所有候选的 ranking (审计 + OQ-28f 调优用)
    ranking = [
        PriorityRankingEntry(
            photo_id=c.photo_id,
            gps_within_1km=is_g, theme_jaccard_above_0_5=is_t, event_match=is_e,
            score=s, selected=(c.photo_id in selected_ids),
        )
        for c, s, is_g, is_t, is_e in scored
    ]
    return [c for c, _, _, _, _ in selected], ranking
```

### 2.3 · 排序示例

| 候选 | gps<1km | theme>0.5 | event 一致 | score | 排名 (n=4) |
|---|---|---|---|---|---|
| c1 | ✓ | ✓ | ✓ | 2.5 | 1 ✓ |
| c2 | ✓ | ✓ | ✗ | 2.0 | 2 ✓ |
| c3 | ✓ | ✗ | ✓ | 1.5 | 3 ✓ |
| c4 | ✗ | ✓ | ✓ | 1.5 | 4 ✓ |
| c5 | ✓ | ✗ | ✗ | 1.0 | 5 ✗ |
| c6 | ✗ | ✗ | ✓ | 0.5 | 6 ✗ |
| c7 | ✓ | ✗ | ✗ | 1.0 | 7 ✗ |

`c5 / c6 / c7` 单维命中但被 0.5×event 权重压在 c4 (theme+event 多维) 之后. event 单独命中 (c6=0.5) 永远排在任一 GPS/theme 命中之后.

---

## 三、`apply_backfill_caps` 三条 Caps (不动)

| Cap | 检查 | PRD 出处 |
|---|---|---|
| CAP-01 | `truth_table.bounds_max == strong` | §3.10.5 表 "兜底回扫: strong 以上" |
| CAP-02 | `llm.proposed_strength == strong` | §3.10.5 LLM 复核也需 strong |
| CAP-03 | `recalled_photos >= 2` | §3.10.4 "至少召回 2 张沉淀单图(总数 ≥ 3 张)" |

**任一未过 → no_backfill / insufficient_candidates**.

⚠ ADR-0017 **不删不改** `apply_backfill_caps`. v0.2 spec "删函数 + 改调 run_l2_path_b 内核" 路线**已作废**.

---

## 四、多张 B 失败拆 N 张 dispatch

```python
def run_full_l2(new_photos, growing_albums, sediment_pool, scenario=None):
    N = len(new_photos)

    # ── N=1 单张 ──
    if N == 1:
        P = new_photos[0]
        g_log = run_growth_path(P, growing_albums, scenario)
        if g_log.final_decision.decision_tier in ("auto_merge", "ask_user"):
            return ArbitrationResult(winner="path_A", primary_album=...)

        b_log = cascade_backfill_single(P, sediment_pool, scenario)
        if b_log.final_decision.decision_tier == "create_new_album":
            return ArbitrationResult(winner="path_C", primary_album=新相册, ...)
        return ArbitrationResult(winner="none", settled_photo_ids=[P.photo_id])

    # ── N=2 双张 (PRD §3.2.2) ──
    elif N == 2:
        l2_log = run_l2_path_b(new_photos, scenario)
        return arbitrate_l2_only(l2_log)
        # 不走 A/C; demo v0.1 不写测试

    # ── N≥3 多张 ──
    else:
        l2_log = run_l2_path_b(new_photos, scenario)
        if l2_log.final_decision.association.display_decision == "show_mini_album":
            return ArbitrationResult(winner="path_B", primary_album=..., ...)

        # B 失败 → 拆 N 张, 每张独立 A → C
        growth_merges: list[GrowthMergeRecord] = []
        cascade_albums: list[Association] = []
        settled_photo_ids: list[str] = []
        working_sediment = list(sediment_pool)        # 拷贝, 动态增减

        for P_i in new_photos:
            g_log = run_growth_path(P_i, growing_albums, scenario)
            if g_log.final_decision.decision_tier in ("auto_merge", "ask_user"):
                growth_merges.append(GrowthMergeRecord(
                    photo_id=P_i.photo_id,
                    target_album_id=g_log.final_decision.merge_target_album_id,
                    decision_tier=g_log.final_decision.decision_tier,
                ))
                continue

            b_log = cascade_backfill_single(P_i, working_sediment, scenario)
            if b_log.final_decision.decision_tier == "create_new_album":
                cascade_albums.append(_album_from_backfill(P_i, b_log))
                # 已召回的 sediment 退出池, 不重复召回
                working_sediment = [
                    p for p in working_sediment
                    if p.photo_id not in b_log.final_decision.recalled_photo_ids
                ]
            else:
                settled_photo_ids.append(P_i.photo_id)
                working_sediment.append(P_i)          # 进沉淀, 后续 P_j 可召回

        return arbitrate_cascade(
            l2_log, growth_merges, cascade_albums, settled_photo_ids,
        )
```

---

## 五、多产物 ArbitrationResult

| 字段 | 类型 | 用途 |
|---|---|---|
| `primary_album` | Association \| None | N=1 走 A/C 命中 / 多张 B 整批命中 |
| `cascade_albums` | list[Association] | 多张 B 失败拆 N 张后, 各 P_i 各自 cascade 命中 (可能 0~N 个) |
| `growth_merges` | list[GrowthMergeRecord] | 多张 B 失败拆 N 张后, 各 P_i 走 A 命中 |
| `settled_photo_ids` | list[str] | 拆 N 张后 A/C 都失败的 photos |
| `arbitration_winner` | `"path_A" / "path_B" / "path_C" / "cascade" / "none"` | 主要 winner |
| `case_matched` | str | Case 1-8 (含新 Case 5 多张拆 N 张) |

---

## 六、Case 验证 (8 个)

| Case | 输入 | 输出 | 说明 |
|---|---|---|---|
| A | N=1, A 命中 | winner=path_A, primary_album=老相册 | 单张加入 |
| B | N=1, A 失败 + C 命中 | winner=path_C, primary_album=新相册 | 单张救活 |
| C | N=1, A C 都失败 | winner=none, settled=[P] | 单张沉淀 |
| D | N=5, B 整批命中 | winner=path_B, primary_album=新相册 5 张 | 多张整批 |
| E | N=5, B 失败, 3 A + 2 C 命中 | winner=cascade, growth_merges=3, cascade_albums=[5张, 3张] | 拆 N 张混合救活 |
| F | N=5, B 失败, 0 A + 部分 C 命中 (含沉淀池自然承接) | winner=cascade, cascade_albums=3 个 | 自然承接演示 |
| G | Case F 顺序反过来 | 等价于 Case F | 顺序无所谓 |
| H | N=1, 5 张候选 4 张 event 一致 + 1 张 GPS | top 4 含 1 GPS + 3 event | event×0.5 权重验证 |

详见 [Pipeline_Cascade_Backfill_Spec.md §七](../Pipeline_Cascade_Backfill_Spec.md).

---

## 七、配置

`config/truth_table_backfill.yaml` (ADR-0017 新增字段):

```yaml
backfill:
  lookback_days: 30
  coarse_filter:
    gps_max_km: 1.0
    theme_jaccard_min: 0.5
    match_event_hint: true
    # max_candidates 字段保留兼容, cascade_backfill_single 不用 (改用 max_recall_photos)

  max_recall_photos: 4                       # PRD §3.10.5 召回上限

  priority_weight:                            # ← ADR-0017 新增
    gps: 1.0
    theme: 1.0
    event: 0.5                                # event_hint 封闭枚举易重复, 降权

  candidate_pool:                             # ← ADR-0017 新增
    max_sediment_size: 50                     # demo v0.1; PRD §3.10.10 说 200+ 改激进粗筛

  caps:
    require_truth_table_bounds_max_strong: true
    require_llm_proposed_strength_strong: true
    min_recalled_photos: 2
```

---

## 八、契约变更

### 8.1 · BackfillDecisionLog 加 priority_ranking

```python
class PriorityRankingEntry(BaseModel):
    photo_id: str
    gps_within_1km: bool
    theme_jaccard_above_0_5: bool
    event_match: bool
    score: float
    selected: bool                            # 是否进入 top 4

class BackfillDecisionLog(BaseModel):
    # ... 原字段不变 ...
    priority_ranking: list[PriorityRankingEntry] = []   # ← ADR-0017 新增
```

### 8.2 · ArbitrationResult 多产物

```python
class GrowthMergeRecord(BaseModel):
    photo_id: str
    target_album_id: str
    decision_tier: Literal["auto_merge", "ask_user"]

class ArbitrationResult(BaseModel):
    # ... 原字段不变 ...
    cascade_albums: list[Association] = []              # ← ADR-0017 新增
    settled_photo_ids: list[str] = []                   # ← ADR-0017 新增
    growth_merges: list[GrowthMergeRecord] = []         # ← ADR-0017 新增
```

---

## 九、性能预算

| 操作 | 算力 |
|---|---|
| OR 粗筛 (50 张池) | <2ms (haversine + jaccard 各 50 次) |
| 维度排序 (50 张候选) | <1ms (Python sort) |
| `apply_backfill_caps` | <1ms (查 caps + 组装 Decision) |
| 主真值表 + LLM mock | <5ms (LLM mock 桩) |
| **单次 cascade** | **<10ms** (mock 阶段) |
| **多张拆 N=5 张** | **<50ms** (5 次 cascade) |

---

## 十、不变性

1. **单张走 A → C, 多张走 B → 拆 N 张 A → C** (每张独立)
2. **N=2 走 light_judge**, 不走 A/C, demo v0.1 不测
3. **cascade 单次完全沿用 v0.1 `apply_backfill_caps`** (strong-only, 不删不改)
4. **召回上限 4 张** (PRD §3.10.5)
5. **维度强度总分排序选 top N**, event 权重 0.5
6. **沉淀池自然承接** (顺序无所谓)
7. **召回的 sediment 在该批内不重复**
8. **粗筛保留 OR** (GPS/theme/event)
9. **多产物输出** (primary_album + cascade_albums + growth_merges + settled_photo_ids)
10. **不动 path B / path A / 维度算法**

---

## 十一、关联

**ADR**:
- [ADR-0017](../decisions/0017-pipeline-cascade-backfill.md) (本算法决策)

**docs**:
- [docs/05_truth_table_backfill.md](./05_truth_table_backfill.md) (path C 真值表 + caps 保留)
- [docs/09_arbitration.md](./09_arbitration.md) (仲裁器多产物扩展)
- [docs/02_data_contracts.md](./02_data_contracts.md) (新增 cascade_albums/growth_merges/PriorityRankingEntry)
- [docs/01_architecture.md](./01_architecture.md) (pipeline 流程图)

**代码**:
- `src/pipeline.py::run_full_l2` (三路分流)
- `src/policy/cascade_backfill.py::cascade_backfill_single` (cascade 单次)
- `src/candidate_builder/backfill_scan.py::rank_and_pick_top_n` (优先级排序)
- `src/policy/backfill_engine.py::apply_backfill_caps` (不动, strong-only)
- `src/arbitration/merge_results.py::arbitrate` (多产物合并)
- `src/contracts/{arbitration,backfill}.py` (新契约)

**OQ**:
- [OQ-028](./12_open_questions.md#oq-028-pipeline-cascade-backfill-边界) (含 OQ-28b/c/e/f)
- 重点 OQ-28f: event 0.5 权重真实数据调优

**原始 spec** (实施完后归档):
- `Pipeline_Cascade_Backfill_Spec.md` v0.3 → `archive/specs/`
