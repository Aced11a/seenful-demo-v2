# 05 · 兜底回扫真值表 (路径 C)

> 救活 30 天内沉淀单图。复用主真值表 + 兜底专用封顶规则。
> 配置: `config/truth_table_backfill.yaml`
> 来源: Seenful_L1_L2_Full_Decision_Flow.md 路径 C

## 与路径 B 的关系

| | 路径 B (新窗口成集) | 路径 C (兜底救活) |
|---|---|---|
| 输入 | 当前窗口的新照片 (≥2 张) | 1 张新照片 + 30 天内沉淀单图候选 |
| 候选集 | 当前窗口 | 历史沉淀单图 (uploaded_at >= NOW - 30d) |
| 真值表 | 主表 A-F1 完整 | **复用主表**, 但加封顶 |
| LLM prompt | 标准 | 追加"兜底场景"特殊指引 |
| 最终结局 | show_mini_album / show_inline_hint / suppress | create_new_album / no_backfill |

## 候选集构建 (Step 1)

```sql
-- 概念 SQL,实际由 candidate_builder/backfill_scan.py 实现
SELECT * FROM photos
WHERE uploaded_at >= NOW() - INTERVAL 30 DAY
  AND sensitive_level < 'medium'
  AND photo_id NOT IN (SELECT photo_id FROM mini_album_photos)
  AND is_deleted = false
  AND backfill_excluded_global = false
```

## 粗筛 (Step 2,代码层,不调 LLM)

任一条件命中即视为潜在关联候选:

- GPS 距离 < 1 km (相对新照片)
- theme_tags Jaccard > 0.5
- event_hint 一致 (且非 unknown)

> ⚠ **ADR-0017 升级**: cascade_backfill_single (新入口) 不再在此截 5 张, 改为粗筛保留所有候选 → 维度强度总分排序选 top 4. 老入口 `run_backfill_path` 保留 `max_candidates=5` 截断行为, 兼容老 scenarios.

## 维度强度总分排序选 top 4 (ADR-0017 新增)

粗筛后所有候选**按维度强度总分排序**, 取 top 4 (PRD §3.10.5 召回上限):

```
score = (gps<1km ? 1.0 : 0) + (theme>0.5 ? 1.0 : 0) + (event 一致 ? 0.5 : 0)
```

| 字段 | 权重 | 理由 |
|---|---|---|
| GPS<1km | 1.0 | 强空间关联 |
| theme jaccard>0.5 | 1.0 | 强主题关联 |
| event 一致 | **0.5** | event_hint 封闭 10 枚举, 命中概率高但语义弱 |

**tie-breaker**: 总分相同 → captured_at 倒序 (最近优先).

权重在 `config/truth_table_backfill.yaml::priority_weight` 配置, 调优转 [OQ-028f](./12_open_questions.md).

详见 [docs/23_pipeline_cascade_backfill.md](./23_pipeline_cascade_backfill.md).

## 复用主真值表 (Step 3)

把 "新照片 + 召回沉淀单图" 视作整体,塞进主真值表流程:
- 复用 `features/assemble.py` 算 7 维
- 复用 `policy/bands.py` 分档
- 复用 `policy/truth_table.py` 查表(A-F1 全集)
- 复用 `llm/judge.py` 复核

## 兜底专用 LLM prompt 追加

LLM system prompt 在路径 B 基础上追加:

> 这是兜底回扫场景,沉淀单图可能跨多天甚至数周。
> 只在你确定它们属于同一段连续记忆时给 strong,
> 其他情况都给 medium 或更低。

v0.1 mock 阶段:`MockBackfillJudge` 始终返回 `proposed_strength = bounds_min`,与路径 B 一致。

## 兜底专用 Policy Engine 封顶 (Step 4)

**只有同时满足三条**才允许新建兜底集 (`create_new_album`):

1. 主真值表 `bounds_max = strong` (即命中 A 系或 B7/B8/B9)
2. LLM `proposed_strength = strong`
3. 召回沉淀单图 ≥ 2 张 (加新照片共 ≥ 3 张,满足最低成集门槛)

任一未满足 → `decision_tier = no_backfill`,新照片继续走仲裁器走单图沉淀流程。

成立时,最多取**前 4 张**沉淀单图 (配置项 `backfill.max_recall_photos`) + 新照片,共 ≤ 5 张组新集。

## 输出契约

```python
class BackfillDecision(BaseModel):
    backfill_decision_id: str
    new_photo_id: str
    decision_tier: Literal["create_new_album", "no_backfill", "insufficient_candidates"]
    recalled_photo_ids: list[str]
    target_album_strength: BandLevel | None       # 命中时的强度
    primary_signal: str
    reason: str
```

## 决策落痕 (BackfillDecisionLog)

```json
{
  "decision_id": "decb_xxx",
  "path_taken": "path_C",
  "new_photo_id": "photo_xxx",
  "candidates_after_coarse_filter": ["photo_a", "photo_b", ...],
  "main_truth_table_match": "A1",
  "llm_judgement": { ... },
  "backfill_caps_applied": [
    { "rule": "BACKFILL-CAP-01-bounds_max",      "passed": true },
    { "rule": "BACKFILL-CAP-02-llm_strength",    "passed": true },
    { "rule": "BACKFILL-CAP-03-recall_count_2",  "passed": true }
  ],
  "final_decision": { ... BackfillDecision ... }
}
```

## 与仲裁器交互

兜底回扫产物在三路仲裁器中:
- **Case 3** 才被采纳: 路径 A + B 都没命中 + 路径 C `decision_tier = create_new_album`
- 否则作废(即使强成集)。这是"避免相册边界漂移"的产品红线。

## A.ask_user 用户拒绝后

如果路径 A 命中 `ask_user`,用户拒绝并入,新照片**不再走兜底回扫**:
- 写入候选老相册的 `excluded_photo_ids`
- 直接单图沉淀
- 这是 PRD §策略 3 禁用的延伸:避免循环

由仲裁器在 `Case 1 (ask_user_declined)` 路径处理,v0.1 简化:不模拟用户响应,只展示算法层逻辑。
