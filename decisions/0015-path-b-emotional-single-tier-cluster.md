# ADR-0015 · 路径 B emotional 维度: 开放字段 + 单层语义聚类 + neutral baseline

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-18 |
| 决策人 | Ace — 经多轮迭代 (v0.1 误用 Counter → v0.2 开放字段语义聚类) |
| 影响范围 | 重写 `src/features/emotional.py` + 升级 `src/contracts/features.py::EmotionalFeature + EmotionalShape + FeaturePackage.emotional` + 改 `src/contracts/l1_output.py::emotional_tone` (prompt 描述改一行) + 加 `src/features/_two_tier_cluster.py::enable_secondary` 参数 + 新增 `config/path_b_emotional.yaml` + 新增 `docs/21_path_b_emotional.md`; 改 `docs/{00,01,02,07,11,12}` |
| 相关文档 | `docs/21_path_b_emotional.md`; `Path_B_Emotional_Aggregation_Spec.md` v0.2 (设计来源, 实施完后归档) |
| 关联 OQ | **新增** [OQ-026](../docs/12_open_questions.md#oq-026-adr-0015-接受边界的真实数据验证) (5 子问题 a-e: prompt 接入风险 / 黑名单完整性 / neutral cap 严格度 / mock 局限 / 邻近度 group) |
| 关联 ADR | **复用** [ADR-0013](./0013-path-b-theme-two-tier-cluster.md) `_two_tier_cluster.build_two_tier_feature` 工具 + 新增 `enable_secondary=False` 参数 (theme/anchor 默认 True 不破); supersede 老 `src/features/emotional.py` (Counter 三档); 修订 L1 `emotional_tone` 字段描述 (7 白名单 → 开放画面氛围词) |

---

## 1 · 背景

### 1.1 · 现状

`src/features/emotional.py` v0.1 (24 行) 用 Counter most_common 三档: 1.0=0.85 / ≥2/3=0.55 / 其他=0.10.

字段 `emotional_tone: str` 开放, 但 L1 prompt 限制 7 白名单. v0.1 算法当**半封闭** Counter, 算法范式选错.

### 1.2 · 失败模式 (Ace 2026-05-18 提出)

| 场景 | v0.1 | 应该 | 失败根因 |
|---|---|---|---|
| [neutral × 5] | 0.85 strong | weak | neutral 是 baseline 不是强信号 |
| [calm × 3, quiet × 2] | medium | strong | Counter 不识同义 (邻近词) |
| [诗意 × 5] (开放词) | 0.10 none (off-list?) | strong | 7 白名单不含画面氛围词 |
| [happy × 5] (违反红线) | 0.85 strong (错) | strong + 落痕违规 | 字段不校验违规 |

### 1.3 · "照片情感 ≠ 用户情绪" (Ace 核心洞察)

7 老白名单 (relaxed/calm/quiet/awe/warm/busy) 偏"用户情绪状态", 不能表达**画面氛围** (诗意/怀旧/静谧/戏剧化/极简/...).

**红线 §1 "不做情绪推断"** 禁的是"推断用户内心情绪" (happy/depressed/anxious/lonely), 不是"画面属性" (诗意 ≠ 开心).

### 1.4 · 引发本 ADR

- emotional 是 path B 7 维最后一个未升级 (location/time/event/theme/anchor 已落 ADR-0010~0014)
- 不能用 Counter (字段开放), 应该用语义聚类
- L1 prompt 需扩到画面氛围开放词典 + 红线区分

---

## 2 · 决策

### 2.1 · 算法范式

**开放字段 + 单层语义聚类**, 直出 4 档 band. 真值表 28 条不变.

复用 ADR-0013 `_two_tier_cluster.build_two_tier_feature` 工具, 加 `enable_secondary: bool = True` 参数. emotional 传 `False` 跳过 Phase 3 升降档 (单层).

### 2.2 · 6 行 grid (含 EM.0 preempt)

```
EM.0 (preempt, 优先): 主簇代表词 = "neutral" → weak / neutral_baseline
EM.1: coverage = 1.0 (非 neutral) → strong / unanimous_emotion
EM.2: 0.8 ≤ < 1.0 (非 neutral) → medium / dominant_emotion
EM.3: 0.5 ≤ < 0.8 (非 neutral) → medium / mixed_emotion
EM.4: < 0.5 OR no cluster, N_valid ≥ 2 → weak / scattered_emotion
EM.5: N_valid ≤ 1 → none / no_emotion_signal
```

### 2.3 · L1 prompt 改一行

`src/contracts/l1_output.py::L1Output.emotional_tone.description`:
- 从 "允许: relaxed/calm/neutral/awe/quiet/warm/busy" 改为 **"允许画面属性氛围词 (开放), 禁推断用户内心情绪"**
- 字段类型仍 `str` 不变 (不引入 Literal)
- 红线 §1 区分: "诗意" (画面属性) 允许; "开心" (用户情绪) 禁止

### 2.4 · 红线落痕不阻断

LLM 违反红线 (输出 happy/sad 等) 时算法**仍正常进 distribution**, 仅落痕:
- `EmotionalFeature.detected_inferred_emotion_count`
- `EmotionalFeature.detected_inferred_emotions: list[str]`

L1 prompt 才是阻拦的第一道关. 算法层软阻拦 + 落痕给上游知情.

### 2.5 · 配置

```yaml
# config/path_b_emotional.yaml
path_b_emotional:
  primary_field: "emotional_tone"
  primary_hit_rate_threshold: 0.5
  min_hit_count: 2

  primary_band_thresholds:
    strong_coverage: 1.0
    medium_high: 0.8
    medium_low: 0.5

  neutral_baseline:
    enabled: true
    cap_band: "weak"
    neutral_token: "neutral"

  inferred_emotion_blacklist:
    chinese: [开心, 悲伤, 忧郁, 焦虑, 孤独, 抑郁, 愤怒, 恐惧, 高兴, 难过]
    english: [happy, sad, depressed, anxious, lonely, melancholic, joyful, angry, fearful]

  fallback:
    n_valid_min: 1
```

---

## 3 · 评估过的备选项

| 方案 | 拒绝理由 |
|---|---|
| A. 老 Counter v0.1 | 字段实际开放, Counter 不识同义, neutral 错升 strong |
| B. 扩白名单到 16-20 (闭枚举) | 永远列不全, LLM 仍可能违规 |
| **C. 开放字段 + 单层语义聚类 (本 ADR)** | 跟 theme/anchor v0.3 算法骨架同源, 复用代码, 灵活 |
| D. 字段改 list[str] (多值) | L1 schema 改动太大, fixtures 全部要重写 |

---

## 4 · 影响范围

### 4.1 · 契约变更

**新增** `src/contracts/features.py`:
```python
class EmotionalShape(str, Enum):
    UNANIMOUS_EMOTION = "unanimous_emotion"    # EM.1
    DOMINANT_EMOTION = "dominant_emotion"      # EM.2
    MIXED_EMOTION = "mixed_emotion"            # EM.3
    NEUTRAL_BASELINE = "neutral_baseline"      # EM.0 preempt
    SCATTERED_EMOTION = "scattered_emotion"    # EM.4
    NO_EMOTION_SIGNAL = "no_emotion_signal"    # EM.5

class EmotionalFeature(BaseModel):
    band: BandLevel
    rule_fired: str
    score: float
    # cluster 诊断
    total_photos / valid_photo_count / tag_pool_size / cluster_count
    emotion_clusters / hit_rates / coverage / outlier_photo_ids
    # neutral baseline
    primary_dominant_tone: str | None
    is_neutral_baseline: bool
    # 红线诊断
    detected_inferred_emotion_count: int
    detected_inferred_emotions: list[str]
    shape: EmotionalShape
```

**修改** `FeaturePackage.emotional: EmotionalFeature | None` 字段新增.

**修改** `src/features/_two_tier_cluster.py::build_two_tier_feature` 加 `enable_secondary: bool = True` 参数. 默认 True (theme/anchor 不破), False 时跳过 Phase 3 + 不计算 secondary_*.

### 4.2 · L1 字段变更

`src/contracts/l1_output.py::L1Output.emotional_tone` 仅 description 改 (字段类型 `str` 不变):
- 从"7 白名单" 引导改为"开放画面氛围词 + 红线推断情绪阻拦"

### 4.3 · 新增算法模块

**重写** `src/features/emotional.py`:
- `build_emotional_feature(photos) -> EmotionalFeature` 高层入口
- 调 `_two_tier_cluster.build_two_tier_feature(enable_secondary=False)` 通用工具
- 单 extractor: `lambda p: [p.emotional_tone] if p.emotional_tone else []`
- 后处理: neutral baseline 检测 + 红线诊断 (黑名单匹配)

### 4.4 · 配置

新增 `config/path_b_emotional.yaml` (见 §2.5).

### 4.5 · 调用方

- `src/features/assemble.py` 调 `build_emotional_feature(photos)` 替代 `compute_emotional_score`
- `src/policy/bands.py::compute_bands` `Bands.emotional` 直读 `EmotionalFeature.band`

### 4.6 · 测试

`tests/unit/test_features_emotional.py` 重写, 8 个 Case + 边界 (跟 spec §五 同).

---

## 5 · 回滚条件

| 回滚条件 | 动作 |
|---|---|
| L1 真接入后 LLM 违反红线频率 > 30% | 修 L1 prompt few-shot + 扩黑名单 |
| neutral cap weak 误降率 > 20% | 放宽 EM.0 preempt 条件 (例: 仅当 coverage ≥ 0.6 + 主簇=neutral 才 cap) |
| 真模型上同义识别准确率 < 60% (calm/quiet/relaxed 等不合并) | 调 cluster_merge_similarity 0.75 → 0.65 |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| **OQ-026 (新增)** | — | ADR-0015 接受边界 v0.2 真实数据验证 (5 子问题 a-e) |

无 OQ 关闭 (emotional 之前没独立 OQ).

---

## 7 · 后续动作

1. ✅ 本 ADR 写完
2. ⏳ `docs/21_path_b_emotional.md`
3. ⏳ `config/path_b_emotional.yaml`
4. ⏳ contracts 升级 + `_two_tier_cluster` 加参数
5. ⏳ `src/features/emotional.py` 重写 + L1 prompt 改一行
6. ⏳ assemble + bands 适配
7. ⏳ 跨 docs 同步
8. ⏳ 单测 + golden + grep + 归档
