# Pipeline Cascade Backfill 规范 (流程改造 + 回滚校准 PRD §3.10)

> **版本**: v0.3 (draft, 待 Ace 审核 — PRD §3.10 校准版, 整体回退 v0.2 "向 L2 对齐" 路线)
> **日期**: 2026-05-19
> **适用**: Seenful L2 Engine 整套上传决策流水线 (path A/B/C + 仲裁)
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (ADR-0017 + docs/23).
>
> **决策来源 (Ace 2026-05-18 → 2026-05-19)**:
> 1. **单张上传**: Path A 失败 → Path C 回滚
> 2. **多张上传**: Path B 失败 → 拆 N 张 → 每张独立 Path A → 失败再独立走 Path C
> 3. **N=2 走 light_judge**, 不进相册, 不写测试
> 4. **回滚机制严格遵循 PRD §3.10**:
>    - 召回上限 4 张 (PRD §3.10.5)
>    - strong-only 门槛 (PRD §3.10.5 + §3.10.10 风险 1)
>    - 至少召回 2 张 (PRD §3.10.4 "总数 ≥ 3 张")
>    - 任务 1 命中, 任务 2 丢弃 (PRD §3.10.3 禁用策略 3)
> 5. **粗筛后选 4 张按维度强度总分排序** (Ace 5/19 新增):
>    - score = (gps<1km ? 1.0 : 0) + (theme>0.5 ? 1.0 : 0) + (event 一致 ? **0.5** : 0)
>    - event 降权 0.5 因为 event_hint 是封闭 10 枚举, 易重复, 语义关联强度低于 GPS / theme
>
> **跟 v0.2 的关键差别**:
> - ❌ v0.2 "删 Caps + 调 run_l2_path_b 内核" 路线**完全作废**
> - ❌ v0.2 "失败兄弟互为候选" 整段**删除** (兄弟沉淀后下次自然在池里, 不需要显式 sibling 召回)
> - ✅ 保留 v0.2 流程层 (单/双/多张分流 + 拆 N 张 + 多产物 ArbitrationResult)

---

## 一、背景

### 1.1 · 现状

`src/pipeline.py::run_full_l2` 当前流程:

```python
# 现实现:
1. Path A (任意张数, 仅对 primary_photo) 跑
2. Path B (≥3 张) 跑
3. Path C 真兜底: 仅当 A 和 B 都失败 + sediment 池非空时跑 (仅 primary_photo)
4. Arbitrate 三路结果
```

**流程问题** (Ace 2026-05-18 拍板新流程要解决的):
- ❌ 多张上传, B 失败后**只对 primary_photo 跑 C**, 其他 N-1 张直接沉淀
- ❌ B 失败后**不拆 N 张走 A**, 错过"3 张并入老相册 + 2 张走 C 救活" 的机会
- ❌ N=1 单张直接进 path B 整套 (但 B 需要 ≥3 张), 应该直接走 A → C

**Path C 自身判定** (v0.3 不动): 现 `src/policy/backfill_engine.py::apply_backfill_caps` 的三条独立 Caps **本质就是 PRD §3.10.5 的"strong 以上 + 召回 ≥ 2 张"门槛**, 不删, 不改:

| Cap | 检查 | PRD 出处 |
|---|---|---|
| CAP-01 | `truth_table.bounds_max == strong` | §3.10.5 表格 "兜底回扫: strong 以上" |
| CAP-02 | `llm.proposed_strength == strong` | §3.10.5 表格 (LLM 复核也需 strong) |
| CAP-03 | `recalled_photos >= 2` | §3.10.4 "至少召回 2 张沉淀单图(总数 ≥ 3 张)" |

### 1.2 · Ace 拍板新流程

```
单张上传 (N=1):
   P → Path A
     ├─ 命中 → 加入老相册
     └─ 失败 → Path C (vs 30 天 sediment)
           ├─ 命中 → 新建相册
           └─ 失败 → P 沉淀

多张上传 (N ≥ 3):
   N 张 → Path B (整批)
     ├─ 命中 → 创建新相册 (N 张全成集)
     └─ 失败 → 拆 N 张
           for each P:
               Path A
               ├─ 命中 → P 加入老相册
               └─ 失败 → Path C (vs 30 天 sediment, 独立)
                          ├─ 命中 → 新建相册
                          └─ 失败 → P 沉淀

双张上传 (N=2):
   light_judge (最高轻提示, 不进相册, 不走后续 A/C)
   不写场景测试 (Ace 决策, demo v0.1)
```

