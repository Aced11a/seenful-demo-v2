# 01 · 架构总览

## 设计哲学

```
代码做"该不该考虑"
LLM 做"考虑了之后判什么"
Policy Engine 做"最终拍板"
```

附加准则:
- **路径优先级**: 续旧 (A) > 拼新窗口 (B) > 救沉淀 (C) > 沉淀
- **关联宁轻勿硬**: weak/light 绝不成集,只走轻提示
- **动态生长但治理**: 30 天可吸纳,但三档置信度 + 高频抑制 + 用户排除

---

## 真实流程: 上传张数分流 + C 真兜底

**关键认知**: A 和 B **不是**并列竞争的两条对等路径,而是按**用户上传场景**分工:
- **A** (动态生长): 把这张照片**挂到老相册**。只要用户名下有 `is_growing=true` 老相册就可触发,与上传张数无关。
- **B** (L2 主路径): 当前批次**成新集**。**由上传张数门控** — 单张不进 B (除非 rolling window 凑够 3 张)。
- **C** (兜底回扫): **当 A 和 B 都没产出相册**时,救活历史沉淀单图。**真兜底,不并行跑**。

PRD 里 "asyncio.gather 三路并行" 是**实现层效率优化**,语义上仍是"A/B 主路径 + C 兜底"。

### ADR-0020 真 API 接入 (2026-05-20)

v0.2 接真服务 (跟算法骨架解耦, env var 切换):

| 模块 | mock (默认) | real |
|---|---|---|
| LLM Judge (主/生长/兜底) | MockJudge 永远取 bounds_min | **QwenJudge** (DashScope qwen-turbo, no-thinking, temperature=0, env `DASHSCOPE_API_KEY`) |
| Embedding | MockEmbedder (64 维 md5 + dict) | **QwenEmbedder** (本地 sentence-transformers + Qwen3-Embedding-0.6B, 1024 维) |
| Geocoder | MockGeocoder | AmapGeocoder (env `AMAP_API_KEY`, ADR-0016 已实测) |

切换: `SEENFUL_LLM_MODE=real` + config 改 provider. graceful_degrade_to_mock 兜底.

新增模块:
- `src/llm/qwen_judge.py::QwenJudge` (path B 主)
- `src/llm/growth_judge.py::QwenGrowthJudge` (path A)
- `src/llm/backfill_judge.py::QwenBackfillJudge` (path C, system prompt 加兜底指引)
- `src/mini_album/theme_aggregation.py::QwenEmbedder` (本地真实现)

详见 [docs/26](./26_real_api_integration.md).

### ADR-0017 流程升级 (2026-05-19)

`run_full_l2` 按上传张数三路分流, 多张 B 失败后**拆 N 张**每张独立走 A→C (详见 [docs/23](./23_pipeline_cascade_backfill.md)):

| N | 流程 |
|---|---|
| **N=1** | P → A → C → 沉淀 |
| **N=2** | light_judge (PRD §3.2.2, demo v0.1 不写测试) |
| **N≥3** | B 整批 → 失败拆 N 张, 每张独立 A → C |

cascade 单次 = `cascade_backfill_single` (OR 粗筛 → 维度强度总分排序选 top 4 → 现 `apply_backfill_caps` strong-only). 多产物输出 ArbitrationResult 含 `primary_album` + `cascade_albums` + `growth_merges` + `settled_photo_ids`.

### ADR-0018 Feature Assembler 双版本 (2026-05-19)

Path B 7 维度算法走双版本开关 (详见 [docs/24](./24_feature_assembler_plan_ab.md)):

| Plan | 算法 | 用途 |
|---|---|---|
| **L2 2.0** (默认) | ADR-0010~0015 升级版各维度独立算法, 直出 4 档 band | 主, 生产 |
| **L2 1.0** | v1.3 工程规范 §3.2 score-based 抄本 | 副, demo 对比 |

