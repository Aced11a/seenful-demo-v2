# Seenful L2 Engine · 项目结构与文档管理规范

> 适用范围：L2 主路径 + L2.5 动态生长 + 兜底回扫的从头实现项目
> 工作流：vibe coding (Claude Code) + 规范驱动开发 + 测试先行
> 维护者：Ace

---

## 一、目录结构

```
seenful-l2-engine/
│
├── README.md                         # 项目入口,30 秒看懂这是什么
├── CLAUDE.md                         # ★ 给 Claude Code 看的项目宪法
├── .gitignore
├── pyproject.toml                    # 依赖管理
├── pytest.ini                        # 测试配置
│
├── docs/                             # ★ 规范层 (代码必须服从)
│   ├── 00_index.md                   # 文档索引,所有规范文档的目录
│   ├── 01_architecture.md            # 四层架构总览 + 数据流图
│   ├── 02_data_contracts.md          # 所有数据结构定义 (L1 / Features / Bands / Decision)
│   ├── 03_truth_table_main.md        # 主真值表 (A1-F1 + G 系列)
│   ├── 04_truth_table_growth.md      # 动态生长真值表 (G-A1 ~ G-F1)
│   ├── 05_truth_table_backfill.md    # 兜底回扫规则
│   ├── 06_hard_rules.md              # 全路径硬规则
│   ├── 07_dimension_thresholds.md    # 维度分档阈值 + 各信号计算公式
│   ├── 08_llm_prompts.md             # LLM Judge prompt 完整版本
│   ├── 09_arbitration.md             # 三路仲裁器逻辑
│   ├── 10_mini_album_schema.md       # 小集数据结构 + 指纹生成规则 ⚠ 你要补的
│   ├── 11_observability.md           # 日志、留痕、可观测字段
│   ├── 12_open_questions.md          # ★ 待决策清单 (实现中遇到的歧义都记这)
│   └── 99_glossary.md                # 术语对照 (Mini Album / 小集 / 记忆相册)
│
├── src/                              # 代码层
│   ├── __init__.py
│   ├── contracts/                    # 数据契约 (Pydantic models)
│   │   ├── __init__.py
│   │   ├── l1_output.py              # L1Output, SemanticFacts
│   │   ├── features.py               # FeaturePackage, Bands
│   │   ├── decision.py               # AssociationDecision, GrowthDecision
│   │   └── mini_album.py             # MiniAlbum, PlaceAnchor
│   │
│   ├── candidate_builder/            # Step 1
│   │   ├── batch_window.py           # batch_upload / rolling_window
│   │   ├── growth_scan.py            # dynamic_growth 候选
│   │   └── backfill_scan.py          # 兜底回扫候选 + 粗筛
│   │
│   ├── features/                     # Step 2
│   │   ├── location.py
│   │   ├── time.py
│   │   ├── theme.py
│   │   ├── event.py
│   │   ├── people.py
│   │   ├── anchor.py
│   │   └── emotional.py
│   │
│   ├── policy/                       # Step 3 + 5 (Policy Engine)
│   │   ├── bands.py                  # 维度分档
│   │   ├── truth_table.py            # 主真值表查询
│   │   ├── truth_table_growth.py     # 动态生长真值表
│   │   ├── truth_table_backfill.py   # 兜底真值表
│   │   ├── hard_rules.py             # 全路径硬规则
│   │   └── engine.py                 # Policy Engine 主流程
│   │
│   ├── llm/                          # Step 4
│   │   ├── judge.py                  # L2 LLM Judge
│   │   ├── synthesis.py              # L2 综述生成
│   │   ├── growth_judge.py           # 动态生长 LLM 复核
│   │   └── mock.py                   # ★ L1 mock 生成器 (你的主输入源)
│   │
│   ├── arbitration/                  # 三路仲裁器
│   │   └── merge_results.py
│   │
│   ├── mini_album/                   # 小集组装
│   │   ├── place_anchor.py           # DBCH 算法 (ADR-0005, v0.1 档位 ADR-0007 统一)
│   │   ├── theme_aggregation.py      # theme 语义簇聚合 + 匹配 (ADR-0008)
│   │   ├── low_quality_place.py      # 高频低质量地点降档 (ADR-0006)
│   │   └── user_home_city.py         # context 判定 stub (OQ-010)
│   │
│   └── pipeline.py                   # 全链路入口 (orchestrator)
│
├── config/                           # ★ 配置层 (热更新)
│   ├── dimension_thresholds.yaml     # 7 维分档阈值
│   ├── truth_table_main.yaml         # 主真值表
│   ├── truth_table_growth.yaml       # 动态生长真值表
│   ├── truth_table_backfill.yaml     # 兜底真值表
│   └── llm_settings.yaml             # 模型选择 / 温度 / token 上限
│
├── tests/                            # ★ 测试层
│   ├── conftest.py
│   ├── unit/                         # 单元测试 (每个 feature / 每条真值表行)
│   │   ├── test_features_location.py
│   │   ├── test_features_theme.py
│   │   ├── test_truth_table_main.py
│   │   ├── test_truth_table_growth.py
│   │   └── test_hard_rules.py
│   │
│   ├── scenarios/                    # ★ 场景测试 (端到端,人类语义可读)
│   │   ├── README.md                 # 场景测试规范
│   │   ├── batch_3_lakeside.yaml     # "西湖的午后" 经典正例
│   │   ├── batch_3_random.yaml       # 三张随机照片应 suppress
│   │   ├── growth_lakeside_continued.yaml
│   │   ├── growth_high_freq_home.yaml
│   │   ├── backfill_sunset_chase.yaml
│   │   └── ...
│   │
│   ├── golden/                       # ★ Golden file (回归基线)
│   │   ├── batch_3_lakeside.expected.json
│   │   ├── batch_3_random.expected.json
│   │   └── ...
│   │
│   ├── fixtures/                     # 测试夹具 (mock L1 输出)
│   │   ├── photos/                   # 命名: <scene>_<id>.l1.json
│   │   │   ├── lakeside_p001.l1.json
│   │   │   ├── lakeside_p002.l1.json
│   │   │   ├── home_meal_p001.l1.json
│   │   │   └── ...
│   │   └── albums/                   # 已有小集 (动态生长测试用)
│   │       └── lakeside_album.json
│   │
│   └── eval/                         # ★ 评估集 (跑 metric)
│       ├── run_eval.py               # 跑全套场景 → 出报表
│       ├── eval_cases.yaml           # 50-100 个评估用例
│       └── reports/                  # 每次跑出的报表 (gitignore)
│
├── scripts/                          # 工具脚本
│   ├── mock_l1.py                    # 用 LLM 给一张照片描述生成 L1 输出
│   ├── new_scenario.py               # 从 yaml 模板新建场景
│   └── dump_decision_log.py          # 把决策日志格式化输出
│
└── decisions/                        # ★ ADR (Architecture Decision Records)
    ├── 0001-use-pydantic-for-contracts.md
    ├── 0002-llm-provider-choice.md
    ├── 0003-fingerprint-static-vs-dynamic.md  # 你之前问的指纹更新策略
    └── ...
```

