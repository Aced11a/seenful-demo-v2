# Seenful L2 Engine · Demo

L2 关联引擎原型 · 三路 + 仲裁完整链路。

## 一分钟跑通

```bash
# 1. 装依赖 (只需一次)
pip install pydantic pyyaml pytest

# 2. 跑全套测试 (应该 272 passed)
python -m pytest -q

# 3. 看 demo 输出 (按场景分组,带喜宝话术)
python scripts/run_demo.py --summary       # 摘要版本
python scripts/run_demo.py                 # 完整决策日志版本

# 4. 看可用场景列表
python scripts/run_demo.py --list

# 5. 跑单个场景
python scripts/run_demo.py full_case1_add_to_album
```

## 核心命题

> L2 不是一个 Prompt,它是一个 Association Engine。
> 代码做"该不该考虑",LLM 做"考虑了之后判什么",Policy Engine 做"最终拍板"。

## 三条路径 + 一个仲裁

```
┌────────────────────────────────────────────────────────────────────┐
│ 用户上传 1-N 张照片                                                │
└────────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
       ┌─────────┐       ┌─────────┐       ┌──────────┐
       │ 路径 A  │       │ 路径 B  │       │  路径 C  │
       │ 动态生长 │       │ L2 主   │       │ 兜底回扫 │
       │ (L2.5)  │       │ (batch) │       │  (P0.5)  │
       └─────────┘       └─────────┘       └──────────┘
            │                 │                  │
            └─────────────────┼──────────────────┘
                              ▼
                     ┌────────────────┐
                     │  三路仲裁器     │
                     │  A > B > C     │
                     │  严格优先级     │
                     └────────────────┘
                              │
                ┌─────────────┼──────────────┐
                ▼             ▼              ▼              ▼
         加入老相册      新建小集         新建兜底集      单图沉淀
         (Case 1)       (Case 2)        (Case 3)       (Case 4)
```

## 4 种最终结局 (对应 4 个 full_l2 场景)

| 场景 yaml | 结局 | 触发条件 |
|---|---|---|
| `full_case1_add_to_album` | 加入老相册《西湖的午后》 | 新照片 + 已有可生长老相册 + 命中 A1 |
| `full_case2_new_album` | 新建小集 | 3 张同窗口新照片 + 无老相册 |
| `full_case3_backfill` | 新建兜底集 | 1 张新夕阳 + 沉淀池里 3 张过往夕阳 |
| `full_case4_sediment` | 单图沉淀 | 1 张毫无关联的餐厅照片 |

## 项目结构

```
seenful_demo_v2/
├── docs/                       规范层 (代码必须服从)
│   ├── 00_index.md             所有规范的目录
│   ├── 01_architecture.md      四层架构 + 数据流
│   ├── 02_data_contracts.md    数据契约定义
│   ├── 03_truth_table_main.md  主真值表 28 条
│   ├── 04_truth_table_growth.md 动态生长真值表 10 条
│   ├── 05_truth_table_backfill.md 兜底回扫规则
│   ├── 06_hard_rules.md        全路径硬规则
│   ├── 07_dimension_thresholds.md 维度阈值 (v1.3.2 新方案)
│   ├── 09_arbitration.md       三路仲裁器
│   ├── 11_observability.md     决策落痕规范
│   ├── 12_open_questions.md    Open Questions
│   └── 99_glossary.md          术语表
│
├── decisions/                  ADR (Architecture Decision Records)
│   └── 0004-feature-assembler-revision.md
│
├── src/
│   ├── contracts/              Pydantic 数据契约
│   ├── candidate_builder/      候选集构建 (growth_scan / backfill_scan)
│   ├── features/               7 维特征计算
│   ├── policy/                 真值表 + 硬规则 + Policy Engine
│   ├── llm/                    LLM Judge (v0.1 mock)
│   ├── arbitration/            三路仲裁
│   └── pipeline.py             全链路 orchestrator (run_l2_path_b / run_growth_path / run_backfill_path / run_full_l2)
│
├── config/                     配置层 (热更新)
│   ├── dimension_thresholds.yaml
│   ├── truth_table_main.yaml
│   ├── truth_table_growth.yaml
│   ├── truth_table_backfill.yaml
│   └── llm_settings.yaml
│
├── tests/
│   ├── unit/                   单元测试 (覆盖每条真值表 + 关键边界)
│   ├── scenarios/              端到端场景 yaml (人类可读)
│   ├── golden/                 决策日志基线 (回归用)
│   └── fixtures/
│       ├── photos/             mock L1 输出 (10 张)
│       └── albums/             mock 老相册指纹
│
└── scripts/
    ├── run_demo.py             一键演示
    └── generate_golden.py      刷新 golden file
```

## 实现完成度

| 模块 | 状态 | 备注 |
|---|---|---|
| L1 mock fixture | ✅ | 10 张照片 (lakeside × 4 / random × 4 / sunset_chase × 4 共 12 张) |
| 路径 B · L2 主路径 | ✅ | 28 条真值表 + 7 维特征 + Policy Engine 完整 |
| 路径 A · 动态生长 (L2.5) | ✅ | 10 条真值表 + 4 维特征 + 多相册冲突仲裁 |
| 路径 C · 兜底回扫 | ✅ | 复用主真值表 + 三条封顶规则 |
| 三路仲裁器 | ✅ | 4 个 Case + 策略 3 禁用 |
| MockJudge (LLM) | ✅ | 确定性 stub, 真 LLM 接入留接口 |
| 单元测试 | ✅ | 共 150 个单测 |
| 端到端场景 | ✅ | 共 10 个 yaml + 全 golden file 比对 |

## 待做 (本 demo 不包含)

- v1.3.2 算法重写 (location 地理上下文 / time 双峰检测 / theme embedding 池化) — 见 `decisions/0004-feature-assembler-revision.md`,等审完 docs 再实现
- L2 综述生成 (LLM 写标题 + 50-80 字 synthesis) — 路径 B 命中后的 LLM 第二跳
- Mini Album 落库组装 (place_anchor 已落地 ADR-0005, theme_clusters 已落地 ADR-0008; 其他指纹字段 OQ-008 §8d/8e 待决)
- 真 LLM 接入 (anthropic claude-sonnet-4-6)
- 异步并行三路 (`asyncio.gather`)

## 工作契约

任何修改前先读 [CLAUDE.md](./CLAUDE.md)。改判断逻辑必须先改 `docs/`,改阈值必须改 `config/`,新数据结构必须先改 `src/contracts/`。
