# 09 · 三路仲裁器

> 三条路径(A 动态生长 / B L2 主路径 / C 兜底回扫) 的结果汇合后由仲裁器决定最终走哪一条。
> 来源: Seenful_L1_L2_Full_Decision_Flow.md §三路结果汇合
> 配合 docs/01_architecture.md "上传张数分流 + C 真兜底" 流程图阅读。

## 设计哲学

```
策略优先级: 续旧 > 拼新窗口 > 救沉淀 > 沉淀
含义:       A    > B      > C    > 单图沉淀
```

**已有小集的身份连续性 > 新建任何东西**。

## ⚠ C 是"真兜底", 不是"并行跑然后被作废"

PRD 字面"asyncio.gather 三路并行"是实现层效率优化, 但语义上:
- A 和 B 是**主路径**, 按上传张数分工 (单张走 A / 多张走 B / 多张+有老相册 A+B 都跑)
- **C 仅在 A 和 B 都没产出相册时才被触发**, 不是与 A/B 并行
- 这是为了避免: 用户照片明明已经被 A 加入老相册了, C 还重复"拯救"过去单图导致相册边界漂移

实现上 (`src/pipeline.py::run_full_l2`):

```python
# A 和 B 按条件跑
if growing_albums:
    growth_log = run_growth_path(...)
if len(new_photos) >= 3:
    l2_log = run_l2_path_b(...)

# C 真兜底: 只在 A+B 都失败时跑
a_succeeded = growth_log and growth_log.final_decision.decision_tier in ("auto_merge", "ask_user")
b_succeeded = l2_log and l2_log.final_decision.association.display_decision == "show_mini_album"
if not a_succeeded and not b_succeeded and sedimented_pool:
    backfill_log = run_backfill_path(...)
```

仲裁器收到的 `backfill_log` 在 Case 1/2 应该是 `None`(C 根本没跑),不是"跑了被作废"。

## 严格优先级 (4 个 Case)

### Case 1: 路径 A 命中 (auto_merge / ask_user)

→ 走策略 1: 加入老小集
→ B/C 处理:
  - B 可能跑过(如果上传 ≥3 张), 但被仲裁丢弃 (写入 `discarded_paths`)
  - C **从未跑** (因 A 已成功, 不触发兜底)
→ ending = `add_to_existing_album` (auto_merge) or `ask_user_confirm` (ask_user)

### Case 2: A 未命中 + B 命中 (show_mini_album)

→ 走 B: 创建新小集 (同窗口照片)
→ C **从未跑** (因 B 已成功)
→ ending = `create_new_album_path_b`

### Case 3: A 未命中 + B 未命中(suppress) + C 命中 strong

→ 走策略 2: 创建兜底集 (新照片 + 召回的 2-4 张沉淀单图)
→ ending = `create_new_album_backfill`

### Case 4: 三路全空

→ 单图沉淀,喜宝不做提示 (无感处理)
→ ending = `single_photo_sediment`

## 策略 3 禁用 (强化解释)

❌ **不允许搭车并入**:
- 路径 A 命中, 同时把沉淀单图也搭车并入老相册 → 禁
- 理由: 避免相册边界漂移和身份稀释

实现层有两重保险:
1. **C 不跑** (因 A 已成功, 真兜底条件不满足)
2. 即使因 race condition C 也跑了 (asyncio 并发场景), 仲裁器仍丢弃 C 结果 (`discarded_paths` 含 "path_C")

## A.ask_user 用户拒绝后

⚠️ 用户拒绝并入提示后:
- 该照片**单图沉淀**(不重新走任务 C)
- 写入候选老相册 `excluded_photo_ids`
- 避免循环

v0.1 不模拟用户响应, ask_user 的最终 ending 标记为 `ask_user_pending`。

## 触发输入

仲裁器输入:
- `GrowthDecisionLog | None` — 路径 A 输出 (None = A 未触发, 无候选相册)
- `DecisionLog | None` — 路径 B 输出 (None = 上传 < 3 张, B 未触发)
- `BackfillDecisionLog | None` — 路径 C 输出 (None = A 或 B 已成功, C 未触发, 这是常态)

入口条件汇总:

| 场景 | A | B | C |
|---|---|---|---|
| 单张上传 + 无老相册 + 无沉淀 | 跳过 | 跳过 | 跳过 |
| 单张上传 + 无老相册 + 有沉淀 | 跳过 | 跳过 | 跑(因 A 跳过, B 跳过, C 是唯一可能) |
| 单张上传 + 有老相册 | 跑 | 跳过 | 仅当 A 失败才跑 |
| 多张 (≥3) + 无老相册 | 跳过 | 跑 | 仅当 B 失败才跑 |
| 多张 (≥3) + 有老相册 | 跑 | 跑 | 仅当 A 和 B 都失败才跑 |

## 输出契约

```python
class ArbitrationResult(BaseModel):
    arbitration_winner: Literal["path_A", "path_B", "path_C", "none"]
    ending: Literal[
        "add_to_existing_album",      # Case 1 auto_merge
        "ask_user_confirm",            # Case 1 ask_user
        "create_new_album_path_b",     # Case 2
        "create_new_album_backfill",   # Case 3
        "single_photo_sediment",       # Case 4
        "ask_user_pending",            # 兼容标识
    ]
    target_album_id: str | None
    target_album_strength: str | None
    user_facing_message: str          # 喜宝话术

    # 留痕字段
    discarded_paths: list[str]         # ["path_B"] (跑过但被作废); C 未跑则不计入
    case_matched: str                  # "Case 1" / "Case 2" / "Case 3" / "Case 4"
```

⚠ `discarded_paths` 仅包含**跑过但被仲裁丢弃**的路径。C 因 A/B 成功而**未触发**时, **不计入 discarded**(它本来就没跑)。

## 喜宝话术映射

| ending | 喜宝话术 |
|---|---|
| add_to_existing_album | "那本《X》又添了一笔" |
| ask_user_confirm | "这张和《X》有点接得上,要不要放进去?" |
| create_new_album_path_b | "我给你留在一起了" / "这几张接得上,我帮你收好了" |
| create_new_album_backfill | "这几张拼起来,像是一段日子" |
| single_photo_sediment | (无话术, 无感处理) |
