# 99 · 术语表

| 工程命名 | 团队内部 | 用户可见 | 含义 |
|---|---|---|---|
| `Mini Album` | 小集 | "记忆相册" / 具体标题 | 多张照片成集后的产物 |
| `L1` | L1 | (无) | 单图理解 |
| `L2` | L2 | (无) | 多图关联判断,即本引擎 |
| `dynamic_growth` | 动态生长 / L2.5 | (无统称) | 新照片挂到老相册 |
| `backfill_scan` | 兜底回扫 | (无统称) | 救活沉淀单图 |
| `show_inline_hint` | 轻提示 | 对话流一句话 | 弱关联的展示形式 |
| `show_mini_album` | (无) | 圆圈相册 | 中以上强度的展示形式 |
| `suppress` | (无) | 无感处理 | 静默,不展示 |
| `Candidate Builder` | (无) | (无) | Step 1,决定是否进 L2 |
| `Feature Assembler` | (无) | (无) | Step 2,算 7 维客观分数 |
| `Policy Engine` | Policy Engine | (无) | 分档 + 真值表 + 硬规则 + 最终裁决 |
| `LLM Judge` | (无) | (无) | Step 4,语义复核 |
| `Arbitration` | 仲裁器 | (无) | 三路汇合后的严格优先级裁决 |
| `Case 1-4` | (无) | (无) | 仲裁器的 4 种命中分支 |
| `ending` | 结局 | (无) | 仲裁器输出的最终行为(加入老相册/新建小集/兜底集/沉淀) |

## 强度分级

| 强度 | 含义 | display |
|---|---|---|
| `strong` | 强关联 | show_mini_album |
| `medium` | 中等关联 | show_mini_album |
| `weak` / `light` | 弱关联 | show_inline_hint |
| `none` | 无关联 | suppress |

注:`weak` 和 `light` 在不同上下文混用。代码内部统一用 `weak` 作为 BandLevel 枚举,真值表 bounds 用 `light` 同义。v0.1 统一写 `weak`。

## 维度分组

- **主载体** (main signal,单独足以构成关联): location / theme / event / people
- **放大器** (amplifier,单独不构成): time
- **辅证** (auxiliary,修饰作用): anchor / emotional

## 路径

- **路径 A** = dynamic_growth (动态生长) ✅ — 把照片挂到老相册, **任意上传张数**都可触发(只要用户有 growing_albums)
- **路径 B** = L2 主路径 (batch / window) ✅ — 当前批次成新集, **由上传张数门控**(≥3 张才进 B)
- **路径 C** = backfill_scan (兜底回扫) ✅ — 救活沉淀单图, **真兜底**(仅在 A+B 都未产出相册时触发)
- **仲裁器** = arbitration ✅ — 4 个 Case 严格优先级 A > B > C

⚠ A 和 B **不是并列竞争**, 是按上传场景分工。C **不是并行跑**, 是 A+B 失败后的兜底。

## 仲裁器术语

| 术语 | 含义 |
|---|---|
| `Case 1` | 路径 A 命中, B/C 全部作废 |
| `Case 2` | A 未命中 + B 命中, C 作废 |
| `Case 3` | A + B 都未命中 + C 命中 |
| `Case 4` | 三路全空 → 单图沉淀 |
| `ending` | 仲裁器输出的最终行为(6 种枚举) |
| `discarded_paths` | 命中后被作废的路径(例: Case 1 时为 ["path_B","path_C"]) |
| `策略 3 禁用` | 不允许 A 命中时把沉淀单图搭车并入(避免相册边界漂移) |
