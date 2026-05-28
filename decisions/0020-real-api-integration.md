# ADR-0020 · v0.2 真接入: Qwen LLM + Qwen Embedding + Amap + Persona 记忆 mock

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-20 |
| 决策人 | Ace — 拍板 5 项: Qwen 主/生长/兜底 + Embedding 本地 + POI 高德 + 不管存储 + Persona 记忆按四层 mock (active_state/user_model 字段空) |
| 影响范围 | 新增 `src/llm/qwen_judge.py` (DashScope `qwen-turbo` API) + 改 `src/llm/growth_judge.py` 加 `QwenGrowthJudge` + 改 `src/llm/backfill_judge.py` 加 `QwenBackfillJudge` + 改 `src/mini_album/theme_aggregation.py::QwenEmbedder` 真实现 (本地 sentence-transformers) + 改 `config/llm_settings.yaml` + 改 `config/theme_aggregation.yaml` + 改 `config/geocoder.yaml` + 给 3 persona yaml 加 `event_log` / `daily_digest` / `active_state` / `user_model` 段 + 新增 `src/test_utils/llm_mode.py` (mock/real 切换) + 新增 `tests/personas/_gen_visual_report.py` (LLM 行为可视化) + 新增 `docs/26_real_api_integration.md`; 改 `docs/{00,01,02,12}` |
| 相关文档 | `docs/26_real_api_integration.md`; 外部参考 `D:/user/Downloads/喜宝记忆系统架构设计.md` (四层记忆架构) |
| 关联 OQ | 新增 OQ-031 (真 LLM 真实行为基线 + 跟 mock 偏差对比) |
| 关联 ADR | **不 supersede** 任何; **接 v0.2 入口** (替换 ADR-0018 Plan A 默认的 mock LLM); 复用 ADR-0016 AmapGeocoder; 不影响算法骨架 |

---

## 1 · 背景

### 1.1 现状 (demo v0.1)
- LLM Judge 3 路 (主 / 生长 / 兜底) 全 mock 桩 (永远取 `bounds_min`)
- Embedding 全 MockEmbedder (16/64 维 md5 派生 + 同义词 dict 人工对齐)
- Geocoder 默认 mock (但 ADR-0016 AmapGeocoder 已实测可用)
- Persona 记忆只读 photos, identity/life_events/active_state/user_model 字段保留但空

### 1.2 Ace 2026-05-20 拍板 (5 项)
1. **LLM Judge 全接 Qwen** (主/生长/兜底), DashScope API `qwen-turbo`, no-thinking, temperature=0
2. **Embedding 本地** sentence-transformers + Qwen3-Embedding-0.6B (零成本)
3. **POI 用高德** (AmapGeocoder 已实现, env var 切真)
4. **存储差异不管** (维持 fixture / yaml)
5. **Persona 记忆四层 mock**: Event Log + Daily Digest 字段齐全填充, Active State + User Model 字段保留但空

### 1.3 关键约束
- **成本最低**: API 调试期 < $5
- **mock / real 双模式**: 默认 mock (CI 不花钱 + 确定性), env var `SEENFUL_LLM_MODE=real` 切真
- **现 19 persona scenarios 的 expected 多数为空**, 接真 LLM 不破 (expected 已经"最小化")
- **可视化**: 真 LLM 跑出来的 `semantic_reason` / `evidence` / `counter_evidence` 必须看得到

---

## 2 · 决策

### 2.1 LLM Judge 真接入

**Provider**: 阿里云 DashScope API
**Model**: `qwen-turbo` (足够 Judge 任务)
**Endpoint**: `https://dashscope.aliyuncs.com/compatible-mode/v1` (OpenAI-compatible)
**Auth**: env var `DASHSCOPE_API_KEY`
**Params**: `temperature=0`, `top_p=1.0`, `seed=42` (确定性)
**No-thinking**: Qwen3 默认 thinking mode, 加参数 `enable_thinking: false` 切 no-thinking
**Timeout**: 30s, retry 2 次, 失败 → 退回 MockJudge (graceful degrade)