**关键: 多张 B 失败后, 每张独立走 A → C, cascade 之间互相独立**. 兄弟之间的关联通过"沉淀池"自然承接 — P_i 走 C 失败 → P_i 进 sediment → 处理 P_j 时 P_i 已经在 sediment 池里, 自然被 P_j 的 30 天扫描召回. 不需要显式 "failed_siblings" 机制.

### 1.3 · 引发本 spec 的具体问题

- 当前多张失败"全部沉淀"产品体验差, 错过救活机会 (拆 N 张走 A→C 救活)
- 单张直接进 B 套是错的, 应该 A → C
- 仲裁器只支持单产物输出, 不能"一次上传产 N 个增长记录 + M 个新相册"

---

## 二、核心算法范式

### 2.1 · 完整决策树

```
用户上传 N 张照片
  │
  ├─ N=1 (单张):
  │   P → Path A (vs 老相册)
  │     ├─ auto_merge / ask_user → 加入老相册 ✓
  │     └─ no_merge → Path C (vs 30 天 sediment)
  │                    ├─ create_new_album → 新建相册 ✓
  │                    └─ no_backfill / insufficient → P 沉淀
  │
  ├─ N=2 (双张):
  │   Path B light_judge
  │     ├─ show_inline_hint → 对话轻提示 (不进相册)
  │     └─ suppress → 沉淀
  │   (不走 A/C, PRD §3.2.2 决策; demo v0.1 不写测试)
  │
  └─ N ≥ 3 (多张):
      Path B 整批 (full_l2)
        ├─ show_mini_album → 创建新相册 (N 张全成集) ✓
        ├─ show_inline_hint → 对话轻提示 (不拆张)
        └─ suppress / F1 → 失败, 拆 N 张
              │
              ▼
            for each P_i in N 张 (顺序无所谓, 每张独立):
                Path A (vs 老相册)
                  ├─ auto_merge / ask_user → P_i 加入老相册 ✓
                  └─ no_merge → Path C (vs 30 天 sediment)
                                  ├─ create_new_album → P_i 起新相册 ✓
                                  └─ failed → P_i 进 sediment (并被后续 P_j cascade 自然召回)
```

### 2.2 · cascade_backfill 算法 (单次 P · PRD §3.10 校准)

> ⚠ **核心**: cascade 单次完全沿用现 `apply_backfill_caps` (PRD §3.10.5 三条门槛), 唯一新增 = 粗筛后**维度强度总分排序选 4 张**.

```python
def cascade_backfill_single(
    new_photo: L1Output,                     # 单张 P (cascade 一次只处理 1 张)
    sediment_pool: list[L1Output],           # 30 天 sediment 池 (全部, 不去重 sibling)
    scenario: str | None = None,
) -> BackfillDecisionLog:
    """PRD §3.10 标准 cascade backfill (单张 P)."""

    cfg = load_config("truth_table_backfill.yaml")

    # ─── Step 1 池规模上限 (PRD §3.10.10 风险 2) ───
    # demo v0.1 sediment 池 ≤ 50 张, 真实数据上线再调
    sediment_capped = sorted(
        sediment_pool, key=lambda p: p.captured_at, reverse=True
    )[:cfg["candidate_pool"]["max_sediment_size"]]

    # ─── Step 2 OR 粗筛 (PRD §3.10.5) ───
    # GPS<1km OR theme>0.5 OR event 一致, 全部纳入候选 (不在此截 5)
    candidates_raw = filter_backfill_or_coarse(
        new_photo, sediment_capped, cfg["coarse_filter"]
    )

    # ─── Step 3 维度强度总分排序选 4 张 (Ace 5/19 新增) ───
    # score = (gps<1km ? 1.0 : 0) + (theme>0.5 ? 1.0 : 0) + (event 一致 ? 0.5 : 0)
    # event 权重 0.5 因为 event_hint 封闭 10 枚举易重复, 语义弱
    candidates = rank_and_pick_top_n(
        new_photo,
        candidates_raw,
        n=cfg["max_recall_photos"],          # 4 (PRD §3.10.5)
        weights=cfg["priority_weight"],      # {gps: 1.0, theme: 1.0, event: 0.5}
    )

    # ─── Step 4 现 apply_backfill_caps (不变, PRD §3.10.5 三条门槛) ───
    # CAP-01 truth_table.bounds_max == strong
    # CAP-02 llm.proposed_strength == strong
    # CAP-03 recalled_photos >= 2
    truth_table, llm = evaluate_main_table(new_photo, candidates)
    caps_result = apply_backfill_caps(new_photo, candidates, truth_table, llm)

    # ─── Step 5 BackfillDecisionLog (新增 priority_ranking 落痕) ───
    return BackfillDecisionLog(
        decision_id=f"decb_{uuid()}",
        scenario=scenario,
        new_photo_id=new_photo.photo_id,
        coarse_filter_candidates=[p.photo_id for p in candidates_raw],
        priority_ranking=[                    # ← v0.3 新增
            {"photo_id": c.photo_id, "score": s} for c, s in ranked_with_scores
        ],
        recalled_photo_ids=[p.photo_id for p in candidates],
        main_truth_table_match=truth_table,
        llm_judgement=llm,
        backfill_caps_applied=caps_result.caps,
        final_decision=caps_result.decision,
    )
```