---

## 二、五条核心原则

### 1. 规范先于代码 (docs/ 是宪法)

**写代码前先写规范**。每一条真值表规则、每一个维度阈值，先在 `docs/` 里写明白，再让 Claude Code 实现。

**反模式**：直接让 Claude 写一个"差不多的 truth_table"，然后边跑边改。结果是 3 周后没人知道当前真值表和原始规范偏差有多大。

**正确做法**：
```
1. 在 docs/03_truth_table_main.md 里写完整真值表 (从你已有的工程规范 v1.3.1 拷过来)
2. 在 config/truth_table_main.yaml 里写配置版本
3. 让 Claude 实现 src/policy/truth_table.py,要求逐条对照 docs 和 config
4. 在 tests/unit/test_truth_table_main.py 里逐条写测试
5. 任何修改: 先改 docs → 改 config → 改 code → 跑测试
```

### 2. 数据契约用 Pydantic 锁死

`src/contracts/` 里用 Pydantic 定义所有数据结构。一旦定义，所有模块严格遵守。

```python
# src/contracts/l1_output.py 示例
from pydantic import BaseModel, Field
from typing import Literal

class SemanticFacts(BaseModel):
    main_subjects: list[str] = []
    scene_type: Literal["home", "park", "travel", "restaurant",
                        "street", "indoor", "outdoor", "unknown"] = "unknown"
    activity: Literal["walk", "meal", "gathering", "sightseeing",
                      "gardening", "resting", "unknown"] = "unknown"
    people_presence: Literal["none", "single", "group",
                             "family_like", "unknown"] = "unknown"
    face_count: int = 0
    object_anchors: list[str] = []
    place_category: Literal["home_area", "scenic_spot", "community",
                            "road", "restaurant", "unknown"] = "unknown"
    # ADR-0009: 10 枚举 (6→10), 删 family_visit/festival, 新增 6 个
    event_hint: Literal[
        "meal", "outing", "gathering", "celebration",
        "performance", "sports", "work", "study",
        "daily_record", "unknown",
    ] = "unknown"

class L1Output(BaseModel):
    photo_id: str
    individual_title: str = Field(..., min_length=2, max_length=10)
    individual_understanding: str = Field(..., min_length=60, max_length=120)
    meaning_anchors: list[str]
    meaning_density: float = Field(..., ge=0.0, le=1.0)
    aesthetic_density: float = Field(..., ge=0.0, le=1.0)
    theme_tags: list[str]
    emotional_tone: str
    semantic_facts: SemanticFacts
    # ... captured_at / exif_location / sensitive_level 等
```