全局开关 `config/feature_assembler.yaml::plan`, CLI `--plan a/b` 覆盖. DecisionLog 加 `feature_assembler_plan` 字段落痕版本. 真值表 28 条 / HR / LLM / Path A / Path C 跨版本共享.

---

## 全链路总图

```text
═══════════════════════════════════════════════════════════════════════
                       用户上传 1-N 张照片
═══════════════════════════════════════════════════════════════════════
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │ L1 单图理解 (mock in v0.1)  │
                  └─────────────────────────────┘
                                │
                                ▼
              ┌────────────────────────────────────┐
              │  按上传张数分流 (Candidate Builder) │
              └────────────────────────────────────┘
                                │
        ┌───────────────────────┼──────────────────────┐
        │                       │                      │
        ▼                       ▼                      ▼
  单张 + 无 albums         单张 + 有 albums          多张 (≥3)
  + 无 sediment            或单张 + sediment          ────────────
        │                       │                      │
        ▼                       ▼                      ▼
   ┌─────────┐              ┌─────────┐           ┌─────────────┐
   │ 早返    │              │ 路径 A  │           │ 路径 A + B │
   │ 单图沉淀│              │ 动态生长 │           │ 并行 (A 优先)│
   └─────────┘              └─────────┘           └─────────────┘
                                │                      │
                       A 命中? ──┤             A 或 B 命中? ──┤
                       是   否   │             是          否
                        │   │   │              │           │
                  ┌─────┘   │   │              ▼           ▼
                  ▼         │   │       走 A 或 B (按       │
            加入老相册       │   │       优先级 A > B)       │
            (Case 1)        │   │                          │
                            ▼   ▼                          │
                  ┌────────────────────────────────────────┘
                  ▼
            ┌─────────────────────┐
            │ 路径 C · 兜底回扫    │
            │ (真兜底, 此时才跑)   │
            └─────────────────────┘
                  │
            C 命中 strong?
                  │
       ┌──────────┼──────────┐
       ▼                     ▼
  Case 3                 Case 4
  新建兜底集 (C)         单图沉淀, 喜宝无感
  (新照片+召回沉淀)
```

### 4 种最终结局 vs 触发路径

| Ending | 来源 | 触发条件 |
|---|---|---|
| `add_to_existing_album` (Case 1) | A | 任意上传 + 用户有老相册 + A 命中 (auto_merge) |
| `ask_user_confirm` (Case 1) | A | 同上, A 命中 (ask_user) |
| `create_new_album_path_b` (Case 2) | B | 多张 ≥3 + B 命中 show_mini_album + A 未命中 |
| `create_new_album_backfill` (Case 3) | C | A + B 都未产出 + C 命中 strong |
| `single_photo_sediment` (Case 4) | (无) | A + B + C 全部未产出 |

---

## 三路触发条件细化

### 路径 A · 动态生长 (任意张数)

`src/candidate_builder/growth_scan.py`

触发: 用户名下至少 1 本 `is_growing=true` 老相册 + 新照片非敏感
- 单张上传: A 对该张照片 vs 所有候选老相册评估
- 多张上传: A 对每张照片(v0.1 简化为首张) vs 所有候选老相册评估

### 路径 B · L2 主路径 (≥3 张才进入)

`src/policy/hard_rules.py::pre_filter` + 主真值表流程

触发条件 (PRD §B.Step1):
- 多张模式 ≥ 3 张 → `full_l2`
- 多张模式 = 2 张 → `light_judge_only` (v0.1 未实现, 视同 suppress)
- 多张模式 = 1 张 → **不进 B**, 单图沉淀
- 单张 + 24h 累计 ≥ 3 张 → `full_l2`
- 48h 窗口到期 + ≥ 3 张 → `full_l2`

### 路径 C · 兜底回扫 (真兜底, 在 A+B 都失败时才跑)

`src/candidate_builder/backfill_scan.py`