### 2.3 · 多张上传的 cascade dispatch (拆 N 张)

```python
def run_full_l2(new_photos, growing_albums, sediment_pool, scenario=None):
    N = len(new_photos)

    if N == 1:
        P = new_photos[0]
        growth_log = run_growth_path(P, growing_albums, scenario)
        if growth_log.tier in ("auto_merge", "ask_user"):
            return ArbitrationResult(winner="path_a", primary_album=..., ...)

        # A 失败 → C
        backfill_log = cascade_backfill_single(P, sediment_pool, scenario)
        return arbitrate_single_failed_a(growth_log, backfill_log)

    elif N == 2:
        l2_log = run_l2_path_b(new_photos, scenario)
        return arbitrate_l2_only(l2_log)
        # 不走 A/C; demo v0.1 不写测试

    else:  # N >= 3
        l2_log = run_l2_path_b(new_photos, scenario)
        if l2_log.success:
            return ArbitrationResult(winner="path_b", primary_album=..., ...)

        # B 失败 → 拆 N 张, 每张独立 A → C (顺序无所谓)
        growth_merges: list[GrowthMergeRecord] = []
        cascade_albums: list[Association] = []
        settled_photo_ids: list[str] = []

        for P_i in new_photos:
            g_log = run_growth_path(P_i, growing_albums, scenario)
            if g_log.tier in ("auto_merge", "ask_user"):
                growth_merges.append(GrowthMergeRecord(
                    photo_id=P_i.photo_id,
                    target_album_id=g_log.target_album_id,
                    decision_tier=g_log.tier,
                ))
                continue

            # A 失败 → 该张独立走 C
            b_log = cascade_backfill_single(P_i, sediment_pool, scenario)
            if b_log.final_decision.decision_tier == "create_new_album":
                cascade_albums.append(_album_from_backfill(P_i, b_log))
                # 该张 + 召回的 sediment 退出 sediment_pool (下一张 cascade 不再看)
                sediment_pool = [p for p in sediment_pool
                                 if p.photo_id not in b_log.recalled_photo_ids]
            else:
                settled_photo_ids.append(P_i.photo_id)
                sediment_pool.append(P_i)        # 进沉淀池, 下一张 cascade 可能召回

        return arbitrate_cascade(l2_log, growth_merges, cascade_albums, settled_photo_ids)
```

**关键不变量**:
1. 单张走 A → C, 多张走 B → 拆 N 张 A → C (每张独立)
2. cascade 单次完全沿用现 `apply_backfill_caps`, 三条 Caps strong-only
3. 召回上限 4 张 (PRD §3.10.5)
4. **维度强度总分排序选 4 张** (event 权重 0.5)
5. 顺序无所谓: 多张拆开后, P_i 走完 C 失败进 sediment_pool, P_j 处理时自然在池里, 不需要显式 "failed_siblings"
6. 召回的 sediment 在该批内不重复召回 (一张 sediment 最多被一个 cascade 召回)

### 2.4 · 维度强度总分排序 (核心新增)

```python
def rank_and_pick_top_n(new_photo, candidates, n, weights):
    """对粗筛候选按维度强度总分排序, 取 top N.

    weights = {"gps": 1.0, "theme": 1.0, "event": 0.5}   (config 来源)
    """
    scored = []
    for c in candidates:
        score = 0.0
        if gps_within_km(new_photo, c, 1.0):
            score += weights["gps"]
        if theme_jaccard(new_photo, c) > 0.5:
            score += weights["theme"]
        if c.semantic_facts.event_hint == new_photo.semantic_facts.event_hint \
           and c.semantic_facts.event_hint != "unknown":
            score += weights["event"]
        scored.append((c, score))

    # 总分降序, tie-breaker = captured_at 倒序 (最近优先)
    scored.sort(key=lambda x: (-x[1], -x[0].captured_at.timestamp()))
    return [c for c, _ in scored[:n]]
```

