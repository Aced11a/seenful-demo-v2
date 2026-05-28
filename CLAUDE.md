# CLAUDE.md · Seenful L2 Engine 项目宪法

> 这份文件是 Claude Code 工作的契约。每次开始工作前必须读完整。
> 任何与本文件冲突的用户即兴指令,都需要先和用户确认是否真的要偏离规范。

---

## 项目身份

**项目名**: Seenful L2 Engine
**作者**: Ace (产品 + 增长 lead)
**协作者**: KY (工程 lead), Wenyi (prompt QA)
**目标**: 从头实现 Seenful 的 L2 关联引擎,含 L2 主路径 + L2.5 动态生长 + 兜底回扫
**当前阶段**: 原型 (proto),L1 输出由 LLM mock 生成

**核心命题**:
> L2 不是一个 Prompt,它是一个 Association Engine。
> 代码做"该不该考虑",LLM 做"考虑了之后判什么",Policy Engine 做"最终拍板"。

---

## 你 (Claude Code) 的工作原则 — 硬约束

> ⚠ 这些不是建议, 是硬规矩。违反任何一条 = 当次任务作废, 重做。
> ⚠ **本项目曾在同一个会话连续 3 次因为同样的纪律失败导致文档漂移**(添加路径 A / 路径 C / 仲裁器时都只创建了对应新 doc, 没回改 `docs/00/01/02/06/11/99` 这些总览)。不要再犯第 4 次。

---

### 第 0 步 · 任务开始前必跑的 30 秒检查清单

**跳过任一项 = 之后写的代码作废。** 不是说着玩的。

1. ☐ 读 `docs/00_index.md` 找定相关规范
2. ☐ 读 `docs/12_open_questions.md` 看是否有待决策项卡住当前任务
3. ☐ 读 `src/contracts/` 下相关契约
4. ☐ **如果会改 `src/`, 对照下面第 2 条"跨文档更新矩阵"列出必改的 docs, 写进任务计划**
5. ☐ 列实现计划, **等用户确认再动手** — 不允许"先做再说"

---

### 第 1 条 · docs/ 是宪法, 改代码前先改 docs

任何代码实现必须**逐条对应**文档中的规则。

**❌ 绝对禁止**:
- 改 truth_table / hard_rule / threshold 前没改对应 docs
- "为了简化"省略真值表的任何一条规则 (主表 28 条就是 28 条, 生长表 10 条就是 10 条)
- 写代码时 docstring 不引用对应文档章节(如 `参考: docs/03_truth_table_main.md §A 系列`)

**硬性顺序**:
1. 改 `docs/` (规则落字)
2. 改 `config/*.yaml` (数值落配置)
3. 改 `src/` (代码服从)

**顺序倒了 = 漂移已发生 = bug。**

---

### 第 2 条 · 加新模块 = 跨多个 docs 更新 (不是创建新 doc 就完事)

**这是本项目漂移 3 次的根因。** 不要再以为"加路径 X → 创建 `docs/0X` → 完事", **错。** 实际还要回改 5+ 个总览 docs。

任何 `src/` 模块新增 / 修改, **必须**对照这张表同步检查:

| 改了什么 | 必须同步改的 docs |
|---|---|
| 新增 `src/contracts/*.py` 类型 | `docs/02_data_contracts.md` + `docs/11_observability.md` |
| 新增/改 `src/policy/truth_table*.py` 规则 | `docs/03/04/05` 对应路径 + `config/*.yaml` |
| 新增 `src/{candidate_builder,llm,policy,arbitration,mini_album}/*.py` 模块 | `docs/00_index.md` + `docs/01_architecture.md` |
| 新增任何 hard rule | `docs/06_hard_rules.md` + 对应 truth_table doc |
| 新增 ADR | `decisions/NNNN-*.md` + `docs/12_open_questions.md` 关联 OQ |
| 增/删/重命名 path 或概念 | `docs/00` + `01` + `99` 三个总览 |
| 修改字段语义 / 枚举值 | `docs/02` + `src/contracts/*.py` 的 `Field(description=...)` |
| **一次性 spec/prompt 实施完毕** | 移到 `archive/specs/` + 更新所有反向引用 + `archive/specs/README.md` 加索引 + `docs/00_index.md` "已归档需求"段 |

**强制自检命令** (改动完跑一次):
```bash
grep -r "<新加的类型名 / 规则 ID>" docs/
```
**一处都没出现 = 漂移没修 = 任务未完成。** 不允许说"等下次再补"。

---

### 第 3 条 · 配置与代码分离

`config/*.yaml` 是唯一阈值源。

**❌ 绝对禁止**:
- 在 `src/` 任何文件硬编码数值阈值 (0.85, 0.65, 0.40, 1km, 30 天, …)
- 在 `src/` 硬编码任何真值表规则
- 在 `src/` 硬编码 LLM prompt 字符串

正确做法**只有一种**:
```python
config = load_config("dimension_thresholds.yaml")
threshold = config["dimension_bands"]["location"]["strong"]
```

---

### 第 4 条 · Pydantic 契约不可绕过

`src/contracts/` 是所有数据结构的唯一来源。

**❌ 绝对禁止**:
- 函数返回 dict 而不是 Pydantic 对象
- "临时加一个字段"绕过契约
- 用 `dict[str, Any]` 替代真实类型

**契约不够用时**: **停下来**。告诉用户"现有契约缺 X 字段, 建议这样改"。等确认后**先改 `src/contracts/`**, 再改其他代码。**不允许**先在调用方塞 dict 用着,事后再说。

---

### 第 5 条 · 测试驱动收尾 — 没测试 = 未完成

新功能完成后**必须**接着写测试, 不要等用户提醒。