触发条件:
1. A 未产出相册 (decision_tier ∉ {auto_merge, ask_user}), **且**
2. B 未产出相册 (display_decision ≠ show_mini_album), **且**
3. 沉淀池非空 (`len(sedimented_pool) >= 1`)

三个条件**同时**满足才跑 C。这是"真兜底"的精确定义。

---

## 四层 + Orchestrator

```
┌─────────────────────────────────────────────────────────────┐
│ src/pipeline.py · Orchestrator                              │
│  · run_l2_path_b(photos)                单独测路径 B         │
│  · run_growth_path(new_photo, albums)   单独测路径 A         │
│  · run_backfill_path(new_photo, pool)   单独测路径 C (老入口) │
│  · run_full_l2(photos, albums, pool)    生产入口, 三路分流 + 仲裁 │
│  · src/policy/cascade_backfill.py::cascade_backfill_single   │
│       cascade 单次 (粗筛→排序选 4→Caps, ADR-0017)           │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Candidate Builder (代码)                                 │
│    src/candidate_builder/                                   │
│    · growth_scan.py    路径 A 候选老相册                    │
│    · backfill_scan.py  路径 C 30 天 SQL + 粗筛              │
│   (路径 B 的早返在 src/policy/hard_rules.py::pre_filter)    │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Feature Assembler (代码)                                 │
│    src/features/                                            │
│    · 路径 B 7 维: location/time/theme/event/people/         │
│              anchor/emotional + assemble.py                 │
│    · 路径 B location 走 DBCH-PCA-shape 直出 band (ADR-0010) │
│    · 路径 B time 走 自然日归属 + 链式切分直出 band (ADR-0011)│
│    · 路径 B event 走 primary_share + activity 二次门槛 (ADR-0012)│
│    · 路径 B theme 走 双层 cluster + 升降档 (ADR-0013)        │
│    · 路径 B anchor 走 双层 cluster + 升降档 (ADR-0014)       │
│    · 路径 B emotional 走 单层 cluster + neutral baseline (ADR-0015)│
│    · Location · 高德 Geocoder + 4 档 (市内/省内/国内/国外, ADR-0016)│
│    · 路径 A 4 维 (vs 指纹): growth_features.py              │
│    · 路径 C 复用 7 维 (new + 召回当作整体)                  │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Policy Engine (代码, 分多个 stage)                       │
│    src/policy/                                              │
│    · bands.py              强/中/弱/无 分档, 高频降一档     │
│    · truth_table.py        主真值表 28 条 DSL               │
│    · truth_table_growth.py 生长真值表 10 条                 │
│    · hard_rules.py         前置 HR-PRE-01..04               │
│    · engine.py             路径 B 后半: clamp + 后置 HR    │
│    · growth_engine.py      路径 A: HRG-POST + 多相册仲裁   │
│    · backfill_engine.py    路径 C: 三条 CAP 封顶           │
│    · config_loader.py      yaml 单例加载                   │
└─────────────────────────────────────────────────────────────┘
        │
        ▼ (非 F1 / 非 G-F1 才进 LLM)
┌─────────────────────────────────────────────────────────────┐
│ 4. LLM Judge (mock in v0.1)                                  │
│    src/llm/                                                  │
│    · judge.py            MockJudge / AnthropicJudge        │
│    · growth_judge.py     MockGrowthJudge                    │
│    · backfill_judge.py   MockBackfillJudge                 │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Mini Album (DBCH + Theme + Event + Low Quality)           │
│    src/mini_album/                                          │
│    · place_anchor.py        DBCH (ADR-0005, v0.1 档位      │
│                              被 ADR-0007 临时统一)          │
│    · user_home_city.py      context 判定 (v0.1 stub)        │
│    · low_quality_place.py   高频低质量地点降档 (ADR-0006)    │
│    · theme_aggregation.py   theme 语义簇聚合 + 匹配 (ADR-0008)│
│    · event_aggregation.py   event 三级分层聚合 + 匹配 (ADR-0009)│
│    · 路径 A location/theme/event 走这里, 返回 band 直接消费 │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Arbitration (代码, 仅 run_full_l2 触发)                  │
│    src/arbitration/merge_results.py                         │
│    · arbitrate(growth_log, l2_log, backfill_log)            │
│    · 4 个 Case 严格优先级                                    │
│    · 策略 3 禁用 (A 命中时 C 整体作废)                      │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
   add_to_existing_album / ask_user_confirm /
   create_new_album_path_b / create_new_album_backfill /
   single_photo_sediment
        │
        ▼
   完整决策日志 (DecisionLog / Growth / Backfill / Arbitration)
   见 docs/11_observability.md
```