**排序示例** (n=4, 粗筛后 7 张候选):

| 候选 | gps<1km | theme>0.5 | event 一致 | score | 排名 |
|---|---|---|---|---|---|
| c1 | ✓ | ✓ | ✓ | 2.5 | 1 |
| c2 | ✓ | ✓ | ✗ | 2.0 | 2 |
| c3 | ✓ | ✗ | ✓ | 1.5 | 3 |
| c4 | ✗ | ✓ | ✓ | 1.5 | 4 (tie-broken by captured_at) |
| c5 | ✓ | ✗ | ✗ | 1.0 | 5 (丢弃) |
| c6 | ✗ | ✗ | ✓ | 0.5 | 6 (丢弃) |
| c7 | ✓ | ✗ | ✗ | 1.0 | 7 (丢弃) |

最终 cascade 看 [c1, c2, c3, c4] 4 张. event 单独命中 (c6) 因权重 0.5 排在所有 GPS / theme 命中候选后面.

---

## 三、变量定义

| 变量 | 定义 |
|---|---|
| `sediment_pool` | 30 天内 sediment 池 (未归相册的照片) |
| `sediment_capped` | sediment_pool 按 captured_at 倒序截最近 50 张 (demo v0.1) |
| `candidates_raw` | OR 粗筛后所有满足任一条件的候选 (可能 >5 张) |
| `candidates` | 维度强度总分排序 + 取 top 4 (PRD §3.10.5 召回上限) |
| `priority_ranking` | candidates_raw 全员的 score, 用于 log 落痕 |
| `recalled_photo_ids` | 最终 4 张候选的 photo_ids |

---

## 四、配置

### 4.1 · `config/truth_table_backfill.yaml` (回退 v0.1 + 新增 priority_weight)

```yaml
backfill:
  # 30 天窗口 + 粗筛 (PRD §3.10.5)
  lookback_days: 30
  coarse_filter:
    gps_max_km: 1.0
    theme_jaccard_min: 0.5
    match_event_hint: true

  # 召回上限 (PRD §3.10.5, v0.3 恢复)
  max_recall_photos: 4                       # 加 P 共 5 张 = PRD 标准

  # ─── v0.3 新增: 维度强度总分排序权重 (Ace 5/19) ───
  priority_weight:
    gps: 1.0
    theme: 1.0
    event: 0.5                               # event 封闭枚举易重复, 降权

  # 候选池上限 (demo v0.1, PRD §3.10.10 说 200 才换激进粗筛)
  candidate_pool:
    max_sediment_size: 50

  # 三条独立 Caps (PRD §3.10.5 strong-only, v0.3 完全保留)
  caps:
    require_truth_table_bounds_max_strong: true   # CAP-01
    require_llm_proposed_strength_strong: true    # CAP-02
    min_recalled_photos: 2                        # CAP-03 (PRD "至少召回 2 张")
```

### 4.2 · 跟 v0.2 配置对比

| 字段 | v0.2 状态 | v0.3 状态 |
|---|---|---|
| `caps.require_truth_table_bounds_max_strong` | 删除 | **保留** |
| `caps.require_llm_proposed_strength_strong` | 删除 | **保留** |
| `caps.min_recalled_photos` | 改名 → `min_recalled_photos` | **位于 caps 段, 保留原位** |
| `max_recall_photos` | 删除 (=4) | **保留** (=4) |
| `priority_weight` | 不存在 | **新增** (gps/theme=1.0, event=0.5) |
| `candidate_pool.max_sediment_size` | 50 | 50 (不变) |
| `candidate_pool.include_failed_siblings` | true | **删除** (无 sibling 机制) |

---

## 五、数据结构变更

### 5.1 · BackfillDecision (字段完全不变, v0.1 沿用)

```python
class BackfillDecision(BaseModel):
    backfill_decision_id: str
    new_photo_id: str
    decision_tier: Literal["create_new_album", "no_backfill", "insufficient_candidates"]
    recalled_photo_ids: list[str]                # ≤ 4 张 (PRD 上限)
    target_album_strength: BandLevel | None      # strong-only (PRD)
    primary_signal: str
    reason: str
```

### 5.2 · BackfillDecisionLog (字段微调)