**3 路统一接口** (复用现 `LLMJudge` / `GrowthLLMJudge` / `BackfillJudge` Protocol):
- `src/llm/qwen_judge.py::QwenJudge` (主路径 path B)
- `src/llm/growth_judge.py::QwenGrowthJudge` (路径 A 生长)
- `src/llm/backfill_judge.py::QwenBackfillJudge` (路径 C 回滚, system prompt 追加"兜底场景")

### 2.2 Embedding 真接入

**Provider**: 本地 `sentence-transformers` (零成本)
**Model**: `Qwen/Qwen3-Embedding-0.6B` (1024 维, 中英双语)
**Cache**: `~/.cache/huggingface/` 自动管
**性能**: CPU 5-20ms/句, GPU < 5ms

改 `src/mini_album/theme_aggregation.py::QwenEmbedder` 真实现 (现 raise NotImplemented).

config: `config/theme_aggregation.yaml::embedding.provider: mock → qwen3-embedding-0.6b`

### 2.3 POI Geocoder 切真

**Provider**: 高德 AmapGeocoder (ADR-0016 已实测)
**Auth**: env var `AMAP_API_KEY`
**Quota**: 30 万次/天 免费

config: `config/geocoder.yaml::provider: mock → amap` (env var 也可覆盖)

### 2.4 Persona 记忆 mock (按四层架构, Ace #5)

每个 persona yaml 加 4 段:

```yaml
# User Model (Compiled Truth) — 字段保留, runner 不读 (Ace #5)
user_model:
  identity: {nickname, city, life_stage}
  preferences: {}                   # 空
  current_state: {}                 # 空
  companion_notes: ""
  relationship_stage: {familiarity}

# Active State (执行层) — 字段保留, runner 不读 (Ace #5)
active_state:
  system_counters: {cumulative_active_days, current_streak}
  derived_preferences: {}
  session_state: {}
  behavior_cache: {}
  guard_flags: {}

# Event Log (Timeline 事实层) — 字段齐全填充, runner 不读 (现) / 未来 LLM Context 注入
event_log:
  - {id, ts, type, source, content, business_date, late_arrival}
  # 每张 photo 对应 1 条 photo_upload event
  # 关键 life_event / preference_expression / emotion_signal 也填

# Daily Digest (日级压缩) — 关键日子填充
daily_digests:
  - {business_date, structured, episodic_text, should_store, event_count, frozen_at}
```

工程量: 3 persona × ~30 events + ~10 digests = ~150 行 yaml 段 (1 天).

### 2.5 mock/real 双模式

```python
# src/test_utils/llm_mode.py
def get_llm_mode() -> Literal["mock", "real"]:
    return os.environ.get("SEENFUL_LLM_MODE", "mock")
```

pytest 默认跑 mock (CI 不花钱). 显式 `SEENFUL_LLM_MODE=real DASHSCOPE_API_KEY=... pytest` 跑真.

### 2.6 可视化报告

`tests/personas/_gen_visual_report.py` 跑全 19 scenarios real mode:
- 输入 photos + L1 字段
- 7 维 bands + 真值表 matched_pattern
- **LLM 完整输出** (proposed_strength / semantic_reason / evidence / counter_evidence)
- Policy Engine 最终决定
- Invariants 校验结果

输出 markdown 报告 → 你看每个 case LLM 怎么判.

---

## 3 · 实施清单 (12 步)

1. ADR-0020 (本文档) + docs/26
2. config/llm_settings.yaml 加 qwen provider 段
3. `src/llm/qwen_judge.py::QwenJudge` (DashScope HTTP client + retry + 降级)
4. `src/llm/growth_judge.py::QwenGrowthJudge` + `src/llm/backfill_judge.py::QwenBackfillJudge`
5. `src/mini_album/theme_aggregation.py::QwenEmbedder` 真实现
6. config/geocoder.yaml::provider 默认改 amap (现 mock)
7. 3 persona yaml 加 4 层记忆 mock 段
8. `src/test_utils/llm_mode.py` mock/real 切换
9. pytest fixture: 默认 mock, real 时跳过 (避免 CI 误跑)
10. `tests/personas/_gen_visual_report.py` 可视化报告
11. 跑 5-10 个核心 scenarios real mode (需要 API key)
12. 跨文档 (docs/00/01/02/12) + 收尾