**这层契约的作用**：让 Claude vibe coding 时不能"随便加字段",必须先改契约再改代码。

### 3. 配置和代码分离 (yaml 驱动)

所有阈值、真值表、prompt 全部放 `config/`,代码层读取。改阈值不改代码。

```yaml
# config/dimension_thresholds.yaml
dimension_bands:
  location:
    strong: 0.85
    medium: 0.65
    weak: 0.40
  theme:
    strong: 0.75
    medium: 0.55
    weak: 0.30
  # ... 其他维度

main_signals: ["location", "theme", "event", "people"]
amplifier_signals: ["time"]
auxiliary_signals: ["anchor", "emotional"]

high_frequency_place_downgrade: true
```

**好处**：测试不同阈值组合时,只改 yaml,跑 eval 出报表,不动一行代码。

### 4. 场景测试是最重要的资产

`tests/scenarios/` 里每个 yaml 是一个**人类可读的场景**。这是上线后调优的核心资产 —— 任何 bad case 都先抽象成一个 yaml 场景。

```yaml
# tests/scenarios/batch_3_lakeside.yaml
name: "三张西湖照片应成集 (经典正例)"
trigger: "batch_upload"
upload_mode: "multi_select"

photos:
  - fixture: "lakeside_p001"  # 引用 tests/fixtures/photos/lakeside_p001.l1.json
  - fixture: "lakeside_p002"
  - fixture: "lakeside_p003"

expected:
  arbitration_winner: "path_B"  # L2 评估胜出
  display_decision: "show_mini_album"
  truth_table_match: "A1"        # location 强
  final_strength: "strong"
  mini_album:
    theme_mode: "location"
    dominant_theme: null
    place_anchor:
      is_high_frequency_anchor: false

notes: |
  这是最基础的正例。三张照片 GPS 都在西湖 500m 内,
  非高频地点,主题"湖边/夕阳"中等重合。
  应命中 A1 (location 强),strong 成集,主题模式 location。
```

**核心思想**:这些 yaml 是产品逻辑的"事实陈述",代码改了也得保证这些 yaml 不破。

### 5. 决策落痕 + Golden File 回归

每次跑都产出完整决策日志,关键场景生成 golden file 做回归。

```python
# 跑出来的决策日志 (落库 + 测试都用)
{
  "decision_id": "dec_xxx",
  "scenario": "batch_3_lakeside",
  "path_taken": "path_B",
  "stages": {
    "step1_candidates": {"path_hint": "full_l2", "photo_count": 3},
    "step2_features": {"location": 0.92, "theme": 0.55, ...},
    "step3_bands": {"location": "强", "theme": "中", ...},
    "step4_truth_table": {"matched": "A1", "bounds": ["medium", "strong"]},
    "step5_llm": {"proposed_type": "location", "proposed_strength": "strong", ...},
    "step6_final": {"strength": "strong", "display": "show_mini_album"},
  },
  "policy_overrides": [],
  "final_album": {...}
}
```

任何 PR 都跑场景测试,decision_log 和 golden file 不匹配就 fail。改了 golden 必须在 PR 描述里说明为什么。

---

## 三、CLAUDE.md (项目宪法)

这个文件放仓库根目录,Claude Code 会自动读取。**这是控制 vibe coding 漂移的最关键手段。**

模板见下一段。

---

## 四、文档生命周期管理

| 文档类型 | 何时创建 | 何时更新 | 何时归档 |
|---|---|---|---|
| `docs/` 规范 | 项目开始 | 任何规则修改前 | 永久,但需版本号 |
| `decisions/` ADR | 遇到重大设计选择时 | 永不修改,只能 supersede | 永久保留 |
| `docs/12_open_questions.md` | 实现中遇到歧义时 | 持续 | 解决后转 ADR |
| `tests/scenarios/` | 新场景出现时 | 通过 PR 流程 | 永久 |
| `decisions/` 中已 supersede 的 ADR | - | - | 标记 superseded,保留文件 |

### Open Questions 模板

`docs/12_open_questions.md` 是 vibe coding 时最有用的文件。每遇到一个"文档没说清楚"的问题就记一条:

```markdown
## OQ-001: place_anchor.gps_center 用几何中心还是 meaning_density 加权?

**状态**: 进行中
**发现时间**: 2026-05-13
**发现场景**: 实现 src/mini_album/fingerprint.py 时
**问题**:
  PRD 只说"成集时算 GPS 中心",未说明算法。
  几何中心:简单,但被噪点(误差 GPS)拉偏
  加权中心:更稳,但增加复杂度

**临时决策**: 用几何中心,标记为 TODO
**影响范围**: 动态生长匹配准确度
**待决策人**: Ace
**关联代码**: src/mini_album/fingerprint.py:42
```

解决后转成 ADR(decisions/0003-fingerprint-gps-center.md),保留追溯链。

---

## 五、Vibe Coding 工作流

### 第 1 步:启动新功能前

每次让 Claude 实现一个模块,先确认这三件事:

```
1. docs/ 里相关规范是否完整? 不完整先补
2. src/contracts/ 里数据契约是否定义? 没定义先定义
3. tests/scenarios/ 里有没有覆盖这个模块的场景? 至少要有 1 个正例 + 1 个反例
```

### 第 2 步:让 Claude Code 工作时

每次 prompt 都要带:

```
请实现 src/policy/truth_table.py 的 truth_table_lookup 函数。

要求:
1. 严格对照 docs/03_truth_table_main.md 的真值表
2. 配置从 config/truth_table_main.yaml 读取,不要硬编码
3. 输入输出严格遵守 src/contracts/decision.py 的 TruthTableMatch
4. 覆盖所有模式: A1-A4, B1-B9, G1-G4, C1-C4, D1-D4, E1-E2, F1
5. 命中优先级按文档顺序: A > B > G > C > D > E > F1

请先列出你的实现计划,我确认后再写代码。
不要跳过任何模式,不要"为了简化"合并相似规则。
```

### 第 3 步:测试驱动收尾

让 Claude 写完代码,**永远**接着让它写测试:

```
现在请为 truth_table_lookup 写单元测试,覆盖:
1. 每条规则至少 1 个正例
2. 每条规则至少 1 个边界 (刚好触发 vs 刚好不触发)
3. 模式优先级 (B1 vs C1 同时满足时应命中 B1)
4. F1 兜底

测试用 pytest parametrize,数据驱动。
```

### 第 4 步:跑场景测试验证

```bash
pytest tests/scenarios/ --decision-log-dir=./logs/
```

每个场景跑出来都对比 golden file,失败的人工审查决定是 bug 还是预期变更。

---

## 六、Git Commit 约定

```
feat(truth-table): 实现主真值表 A 系列
fix(features): location 高频地点降档计算错误
docs(open-questions): 新增 OQ-007 关于辅证 ±0.5 档语义
test(scenarios): 新增"杭州一日游"G1 evidence 质量门槛测试
chore(config): 调整 location 强档阈值 0.85 → 0.90
refactor(policy): 抽离 bands 计算到独立模块
```

阈值调整必须用 `chore(config):` 前缀,这样后期能从 git log 直接看到所有阈值变更历史。

---

## 七、推荐工具栈

| 用途 | 选择 | 理由 |
|---|---|---|
| 包管理 | `uv` 或 `poetry` | 比 pip 稳 |
| 数据校验 | Pydantic v2 | 契约层标配 |
| 测试 | pytest + pytest-yaml | scenarios 直接读 yaml |
| 配置 | PyYAML + 单例 ConfigLoader | 支持热更新 |
| LLM | anthropic SDK (你已在用) | 兼容 Claude Code 工作流 |
| 日志 | structlog | 结构化日志,decision_log 直接可解析 |
| 类型检查 | mypy 或 pyright | vibe coding 必备,catch Claude 偷懒 |
| 代码风格 | ruff | 一个工具搞定 lint + format |

---

## 八、第一周建议节奏

| Day | 任务 | 产出 |
|---|---|---|
| 1 | 项目脚手架 + CLAUDE.md + 数据契约 | 跑得起来的空架子 |
| 2 | docs/ 规范文档全部从已有 PRD/工程规范 拷贝整理 | docs/ 完整版 |
| 3 | config/ 全部 yaml + 配置加载器 | 配置驱动跑通 |
| 4 | mock_l1.py + 10 张 fixture 照片 | 测试燃料就绪 |
| 5 | Features 7 维计算 + 单元测试 | features 模块完成 |
| 6 | Policy Engine 主真值表 + 单测 | 主路径骨架 |
| 7 | 第一个端到端场景跑通 + golden file | 闭环验证 |

L2.5 和兜底回扫放到第 2-3 周,先把主路径走通。

---

*v0.1 · 2026-05-12 · 配合 Seenful_L1_L2_Full_Decision_Flow.md 食用*