```python
class BackfillDecisionLog(BaseModel):
    decision_id: str
    scenario: str | None
    new_photo_id: str
    coarse_filter_candidates: list[str]              # OR 粗筛后所有候选
    priority_ranking: list[PriorityRankingEntry]     # ← v0.3 新增, 落 score
    recalled_photo_ids: list[str]                    # 排序后 top 4
    main_truth_table_match: TruthTableMatch | None
    llm_judgement: LLMJudgement | None
    backfill_caps_applied: list[BackfillCap]         # ← v0.1 原字段, v0.3 完全保留
    final_decision: BackfillDecision

    # ─── v0.3 删除 (v0.2 加的, 现在作废) ───
    # embedded_path_b_log: DecisionLog | None       ← 不再嵌入 path B log
    # cascade_iteration: int | None                  ← 无 cascade 顺序处理, 不需要

class PriorityRankingEntry(BaseModel):
    """单候选的优先级排序详情 (落痕用)."""
    photo_id: str
    gps_within_1km: bool
    theme_jaccard_above_0_5: bool
    event_match: bool
    score: float                                     # 总分
    selected: bool                                   # 是否进入 top 4
```

### 5.3 · ArbitrationResult 支持多产物 (v0.2 保留)

```python
class ArbitrationResult(BaseModel):
    arbitration_id: str
    winner: ArbitrationWinner                    # 主要 album 来源
    ending: ArbitrationEnding
    primary_album: Association | None            # 主要相册 (单张 N=1 或多张 B 命中)

    # ─── v0.2 加, v0.3 保留 (多张拆 N 张需要多产物) ───
    cascade_albums: list[Association] = Field(default_factory=list,
        description="cascade backfill 产出的额外相册 (拆 N 张 → 多个 P_i 各自起 C 集)")
    settled_photo_ids: list[str] = Field(default_factory=list,
        description="未成集进 sediment 的 photo_ids")
    growth_merges: list[GrowthMergeRecord] = Field(default_factory=list,
        description="拆 N 张走 A 加入老相册的记录")
```

### 5.4 · GrowthMergeRecord (v0.2 保留)

```python
class GrowthMergeRecord(BaseModel):
    """单张照片加入老相册的记录."""
    photo_id: str
    target_album_id: str
    decision_tier: Literal["auto_merge", "ask_user"]
```

---

## 六、流程图 (实施视图)

```
run_full_l2(new_photos, growing_albums, sediment_pool):
  N = len(new_photos)

  if N == 1:
      P = new_photos[0]
      g_log = run_growth_path(P, growing_albums)
      if g_log.tier in (auto_merge, ask_user):
          return ArbitrationResult(winner="path_a", primary_album=...)

      b_log = cascade_backfill_single(P, sediment_pool)
      if b_log.final_decision.decision_tier == "create_new_album":
          return ArbitrationResult(winner="path_c", primary_album=新相册)
      return ArbitrationResult(winner="none", settled_photo_ids=[P.photo_id])

  elif N == 2:
      l2_log = run_l2_path_b(new_photos)
      return arbitrate_l2_only(l2_log)
      # PRD §3.2.2 + Ace decision: 不进 A/C, demo v0.1 不写测试

  else:  # N >= 3
      l2_log = run_l2_path_b(new_photos)
      if l2_log.success:
          return ArbitrationResult(winner="path_b", primary_album=...)

      # B 失败 → 拆 N 张, 每张独立 A → C
      growth_merges, cascade_albums, settled = [], [], []
      working_sediment = list(sediment_pool)       # 拷贝, 拆 N 张过程中可能动态增减

      for P_i in new_photos:
          g_log = run_growth_path(P_i, growing_albums)
          if g_log.tier in (auto_merge, ask_user):
              growth_merges.append(GrowthMergeRecord(...))
              continue

          b_log = cascade_backfill_single(P_i, working_sediment)
          if b_log.final_decision.decision_tier == "create_new_album":
              cascade_albums.append(_album_from(P_i, b_log))
              # 已召回的 sediment 退出池, 不重复召回
              working_sediment = [p for p in working_sediment
                                  if p.photo_id not in b_log.recalled_photo_ids]
          else:
              settled.append(P_i.photo_id)
              working_sediment.append(P_i)         # 该张进沉淀, 后续 P_j 可能召回

      return arbitrate_cascade(l2_log, growth_merges, cascade_albums, settled)
```

---

## 七、Case 验证

### Case A · 单张 → A 命中 (加入老相册)
```
N=1, P 跟老相册《西湖》匹配 strong → auto_merge
→ ArbitrationResult(winner="path_a", primary_album=《西湖》, cascade_albums=[])
```

