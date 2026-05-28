# CLAUDE.md · `api_harness/` 子项目宪法

> 这份文件治理 `api_harness/`(后端 API E2E 测试台)。每次在本文件夹动手前必须读完。
> 与根 `D:\seenful_demo_v2\CLAUDE.md` **不冲突也不覆盖**:根宪法治理 `src/` L2 引擎;本文件只治理 `api_harness/`。
> 凡与根宪法冲突的地方,以"边界条款"明确写出(见第 0 条)。

---

## 子项目身份

- **名**:Backend API E2E 测试台
- **目的**:用 mock L1 输入调**后端同事的真实 L2 API**(HTTP + 落库 + 有状态),验证后端决策是否符合产品预期
- **作者**:Ace **·** API 提供方:后端同事 **·** prompt/规则参照:根项目 docs
- **阶段**:需求对齐中,`SPEC.md` 草案 v0.1
- **唯一设计源**:`api_harness/SPEC.md`

---

## 硬约束(违反 = 当次任务作废,重做)

### 第 0 条 · `src/` 与现有 tests/ 只读不改 ← 边界条款

- api_harness **不得修改** `../src/` 任何文件,也不改 `../tests/personas/*.yaml` 原始数据。
- 需要契约/场景就 **读 / import**,绝不回写。
- 复用 76 persona 场景:把它们"翻译"成 timeline 的工作**只在 api_harness 内做**,产物落在 `api_harness/timelines/`。

### 第 1 条 · `SPEC.md` 是宪法,改代码前先改 spec

- 任何 `client / adapter / timeline / runner / dashboard` 的**行为变化**,先改 `SPEC.md`,再改代码。
- 硬性顺序:`SPEC.md` → `reference/` 或 `config` → 代码。**顺序倒了 = 漂移。**

### 第 2 条 · 跨文档更新矩阵(api_harness 版)

加/改任何东西,对照这张表同步检查(本项目在根目录漂移过 3 次,别在这里重蹈):

| 改了什么 | 必须同步改 |
|---|---|
| L1 字段映射 | `SPEC.md` §5 + `reference/l1_standard_sample.json` + `adapter.py` |
| API 端点 / 认证 | `SPEC.md` §1 + `config.py`(密钥走 env,见第 3 条) |
| 决策枚举 / 比对层级 | `SPEC.md` §6 + `runner.py` + `gen_dashboard.py` |
| 场景 schema(每场景隔离 session) | `SPEC.md` §3 + `cases/**/*.yaml` + `runner.py` |
| 新增/改场景用例 | `SPEC.md` §4 + `TEST_PLAN.md` §5 + 对应 `cases/**/*.yaml` |
| 场景可跑性分类(✅/🟡/⛔) | `TEST_PLAN.md`(逐条) + `SPEC.md` §4/§7(策略) |
| open item 解决 | `SPEC.md` §9 划掉该项 + 落实到对应章节 |

### 第 3 条 · 密钥只走环境变量

- 非密配置(endpoint URL、`x-gateway-checked: 1` 这类网关 header)可写进 `config.py`。
- **密钥 / token / 鉴权值只从环境变量读**(如 `os.environ[...]`),**绝不写进任何受版本控制的文件**。`results/` 落盘前也要脱敏。

### 第 4 条 · 不改题目 · 不替后端改规则

- `expected` 是**产品意图基准**。后端结果 ≠ expected → **照实标 mismatch**,不准为了好看改 expected(改 expected 让它"通过" = 改题目 = 作废)。
- 后端逻辑是后端同事的,本台子**只观测 + 比对**,不在台子里"修正"后端行为。
- 多值期望 / acceptable 兜底是已授权机制(`[ask_user, no_merge]` 任一通过,意图 no/auto 但结果 ask_user 记 acceptable);但**绝不允许把 no → merge 方向放宽**。
- **bug / 偏差先留着可见**,定位根因优先,不偷偷抹平。

### 第 5 条 · 有状态隔离纪律

- 单库自动累积(开发环境单用户,不传 userId);API#3 默认是 **per-mockBizId 级联删除**(2026-05-28 airtight 实测:`del(其他id)` 不动 X、`del(X)` 才删 X)。Ace 与后端确认"可清数据库,后端或有额外配置",两种模式并存。
- **严格串行**:开发环境单库共享,不能并行(若后端开整库 wipe 开关,并行会互相清掉)。**每场景一个隔离 session**:`(L2.5/cascade)setup 现建前置 → trigger → 取结果 → teardown 逐个删本场景所有 mockBizId`。
- **runner 用 per-id 账本 teardown**——两种模式下都正确(per-id 在 wipe-all 下也工作,只是多调用几次)。
- ⚠ **若后端整库 wipe 开关开启**:harness 跑动时**不能同时手动测后端**,任意一方的 del 会清对方数据。
- **失败归因**:L2.5/cascade 的 trigger 不对时先看 setup——前置建集没成 → 标 **BLOCKED**,**不算 mismatch**;前置成了仍判否 → 才是真 mismatch。

### 第 6 条 · L1 单一事实源

- 新 L1 字段标准的**权威样例只放** `reference/l1_standard_sample.json`。`adapter.py` 与 `SPEC.md` 都引用它,**不在多处各写一份**。
- 发现后端新 L1 与此样例有出入 → **先问 Ace**,改完同步样例文件 + `SPEC.md` §5。

---

## L1 字段对齐(已决 · 2026-05-27)

- **A**:`face_count` 放**顶层**,`semantic_facts` 不再含它。
- **B(替换/改写,已定稿)**:
  - `theme_tags` → **`ai_scene_tags`,值翻成中文**(参与主题维度;经 `reference/theme_tag_zh_map.json` 翻译表,Step 2 建)。
  - `salient_objects` **← `semantic_facts.main_subjects`** 复制(参与 subject 维度)。
- **C**:全新字段 mock 占位;`safety_flags` 布尔用**字符串**(`"false"` / `sensitive_level:"none"`);同义 tag 命名以新 L1 样例为准。
- **D**:**GPS / 高频地点 / `captured_at` 当前微信小程序环境拿不到 → 一律不传**。
  - location + time 维度测试**本轮不做**,但 HTML 必须列出"**将来拿到地理信息后要补的 location/time 测试**"。
- **emotional_tone**:与 `color_mood`(画面色调)语义重叠;Ace 定**旧氛围词/样例情绪词两种风格都可参考**,adapter 任填其一,本台子不判其对错。

---

## 术语(沿用根项目,严格遵守)

`Mini Album` = 小集;`L2` 主路径 / `L2.5` 动态生长 / `cascade` 兜底回扫。
LLM / prompt 机器词禁忌沿用根项目(禁 AI/分析/识别/检测/评分/算法/模型)。

---

## 当你不确定时,按优先级问 Ace

1. 这改动是否要先改 `SPEC.md`?
2. 这是不是在**改题目**(动了 `expected`)?
3. 这密钥是不是漏写进文件了?
4. 这失败是真 mismatch 还是 **BLOCKED**(前置没成)?

---

*v0.1 · 2026-05-27 · 初版,随 SPEC.md 草案建立*