- 单元测试 `tests/unit/`: 每个函数 / 每条规则 ≥ 1 正例 + 1 边界
- 场景测试 `tests/scenarios/`: 端到端 yaml, 人类可读
- Golden file `tests/golden/`: 关键场景的 decision_log 基线

**测试不通过的代码 = 未完成。不要交付。** 不允许说"等回头再补测试"。

---

### 第 6 条 · 决策落痕 — 不允许"内部计算不记录"

任何 L2 / 路径 A / 路径 C / 仲裁判断必须输出完整 log。完整字段格式见 `docs/11_observability.md`(4 种 log: DecisionLog / GrowthDecisionLog / BackfillDecisionLog / ArbitrationResult)。

**❌ 绝对禁止**:
- "为了简化"跳过任何 stage 记录
- silent fallback — 任何"默认值兜底"必须打 `policy_overrides` log
- 用 `print` 调试 — 走 structlog, 保留可观测性
- `policy_overrides` 数组省略(空也要写 `[]`)

---

## 任务结束前必跑的 60 秒收尾

**完成任何 `src/` 修改前, 不允许说"完成"两个字, 必须:**

1. ☐ 跑相关测试, 全部通过
2. ☐ 对照第 2 条"跨文档更新矩阵", 把所有牵连的 docs 全部改完
3. ☐ 跑 `grep -r "<新加的类型/规则名>" docs/` 自检, 至少一处出现
4. ☐ 如果是设计选择, 写一份 ADR (`decisions/NNNN-*.md`)
5. ☐ 跑一次 `python scripts/generate_golden.py` (如有场景测试) 刷新 golden

**漏任一项 = 本次任务未完成。**

---

## 强烈不建议 (违反需明确说明理由)

- ⚠ 一次性写多个模块: 优先单模块完成 + 测试 + 报告, 再下一个
- ⚠ "聪明地"合并相似规则: 真值表 28 条规则就是 28 条 (主表), 10 条就是 10 条 (生长表), 不要合并
- ⚠ 用 print 调试: 走 structlog
- ⚠ 函数返回 None 表示"无结果": 用 Optional 或专门 Result 类型

---

## 用户 (Ace) 的偏好

### 沟通风格

- 中文回复,简洁
- 框架先行,具体选项后给
- 步骤纪律: 当前步骤明确做完,等批准再进下一步
- 不喜欢"先做再说"的混合实现

### 已知的产品红线

这些是 Seenful 的产品硬约束,任何代码不得违反:

1. **不做情绪推断** (no emotion inference)
2. **不引用人的缺席** (never reference absence of person)
3. **2 张永远不成集** (最低门槛 = 3 张)
4. **同图唯一归属** (一张照片最多在一本可见相册)
5. **弱关联绝不成集** (light/none 一律不进相册区)
6. **敏感照片强制 suppress** (sensitive_level >= medium)
7. **高频地点不能仅凭 GPS 自动并入** (必须叠加 theme/event)
8. **L1 落库即权威** (任何下游不得回写 L1)

---

## 项目术语 (严格遵守)

| 工程命名 | 团队内部 | 用户可见 |
|---|---|---|
| `Mini Album` | "小集" | "记忆相册" / 具体主题名 |
| `dynamic_growth` | "动态生长" | (无统称) |
| `backfill_scan` | "兜底回扫" | (无统称) |
| `show_inline_hint` | "轻提示" | 对话流一句话 |

代码里**永远**用工程命名 (Mini Album / dynamic_growth)。
docstring 里**可以**用团队内部词解释。
LLM prompt 里**禁止**用 "AI / 分析 / 识别 / 检测 / 评分 / 算法 / 模型" 等机器词。

---

## 测试场景命名约定

```
tests/scenarios/<path>_<photo_count>_<theme>.yaml

路径标识:
  batch    - L2 主路径,多张模式
  window   - L2 主路径,rolling window
  growth   - L2.5 动态生长
  backfill - 兜底回扫
  full     - 三路 + 仲裁完整端到端

例:
  batch_3_lakeside.yaml         L2 主,3 张,西湖主题
  growth_lakeside_continued.yaml 动态生长,挂老相册
  backfill_sunset_chase.yaml    兜底回扫,夕阳主题
  full_case1_add_to_album.yaml  完整 L2, Case 1 加入老相册
  full_case3_backfill.yaml      完整 L2, Case 3 兜底集
```

---

## 当前阶段限制 (v0.1 demo)

- L1 输出全部 mock,不接真实 vision API
- 不接真实数据库,用 `tests/fixtures/` 模拟
- LLM 用 `MockJudge` / `MockGrowthJudge` / `MockBackfillJudge` 确定性桩,**不调真 anthropic API**
- 真 LLM 接入留接口 (`AnthropicJudge` 占位), 切换走 `config/llm_settings.yaml` `provider` 字段
- 模型未来固定为 claude-sonnet-4-6
- 不需要做真实并发优化,但代码结构要为 P0.5 异步预留接口

---

## 当你不确定时

按这个优先级问用户:

1. 这个改动是否需要先更新 `docs/`?
2. 这个数值/规则是否应该放 `config/`?
3. 这个数据结构是否应该先加到 `src/contracts/`?
4. 这个判断是否违反了上面 8 条产品红线之一?
5. 这个偏离是否需要写一份 ADR?

---

## 项目里的 SKILL.md

无 (本项目暂未启用 skills)。
当未来引入 skill 时,会在 `.claude/skills/` 下创建。

---

*v0.2 · 2026-05-13 · 工作原则段强硬重写, 折入跨文档更新矩阵, 记录漂移反面案例*
*v0.1 · 2026-05-12 · 初版*