### Case B · 单张 → A 失败 → C 命中 (新建相册)
```
N=1, P 跟所有老相册 no_merge
sediment 池 OR 粗筛后 7 张候选:
  c1 (gps✓+theme✓+event✓)=2.5  ← 选
  c2 (gps✓+theme✓)=2.0          ← 选
  c3 (gps✓+event✓)=1.5          ← 选
  c4 (theme✓+event✓)=1.5        ← 选 (tie-broken)
  c5 (gps✓)=1.0                  ← 丢
  c6 (event✓)=0.5                ← 丢
  c7 (gps✓)=1.0                  ← 丢
→ 召回 4 张: [c1, c2, c3, c4]
→ apply_backfill_caps: 主真值表 strong + LLM strong + recall=4 ≥ 2 → create_new_album
→ ArbitrationResult(winner="path_c", primary_album=新相册 5 张)
```

### Case C · 单张 → A C 都失败 (沉淀)
```
N=1, P 跟所有老相册 no_merge
sediment 池 OR 粗筛后只 1 张候选 (<2)
→ cascade_backfill_single insufficient_candidates → P 进 sediment
→ ArbitrationResult(winner="none", settled_photo_ids=[P])
```

### Case D · 多张 → B 命中 (新建相册)
```
N=5, B 整批 show_mini_album → 5 张全成集
→ ArbitrationResult(winner="path_b", primary_album=新相册 5 张, cascade_albums=[])
```

### Case E · 多张 → B 失败 → 3 张 A 命中 + 2 张走 C
```
N=5, B suppress
拆 5 张:
  P1 P2 P3 → A auto_merge 进《西湖》  → growth_merges=[3 条]
  P4 → A no_merge → C 跑 (sediment 池 50 张)
    粗筛 6 张候选, 排序选 top 4
    apply_backfill_caps strong + recall=4 → create_new_album {P4 + 4 张 sediment}
    cascade_albums=[新相册 5 张]
  P5 → A no_merge → C 跑 (sediment 池减 4 张, 剩 46 张)
    粗筛 2 张 (<4 但 ≥2), 排序后留 2 张
    apply_backfill_caps strong + recall=2 → create_new_album {P5 + 2 张}
    cascade_albums=[新相册 5 张, 新相册 3 张]

→ ArbitrationResult(
    winner="cascade",
    growth_merges=3,
    cascade_albums=[5 张, 3 张],
    settled_photo_ids=[],
  )
```

### Case F · 多张 → B 失败 → 全 A 失败 → 部分 C 命中
```
N=5, B suppress
拆 5 张, 全 A no_merge
  P1 → C: 粗筛 5 候选, top 4 strong → create_new_album {P1+4}, sediment 池减 4
  P2 → C: 粗筛 3 候选 (剩余池), top 3 → recall=3, strong → create_new_album {P2+3}
  P3 → C: 粗筛 0 候选 → insufficient → P3 进 sediment
  P4 → C: 粗筛 1 候选 (含 P3!), <2 → insufficient → P4 进 sediment
  P5 → C: 粗筛 2 候选 (含 P3 P4!), strong → create_new_album {P5+P3+P4} (3 张)

→ ArbitrationResult(
    winner="cascade",
    cascade_albums=[{P1+4}, {P2+3}, {P5+P3+P4}],   ← 3 个 cascade 相册
    settled_photo_ids=[],
  )
```

⚠ Case F 演示**沉淀池自然承接**: P3/P4 走 C 失败进 sediment, 处理 P5 时 P3/P4 已经在池里, 被 P5 的粗筛召回 → 三者一起成集. 不需要显式"失败兄弟"机制.

### Case G · 多张 → B 失败 → cascade 顺序 c5 c4 c3 c2 c1 (顺序无所谓验证)
```
N=5, B suppress, 顺序反过来跑:
  P5 P4 P3 P2 P1 任意顺序
→ 结果跟 Case F 等价 (因 cascade 单次 = strong + caps, 不依赖兄弟召回顺序)
```

### Case H · event 降权验证 (核心新 case)
```
N=1, P 跟所有老相册 no_merge
sediment 池 OR 粗筛后 5 张候选:
  c1 (event✓ daily_record): score=0.5    ← event 单独
  c2 (event✓ daily_record): score=0.5
  c3 (event✓ daily_record): score=0.5
  c4 (event✓ daily_record): score=0.5
  c5 (gps✓): score=1.0                    ← 排第 1
→ top 4 = [c5, c1, c2, c3] (tie-broken by captured_at)
→ 验证 4 张 event 一致但都被 c5 排第一; c4 因为相同 event 但更老被丢弃

⚠ 没 event×0.5 降权时, 5 张 event=1 都排前面, c5 反而垫底, GPS 强关联会被 event 噪音淹没.
```