---

## 模块依赖方向

```
contracts ◄────── features ◄────── mini_album (place_anchor / theme_aggregation /
   ▲                ▲                            event_aggregation / low_quality_place /
   │                │                            user_home_city)
   │                │ (growth_features 用 match_new_photo + match_theme + match_event)
   │      ◄────── candidate_builder
   │
   │      ◄────── policy
   │
   │      ◄────── llm
   │
   │      ◄────── arbitration
   │
   └────────────── pipeline → 全部
```

规则:
- `contracts` 不依赖任何其他模块(纯 Pydantic)
- `features` / `candidate_builder` / `policy` / `llm` 互不依赖(全部依赖 contracts)
- `mini_album` 依赖 contracts; `features.growth_features` 调 `mini_album.place_anchor.match_new_photo` (ADR-0005) + `mini_album.theme_aggregation.match_theme` (ADR-0008) + `mini_album.event_aggregation.match_event` (ADR-0009)
- `arbitration` 依赖 contracts(读三路日志结构)
- `pipeline` 是唯一的 orchestrator,负责串联

---

## 4 个 Orchestrator 入口的使用场景

| 入口 | 何时调 | 输入 | 输出 |
|---|---|---|---|
| `run_l2_path_b(photos)` | 仅测路径 B 算法 / 单元测试 | ≥1 张新照片 | `DecisionLog` |
| `run_growth_path(new_photo, albums)` | 仅测路径 A / 单元测试 | 1 张新 + N 本老相册 | `GrowthDecisionLog` |
| `run_backfill_path(new_photo, pool)` | 仅测路径 C / 单元测试 | 1 张新 + 30 天沉淀池 | `BackfillDecisionLog` |
| `run_full_l2(photos, albums, pool)` | **生产入口** / 端到端场景 | 一次上传的全部上下文 | `ArbitrationResult` (含三路原始日志,可能含 None) |

---

## v0.1 的简化与待补

| 模块 | v0.1 实现 | v0.2 待替换 |
|---|---|---|
| L1 输出 | fixture 静态 JSON | 真实 Qwen3.6-Plus vision API |
| LLM Judge | 确定性 Mock | anthropic claude-sonnet-4-6 |
| feature 算法 (theme/event/anchor) | v0.1 简化 (固定阈值 / Jaccard) | v1.3.2 (双峰 / embedding 池化) 见 ADR-0004 |
| place_anchor (路径 A location) | **DBCH 已落地** (ADR-0005, 2026-05-13) | 真实数据 P0.5 调优 eps 参数 |
| L2 综述生成 | 不实现 | 生成标题 + synthesis + cover 选择 |
| Mini Album 落库 — 其他指纹字段 | theme_clusters (ADR-0008 mock embedder) + event_agg (ADR-0009) 均已落地; anchors_set 仍手填 fixture | 见 OQ-008 §8e |
| 异步并行 (A+B) | 同步串行 | `asyncio.gather` |
| Rolling window (B) | 不实现 | 24h / 48h 累计触发 light_judge_only |
| 用户响应模拟 | ask_user 标 pending 不模拟 | 真实用户决策回流 + excluded_photo_ids 写回 |