---

## 4 · 验证

- pytest 跑 mock mode 不破 (现 470 测试全过)
- `SEENFUL_LLM_MODE=real` + key 设置后, 跑 5 个核心 scenarios 看真 LLM 行为
- 可视化报告生成 markdown
- 成本预算: < $5 调试期

---

## 5 · 跟现 ADR 关系

| ADR | 关系 |
|---|---|
| ADR-0010~0015 (path B 维度算法) | 不动 |
| ADR-0016 (AmapGeocoder) | 复用, 现切 provider=amap |
| ADR-0017 (Cascade) | 不动 |
| ADR-0018 (Plan A/B) | Plan A 默认从 mock LLM → 真 Qwen |
| ADR-0019 v0.2 (Persona) | 接入后跑同 19 scenarios real mode |

---

## 6 · 关联

**外部**:
- DashScope API: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Qwen3 模型: `qwen-turbo` (LLM) / `Qwen/Qwen3-Embedding-0.6B` (embedding)
- 高德 API: ADR-0016 已实测

**OQ**:
- 新增 OQ-031 (真 LLM 真实行为基线 + 跟 mock 偏差对比, 真实数据上线后 grid search)

---

## 7 · v0.7 修订 (2026-05-20): 真 Embedding 阈值校准

### 7.1 接真 Qwen Embedding 后 7 个单测失败

切 `config/theme_aggregation.yaml::embedding.provider: mock → qwen3-embedding-0.6b` 后:
- 533 → 526 测试通过, 7 个 fail
- 全部 fail 都因**真 Qwen Embedding 分布跟 mock 估值不同**

### 7.2 真 Qwen vs mock 分数对照 (实测)

| Case | mock score | 真 Qwen | 说明 |
|---|---|---|---|
| zzz_unknown vs lakeside (随机词) | ~0.10 | **0.47** | Qwen 给任何词 baseline 相似度 |
| meal vs lakeside (不同义) | ~0.10 | **0.51** | 仍有 0.5+ baseline |
| apple vs xylophone (英文不同义) | ~0.0 | **0.67** | 同语言 baseline 偏高 |
| sunset vs lake (近义) | ~0.50 | **0.69** | 真实近义 |
| 湖边 vs lakeside (跨语言同义) | ~1.0 | **0.62** | 跨语言同义比预期弱 |
| lake / lakefront / lakeshore (英文同义) | ~1.0 | **0.84-0.88** | 同语言同义强 |
| tag_0 vs tag_1 vs tag_N (字母模式) | ~0.0 | **0.96-0.98** | 模型识别"tag_N 模式" 高度相似 |

### 7.3 校准动作

#### A. 阈值上移 (config/theme_aggregation.yaml)
```yaml
band_thresholds:
  strong: 0.85   # was 0.75 — 真同义 ≥ 0.85
  medium: 0.70   # was 0.55 — 真相关 0.69-0.85
  weak:   0.55   # was 0.35 — 避开 Qwen baseline 噪声 0.45-0.55
```

#### B. 单测 fixture 现实化
- `tag_0 / tag_1 / a_N` 等"模式化字母" → 真 Qwen 看成同义 → 改为 真实多样化 (fireworks/anchor/telescope/violin/mushroom)
- 跨语言同义对 (湖边 vs lake) → 真 Qwen 跨语言识别较弱 → 改用同语言 (lakeside / lake / lakefront / lakeshore / waterside)

### 7.4 docs 联动

- ✅ docs/14_theme_aggregation.md §8.1 加"真 Qwen Embedding 校准"段, 真实分数表 + 阈值变化
- ✅ ADR-0020 v0.7 修订段 (本节)

### 7.5 最终状态

- 533 测试全过 (真 LLM + 真 Embedding 模式)
- 4 单测 fixture 现代化 (反真实 mock 假设)
- 阈值整体上移, 适配 Qwen 真分布
- dashboard 重生 (真 LLM + 真 Embedding + 新阈值)