---

## 八、不变性

1. **单张走 A → C, 多张走 B → 拆 N 张 A → C** (每张独立)
2. **N=2 走 light_judge**, 不走后续 A/C, demo v0.1 不测试
3. **cascade 单次完全沿用 v0.1 `apply_backfill_caps`** (PRD §3.10.5 三条 strong-only Caps)
4. **召回上限 4 张** (PRD §3.10.5)
5. **维度强度总分排序选 top N** (event 权重 0.5)
6. **沉淀池自然承接** (P_i 失败进 sediment, P_j 可召回, 不需要 sibling 机制)
7. **召回的 sediment 在该批内不重复**
8. **粗筛保留 OR** (GPS<1km / theme>0.5 / event 一致, PRD §3.10.5)
9. **多产物输出**: ArbitrationResult 含 primary_album + cascade_albums + growth_merges + settled_photo_ids
10. **不动 path B 真值表 28 条 / HR-PRE / HR-POST / LLM judge** (cascade 不调 `run_l2_path_b` 内核)
11. **不动 ADR-0005~0016** 任何维度算法

---

## 九、待决 OQ (本 spec)

### OQ-28a · ~~cascade 中"已处理但未成集" photos 怎么处理~~ (v0.2 加, v0.3 作废)
- v0.2 担心"失败兄弟召回顺序敏感", v0.3 删 sibling 机制后**问题消失**
- 沉淀池自然承接 (Case F), 顺序无所谓 (Case G)

### OQ-28b · cascade 中真值表 path 选择
- 现状: 复用 path B 主表 28 条 (A1-F1)
- v0.1 demo 不调, 真实数据后调
- **保留**

### OQ-28c · sediment 池 50 张是否够
- demo v0.1 50 张, PRD §3.10.10 说 100-150 张可能漏召回
- **保留**, v0.2 真实数据后调到 100 张

### OQ-28d · ~~顺序敏感性产品影响~~ (v0.2 加, v0.3 作废)
- v0.3 拆 N 张每张独立 cascade, 顺序无所谓

### OQ-28e · cascade 多产物频控
- 一次上传可能产出多个 cascade_albums (Case F: 3 个)
- PRD §3.10.7 "单用户单天最多 1 次成集通知"
- **保留**, v0.1 demo 不做, v0.2 加合并通知

### OQ-28f · event 降权权重 0.5 是否合适 (v0.3 新增)
- event_hint 10 枚举里 daily_record / outing / meal 占绝大多数, 命中"event 一致"概率高
- 0.5 权重让 event 单独命中候选**永远**排在任一 GPS / theme 命中候选之后
- 但 0.5 可能太低, event 命中 + GPS 命中 (1.5) = GPS + theme 命中 (1.0+1.0=2.0) 的 75%, 区分度还好
- 真实数据后调到 0.3 或 0.7 待观察
- **保留**, v0.2 真实数据后调

---

## 十、与已落 ADR 关系

| ADR | 关系 |
|---|---|
| ADR-0005 (path A DBCH) | 复用 (cascade 拆 N 张走 A) |
| ADR-0010 (path B location) | 复用 (B 整批跑) |
| ADR-0012 (path B event) | 复用 |
| ADR-0013/0014/0015 (path B theme/anchor/emotional) | 复用 |
| ADR-0016 (Geocoder 4 档) | 复用 |
| **ADR-0017 (本)** | (1) 改 pipeline 流程分流 (2) 新增维度强度总分排序选 4 张 (3) arbiter 多产物 |
| 现 path C (docs/05) | **小改**: 不动 caps + 真值表复用, 加 "维度强度排序选 4 张" 段 |

⚠ **v0.3 不动 `apply_backfill_caps`**, 也不动 path B 任何内核. ADR-0017 只是流程层 + 候选选择策略.

---

## 十一、实施清单 (12 步)

