# 26 · v0.2 真接入: Qwen + Embedding + Amap + Persona 记忆 mock

> 算法依据: [ADR-0020](../decisions/0020-real-api-integration.md).

---

## 一、4 块接入

| 块 | provider | 调用方式 | 成本 |
|---|---|---|---|
| **LLM Judge** (主/生长/兜底) | DashScope `qwen-turbo` (no-thinking) | HTTP, env `DASHSCOPE_API_KEY` | ~$0.0002/调用, 60 scenarios < $0.05 |
| **Embedding** | 本地 sentence-transformers + `Qwen/Qwen3-Embedding-0.6B` (1024 维) | Python 库 | 0 (本地) |
| **POI Geocoder** | 高德 (`AmapGeocoder`, ADR-0016 已实测) | env `AMAP_API_KEY` | 0 (30 万/天免费) |
| **Persona 记忆** | yaml mock | 字段齐全填充 (Event Log / Daily Digest) | 0 |

---

## 二、mock/real 双模式

```bash
# 默认 mock (CI / 测试 / 不花钱)
python -m pytest tests/personas/ -v

# 切真 LLM
export SEENFUL_LLM_MODE=real
export DASHSCOPE_API_KEY=sk-xxx
python tests/personas/_gen_visual_report.py
```

env var 优先级 > config provider.

---

## 三、Qwen LLM Judge 接入细节

### 3.1 配置 (`config/llm_settings.yaml`)

```yaml
provider: mock                  # mock | qwen | anthropic

qwen:
  endpoint: https://dashscope.aliyuncs.com/compatible-mode/v1
  model: qwen-turbo
  api_key_env: DASHSCOPE_API_KEY
  temperature: 0.0              # 确定性
  seed: 42
  enable_thinking: false        # Qwen3 no-thinking
  retry_max: 2
  graceful_degrade_to_mock: true   # 失败退回 mock
```

### 3.2 调用流程

```
真值表查表 → matched_pattern (F1 跳过 LLM)
                      ↓
        Qwen LLM Judge (DashScope HTTP)
                ↓
        proposed_strength + evidence + counter_evidence
                ↓
        Policy Engine clamp 到 bounds + HR-POST
                ↓
        final_strength + display_decision
```

### 3.3 3 路统一接口

| 路径 | 实现 | system prompt 差异 |
|---|---|---|
| Path B 主 (`run_l2_path_b`) | `QwenJudge` | 标准 |
| Path A 生长 (`run_growth_path`) | `QwenGrowthJudge` | 输出 accept (true/false) |
| Path C 兜底 (`cascade_backfill_single`) | `QwenBackfillJudge` | 追加"兜底场景特别指引" |

---

## 四、Embedding 本地接入

`src/mini_album/theme_aggregation.py::QwenEmbedder`:

```python
class QwenEmbedder:
    def __init__(self, model_name="Qwen/Qwen3-Embedding-0.6B"):
        ...
    def __call__(self, tags: list[str]) -> list[list[float]]:
        # 首次自动下载 ~1.2GB 模型
        # 后续 5-20ms/句 (CPU)
        return self._model.encode(tags, convert_to_numpy=True).tolist()
```

切换:
```yaml
# config/theme_aggregation.yaml
embedding:
  provider: qwen3-embedding-0.6b   # mock → qwen 切真
  dim: 1024
```

依赖: `pip install sentence-transformers`

---

## 五、Persona 4 层记忆 mock

按喜宝架构 (`喜宝记忆系统架构设计.md`):

| 层 | 字段 | 现 runner 读? | mock 填充? |
|---|---|---|---|
| **User Model** (Compiled Truth) | `identity` + `preferences` + `current_state` + `companion_notes` + `relationship_stage` | ❌ (Ace #5) | 字段保留, **identity 填充**, 其他空 |
| **Active State** (执行层) | `system_counters` + `derived_preferences` + `session_state` + `behavior_cache` + `guard_flags` | ❌ (Ace #5) | 字段保留, **system_counters 填基础**, 其他空 |
| **Event Log** (Timeline 事实层) | `event_log[]` 含 `id/ts/type/source/content/business_date/late_arrival` | ❌ (现) / ✅ (未来 LLM context 注入) | **字段齐全 + 5-7 条/persona** |
| **Daily Digest** (日级压缩) | `daily_digests[]` 含 `structured/episodic_text/should_store` | ❌ (现) / ✅ (未来) | **2-3 个关键日子/persona** |

---

## 六、可视化报告

`tests/personas/_gen_visual_report.py` 跑全 19 scenarios → `tests/_VISUAL_REPORT.md` (~30KB):

每个 case 含:
- 输入照片 + L1 标签
- 7 维 bands (代码算)
- 真值表 matched_pattern + bounds
- LLM 完整输出 (proposed_strength / semantic_reason / evidence / counter_evidence)
- Policy Engine 最终决定
- Invariants 校验结果

切真 LLM 跑:
```bash
SEENFUL_LLM_MODE=real DASHSCOPE_API_KEY=sk-xxx python tests/personas/_gen_visual_report.py
```

---

## 七、跑命令

```bash
# 测试 (默认 mock)
python -m pytest tests/personas/ -v
python -m pytest -q                       # 全套 470

# 可视化报告 (默认 mock)
python tests/personas/_gen_visual_report.py

# 切真 LLM (需 API key)
export DASHSCOPE_API_KEY=sk-xxx
export SEENFUL_LLM_MODE=real
python tests/personas/_gen_visual_report.py
```

---

## 八、关联

- [ADR-0020](../decisions/0020-real-api-integration.md)
- [ADR-0019 v0.2](../decisions/0019-persona-based-e2e-testing.md) (persona)
- [ADR-0016](../decisions/0016-location-geocoder-4tier.md) (AmapGeocoder)
- [ADR-0018](../decisions/0018-feature-assembler-plan-ab-switch.md) (Plan A 现真 LLM)

**外部**:
- DashScope: https://dashscope.aliyuncs.com (Qwen API)
- 高德开放平台: https://lbs.amap.com (Reverse Geocoding)
- Qwen3-Embedding-0.6B: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
