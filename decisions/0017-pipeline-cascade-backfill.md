# ADR-0017 · Pipeline 流程分流 + Cascade Backfill 校准 PRD §3.10

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-19 |
| 决策人 | Ace — 拍板 PRD §3.10 校准 / 拆 N 张分流 / 维度强度总分排序 / event 0.5 权重 / N=2 不测试 |
| 影响范围 | 改 `src/pipeline.py::run_full_l2` (单/双/多张三路分流) + 新增 `src/policy/cascade_backfill.py` + 改 `src/candidate_builder/backfill_scan.py` (加 max_sediment_size + rank_and_pick_top_n) + 透传 `src/policy/backfill_engine.py::BackfillEngineResult.priority_ranking` + 改 `src/contracts/{arbitration,backfill}.py` (扩多产物 + 加 priority_ranking) + 改 `src/arbitration/merge_results.py` (支持多产物) + 新增 `config/truth_table_backfill.yaml::priority_weight + candidate_pool.max_sediment_size` + 新增 `docs/23_pipeline_cascade_backfill.md`; 改 `docs/{00,01,02,05,06,11,12}` |
| 相关文档 | `docs/23_pipeline_cascade_backfill.md`; `Pipeline_Cascade_Backfill_Spec.md` v0.3 (设计来源, 实施完后归档) |
| 关联 OQ | 新增 [OQ-028](../docs/12_open_questions.md#oq-028-pipeline-cascade-backfill-边界) (含 OQ-28b/c/e/f, 重点 OQ-28f event 权重 0.5 调优) |
| 关联 ADR | **扩展** [ADR-0005](./0005-place-anchor-dbch.md) (path A 在拆 N 张时复用) + [ADR-0010~0016](./0010-path-b-location-dbch-pca-shape.md) (path B 复用); **不动**任何维度算法 ADR; **不 supersede** 现 path C (现 `apply_backfill_caps` 保留) |

---

## 1 · 背景

### 1.1 · 现状失败模式

`src/pipeline.py::run_full_l2` 当前流程:

```
路径 A (任意张数, 仅 primary_photo)
路径 B (≥3 张)
路径 C 真兜底 (A B 都失败 + sediment 池非空, 仅 primary_photo)
```

| 问题 | 后果 |
|---|---|
| 多张上传, B 失败后**只对 primary_photo 跑 C**, 其他 N-1 张直接沉淀 | 错过"3 张并入老相册 + 2 张走 C 救活"的机会 |
| N=1 单张走 B 路径但 B 需要 ≥3 张 (pre_filter 直接 reject) | 单张没机会走完整 A→C 链 |
| Path C 仅对 primary_photo, 不支持"沉淀池自然承接"多次 cascade | 多张 B 失败时大量照片无法救活 |

### 1.2 · v0.2 漂离教训

v0.2 spec 把 cascade "向 L2 对齐" 过度解读成:
- 删除 `apply_backfill_caps` 整函数
- cascade 单次改为整套调 `run_l2_path_b([P, *候选])`
- 失败兄弟互为候选

读 PRD v1.1 §3.10 后发现 cascade 应该**比 path B 更严格** (strong-only + 4 张上限), v0.2 方向**完全作废**.

### 1.3 · Ace 拍板路线 (2026-05-19)

1. **整体回退**: 恢复 `apply_backfill_caps` 三 Caps + 4 张召回上限 + strong-only (PRD §3.10.5)
2. **只对 30 天 sediment 召回**: 删除"失败兄弟互为候选" (兄弟沉淀后下次 cascade 自然在池里)
3. **优先级方案 A + event 降一级**: 维度强度总分排序选 top 4, 权重 gps=1.0 / theme=1.0 / **event=0.5** (event_hint 封闭 10 枚举易重复)
4. **N=2 不写场景测试**: 双张走 light_judge, demo v0.1 不测

---

## 2 · 决策

### 2.1 · Pipeline 三路分流

```
N=1 单张:  P → A → C → 沉淀
N=2 双张:  Path B light_judge, 不走 A/C (PRD §3.2.2, demo v0.1 不测)
N≥3 多张:  Path B 整批
             ├─ 命中 → 新相册
             └─ 失败 → 拆 N 张, 每张独立 A → C
```

### 2.2 · cascade_backfill_single 算法

```python
def cascade_backfill_single(new_photo, sediment_pool, scenario) -> BackfillDecisionLog:
    # Step 1 池规模上限 (demo v0.1 最近 50 张)
    sediment_capped = sorted_recent_n(sediment_pool, cfg.max_sediment_size)

    # Step 2 OR 粗筛 (PRD §3.10.5, 不在此截 5)
    candidates_raw = filter_or(new_photo, sediment_capped)

    # Step 3 维度强度总分排序选 top 4 (核心新增)
    candidates = rank_and_pick_top_n(
        new_photo, candidates_raw,
        n=cfg.max_recall_photos,                  # 4
        weights={"gps": 1.0, "theme": 1.0, "event": 0.5},
    )

    # Step 4 现 apply_backfill_caps (不动, PRD §3.10.5 strong-only)
    truth_table, llm = evaluate_main_table(new_photo, candidates)
    caps_result = apply_backfill_caps(new_photo, candidates, truth_table, llm)

    return BackfillDecisionLog(..., priority_ranking=..., caps_applied=caps_result.caps, ...)
```

### 2.3 · 多张 B 失败 → 拆 N 张

```python
# B 失败后拆 N 张, 每张独立 A → C
working_sediment = list(sediment_pool)         # 拷贝, 动态增减
for P_i in new_photos:
    g_log = run_growth_path(P_i, growing_albums)
    if g_log.tier in ("auto_merge", "ask_user"):
        growth_merges.append(GrowthMergeRecord(...))
        continue
    b_log = cascade_backfill_single(P_i, working_sediment)
    if b_log.final_decision.decision_tier == "create_new_album":
        cascade_albums.append(_album_from(P_i, b_log))
        working_sediment -= b_log.recalled_photo_ids  # 退出池, 不重复召回
    else:
        settled.append(P_i)
        working_sediment.append(P_i)                  # 进沉淀, 后续 P_j 可召回
```

**顺序无所谓**: P_i 失败进 sediment, P_j 自然在池里; 不需要显式 sibling 机制.

### 2.4 · 维度强度总分排序 (核心新增)

```python
def rank_and_pick_top_n(new_photo, candidates, n, weights):
    scored = []
    for c in candidates:
        score = 0.0
        if gps_within_km(new_photo, c, 1.0):
            score += weights["gps"]                # 1.0
        if theme_jaccard(new_photo, c) > 0.5:
            score += weights["theme"]              # 1.0
        if event_match(new_photo, c):
            score += weights["event"]              # 0.5
        scored.append((c, score))

    # 总分降序, tie-breaker = captured_at 倒序 (最近优先)
    scored.sort(key=lambda x: (-x[1], -x[0].captured_at.timestamp()))
    return [c for c, _ in scored[:n]]
```

排序示例 (n=4, 粗筛后 7 张):

| 候选 | gps<1km | theme>0.5 | event 一致 | score | 排名 |
|---|---|---|---|---|---|
| c1 | ✓ | ✓ | ✓ | 2.5 | 1 |
| c2 | ✓ | ✓ | ✗ | 2.0 | 2 |
| c3 | ✓ | ✗ | ✓ | 1.5 | 3 |
| c4 | ✗ | ✓ | ✓ | 1.5 | 4 |
| c5 | ✓ | ✗ | ✗ | 1.0 | 5 (丢) |
| c6 | ✗ | ✗ | ✓ | 0.5 | 6 (丢) |
| c7 | ✓ | ✗ | ✗ | 1.0 | 7 (丢) |

---

## 3 · 关键设计点

### 3.1 · `apply_backfill_caps` 完全保留

| Cap | 检查 | PRD 出处 |
|---|---|---|
| CAP-01 | `truth_table.bounds_max == strong` | §3.10.5 "兜底回扫: strong 以上" |
| CAP-02 | `llm.proposed_strength == strong` | §3.10.5 LLM 复核 |
| CAP-03 | `recalled_photos >= 2` | §3.10.4 "至少召回 2 张沉淀单图(总数 ≥ 3 张)" |

三条 Caps 是 PRD §3.10.5 strong-only 门槛的代码体现, **不删不改**.

### 3.2 · 多产物 ArbitrationResult

| 字段 | 来源 |
|---|---|
| `primary_album` | N=1 单张走 A→C 命中 / 多张 B 整批命中 |
| `cascade_albums` | 多张 B 失败拆 N 张后, 各 P_i 各自 cascade 命中 (可能 0~N 个相册) |
| `growth_merges` | 多张 B 失败拆 N 张后, 各 P_i 走 A 命中 (加入老相册) |
| `settled_photo_ids` | 拆 N 张后 A/C 都失败的 photos |

### 3.3 · BackfillDecisionLog 加 priority_ranking

新增 `PriorityRankingEntry` 落痕粗筛后**所有候选**的 score, 用于审计 + 真实数据调优:

```python
class PriorityRankingEntry(BaseModel):
    photo_id: str
    gps_within_1km: bool
    theme_jaccard_above_0_5: bool
    event_match: bool
    score: float
    selected: bool
```

### 3.4 · 不动 path B / path A / 维度算法

ADR-0017 是**流程层 + 候选选择策略**改造, 不动:
- 真值表 28 条 (主表 + 生长表)
- HR-PRE / HR-POST
- LLM judge (主 + 生长 + 兜底)
- 任何维度算法 (ADR-0010~0016)

---

## 4 · 替代方案 (评估后未采用)

### 4.1 · v0.2 路线: 删 Caps + 调 `run_l2_path_b` 内核
- **作废**: PRD §3.10.5 明确 cascade 比 path B 更严格 (strong-only), 不该向 B 全套对齐
- K_outer 散沙判定也会让 mixed 候选无法成集

### 4.2 · Cluster-first: sediment 池建多维簇
- **作废**: 簇大小 = 3 张 (成集门槛), 摊销不出来 + 簇形成本身难
- 工程量 +7.5 天 (v0.4-lite) 或 +14 天 (完整版), 收益在 demo 阶段看不出来

### 4.3 · Tier-based: 多 tier 单维粗筛 + 每 tier 跑 B
- **作废**: 最坏 3 次 B 内核 + 3 次 LLM 调用, 平均 1.5×, 算力翻倍
- 而且没解 PRD §3.10.5 strong-only 门槛诉求

### 4.4 · Subset 分组 (P-centric pairwise 维度强度)
- **作废**: 不解 strong-only 诉求 (PRD 要求门槛比 B 严), subset 内仍按 B 内核判 medium 可能成集

最终采纳**方案 A · 维度强度总分排序**: 简单可解释, 跟 PRD §3.10.5 "粗筛 5 张候选 → 单次召回上限 4 张" 自然衔接, 工程量最低.

---

## 5 · 实施清单

详见 `Pipeline_Cascade_Backfill_Spec.md` v0.3 §十一, 共 12 步, 6 天工程量:

1. ADR-0017 (本文档) + docs/23
2. docs/02/05/00/01/06/11/12 同步
3. config/truth_table_backfill.yaml 恢复 caps + 加 priority_weight
4. src/contracts/arbitration.py (多产物) + backfill.py (priority_ranking)
5. src/candidate_builder/backfill_scan.py (max_sediment_size + rank_and_pick_top_n)
6. src/policy/backfill_engine.py (透传 priority_ranking)
7. src/policy/cascade_backfill.py (新增 cascade_backfill_single)
8. src/pipeline.py (run_full_l2 三路分流 + 拆 N 张)
9. src/arbitration/merge_results.py (多产物合并)
10. 单测 + 4 个新 scenarios + 重生 golden + grep 自检 + 归档 spec

---

## 6 · 验证

### 6.1 · Case 验证 (spec §七 8 个 cases)

- Case A-C: 单张 A→C 三种结局
- Case D-F: 多张 B 命中 / 拆 N 张 / 部分救活
- Case G: 顺序无所谓 (反序跑等价于 Case F)
- Case H: event 0.5 权重生效 (4 张 event 一致但 GPS 弱, 排在 1 张 GPS 命中之后)

### 6.2 · 跨文档自检

- `grep -r "cascade_backfill_single" docs/` 至少一处
- `grep -r "priority_ranking" docs/` 至少一处
- `grep -r "PriorityRankingEntry" docs/` 至少一处

---

## 7 · 关联

**ADR**:
- 扩展 [ADR-0005](./0005-place-anchor-dbch.md) (path A 在拆 N 张时复用)
- 扩展 [ADR-0010~0016] (path B 复用)
- 不 supersede 任何 ADR

**docs**:
- [docs/23_pipeline_cascade_backfill.md](../docs/23_pipeline_cascade_backfill.md) (本算法实施文档)
- [docs/05_truth_table_backfill.md](../docs/05_truth_table_backfill.md) (path C 真值表, 保留)
- [docs/09_arbitration.md](../docs/09_arbitration.md) (仲裁器多产物扩展)
- [docs/02_data_contracts.md](../docs/02_data_contracts.md) (新增 cascade_albums / growth_merges / PriorityRankingEntry)

**OQ**:
- [OQ-028](../docs/12_open_questions.md#oq-028-pipeline-cascade-backfill-边界) (含 OQ-28b/c/e/f)
- 重点 OQ-28f: event 0.5 权重真实数据调优

**原始 spec** (实施完后归档):
- `Pipeline_Cascade_Backfill_Spec.md` v0.3 → `archive/specs/`