| Step | 动作 | 工程量 |
|---|---|---|
| 1 | 写 `decisions/0017-pipeline-cascade-backfill.md` (PRD §3.10 校准 + 维度强度排序决策) | 0.5 天 |
| 2 | 写 `docs/23_pipeline_cascade_backfill.md` | 0.5 天 |
| 3 | 改 `docs/02_data_contracts.md` (ArbitrationResult 扩 + BackfillDecisionLog 加 priority_ranking + GrowthMergeRecord + PriorityRankingEntry) | 0.3 天 |
| 4 | 改 `docs/05_truth_table_backfill.md` (保留 caps 章节 + 加"维度强度总分排序选 4 张"段) | 0.3 天 |
| 5 | 改 `docs/00/01/06/11/12` 跨文档矩阵 | 0.3 天 |
| 6 | 改 `config/truth_table_backfill.yaml` (恢复 caps + max_recall=4, 加 priority_weight + candidate_pool.max_sediment_size) | 0.2 天 |
| 7 | 改 `src/contracts/arbitration.py` (扩 cascade_albums + growth_merges + settled_photo_ids + GrowthMergeRecord) + `src/contracts/backfill.py` (加 priority_ranking + PriorityRankingEntry) | 0.4 天 |
| 8 | 改 `src/candidate_builder/backfill_scan.py` (粗筛 OR 不变 + 加 max_sediment_size 截 + rank_and_pick_top_n 新增) | 0.6 天 |
| 9 | `src/policy/backfill_engine.py`: **不动 apply_backfill_caps**, 只在 BackfillEngineResult 加 priority_ranking 字段透传 | 0.2 天 |
| 10 | 新增 `src/policy/cascade_backfill.py`: cascade_backfill_single (粗筛 → 排序选 4 → apply_backfill_caps → log 组装) | 0.6 天 |
| 11 | 改 `src/pipeline.py::run_full_l2` (单张/双张/N≥3 三路分流 + 多张 B 失败 → 拆 N 张 A → cascade_backfill_single) + `src/arbitration/merge_results.py::arbitrate` (扩多产物合并) | 1 天 |
| 12 | 单测 (维度排序 / event×0.5 / Caps 三条 / 多产物仲裁) + 新 scenarios (full_case5_dispatch / full_case6_priority_pick4 / full_case7_event_downweight / full_case8_cascade_partial) + 重生 golden + grep 自检 + 归档 spec → archive/specs/ | 1 天 |

**预估总量**: 6 天.

---

## 十二、待 Ace 最终审核 (v0.3)

1. **决策树** (§2.1) — 单张 / N=2 / N≥3 分流 OK?
2. **cascade_backfill_single 算法** (§2.2) — 粗筛 → 排序选 4 → apply_backfill_caps OK?
3. **维度强度总分排序** (§2.4) — score = gps(1) + theme(1) + event(0.5), tie-breaker 用 captured_at 倒序, OK?
4. **多张拆 N 张 dispatch** (§2.3) — 顺序无所谓 + 沉淀池自然承接 + 召回的 sediment 不重复 OK?
5. **`apply_backfill_caps` 不动** (§十) — v0.1 现有 Caps 完全保留, OK?
6. **ArbitrationResult 多产物** (§5.3) — cascade_albums + growth_merges + settled_photo_ids, OK?
7. **BackfillDecisionLog 加 priority_ranking** (§5.2) — PriorityRankingEntry 落痕粗筛后所有候选的 score, OK?
8. **OQ-28b/c/e/f 保留** (§九) — 重点 OQ-28f (event 0.5 权重) 等真实数据再调?
9. **N=2 不写场景测试** (§2.1) — 双张走 light_judge, demo v0.1 不测, OK?
10. **实施 6 天工程量** — 时间可接受?

---

## 十三、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-18 | 初版, Ace 拍板 6 个决策 + 单张/双张/多张 3 分流 + cascade 顺序处理 + 多产物合并 |
| v0.2 (draft) | 2026-05-18 | Ace 追加"回滚向 L2/L2.5 对齐": 删除 path C 独立 Caps (CAP-01/02/03) + cascade 单次改调 `run_l2_path_b` 内核 + BackfillDecisionLog 嵌 path B log; 配置删 caps 段, 实施清单 Step 9 改"删 apply_backfill_caps" |
| **v0.3 (draft)** | **2026-05-19** | **Ace 拍板 PRD §3.10 校准**: 整体回退 v0.2 "向 L2 对齐" 路线, 恢复 v0.1 `apply_backfill_caps` 三 Caps + 4 张召回上限 + strong-only; **删除 cascade 失败兄弟召回机制** (兄弟沉淀后自然在池里, Case F 演示); **新增维度强度总分排序选 4 张** + event 权重 0.5 (event_hint 封闭枚举易重复, 降权); BackfillDecisionLog 加 priority_ranking 落痕; N=2 不写场景测试; 实施 6 天 |
