# 21 · 路径 B Emotional 维度: 开放字段 + 单层语义聚类

> 路径 B (L2 主路径) emotional 维度的算法规范.
> 算法依据: [ADR-0015](../decisions/0015-path-b-emotional-single-tier-cluster.md).
> 复用 [ADR-0013](../decisions/0013-path-b-theme-two-tier-cluster.md) `_two_tier_cluster.build_two_tier_feature` 工具 + `enable_secondary=False`.
>
> ⚠ **开放字段, 不是封闭枚举**: emotional_tone 是 `str` (Ace 2026-05-18 指出). 老 7 白名单仅 L1 prompt 引导, 字段层不校验.
>
> ⚠ **照片情感 ≠ 用户情绪** (Ace 核心洞察): "诗意" 描述画面属性, 允许; "开心" 推断用户情绪, 违反红线 §1.

---

## 一、变量定义

| 变量 | 定义 |
|---|---|
| N | 总照片数 |
| N_valid | emotional_tone 非空字符串的 photo 数 (含 "neutral", 不计 "") |
| tag_pool | ⋃ photos.emotional_tone 跨 photos 单值去重 |
| primary_clusters | `agglomerative_cluster_cosine(vectors, 0.75)` 输出 |
| cluster.hit_rate | 命中该簇的 photo 数 / N |
| emotion_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 |
| coverage | ⋃ emotion_clusters.member_photos / N |
| primary_dominant_tone | coverage 最高簇的代表词 |
| is_neutral_baseline | primary_dominant_tone == "neutral" |
| detected_inferred_emotion_count | 黑名单匹配的 photo 数 (落痕, 不阻断) |

---

## 二、算法步骤

### 2.1 · 流水线

```text
photos
  │
  ▼
┌──────────────────────────────────────────────┐
│ Phase 1 · 红线诊断 (落痕, 不阻断)            │
│  · 对每张 photo 的 emotional_tone 查黑名单   │
│  · detected_inferred_emotion_count++         │
└──────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────┐
│ Phase 2 · 收集 + 单层语义聚类                │
│  · tag_pool = ⋃ photos.emotional_tone        │
│  · MockEmbedder embed → 层次聚类 (0.75)      │
│  · cluster.hit_rate / hit_count              │
│  · emotion_clusters 过阈值 (≥0.5 AND ≥2)     │
│  · coverage                                  │
│  · 调 _two_tier_cluster (enable_secondary=False)│
└──────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────┐
│ Phase 3 · 6 行 grid 判定 (EM.0 preempt 优先) │
└──────────────────────────────────────────────┘
  │
  ▼
EmotionalFeature (band + shape + rule_fired)
```

### 2.2 · 6 行 grid

| # | 条件 | band | shape |
|---|---|---|---|
| **EM.0** (preempt) | primary_dominant_tone == "neutral" | **weak** | neutral_baseline |
| EM.1 | coverage = 1.0 (主簇非 neutral) | **strong** | unanimous_emotion |
| EM.2 | 0.8 ≤ coverage < 1.0 (非 neutral) | medium | dominant_emotion |
| EM.3 | 0.5 ≤ coverage < 0.8 (非 neutral) | medium | mixed_emotion |
| EM.4 | < 0.5 OR no emotion_clusters, N_valid ≥ 2 | weak | scattered_emotion |
| EM.5 | N_valid ≤ 1 | **none** | no_emotion_signal |

⚠ **EM.0 优先级最高**: 即使 coverage=1.0 但主簇是 neutral, 强制 cap weak. emotional 是 baseline 不是强信号.

### 2.3 · 红线诊断 (软阻拦)

```python
INFERRED_EMOTION_BLACKLIST = {
    # 中文 (10 个常见)
    "开心", "悲伤", "忧郁", "焦虑", "孤独", "抑郁", "愤怒", "恐惧", "高兴", "难过",
    # 英文 (9 个常见)
    "happy", "sad", "depressed", "anxious", "lonely",
    "melancholic", "joyful", "angry", "fearful",
}

for p in photos:
    if p.emotional_tone in BLACKLIST:
        detected_inferred_emotion_count += 1
        detected_inferred_emotions.add(p.emotional_tone)
# 仍正常进 distribution + 聚类, 不阻断
```

LLM 上游看到 `detected_inferred_emotion_count > 0` 可知"L1 prompt 失效", v0.2 触发改 L1 few-shot.

---

## 三、EmotionalShape 枚举

| 值 | 对应 rule_fired | 语义 |
|---|---|---|
| `neutral_baseline` | EM.0 | 主簇=neutral 兜底 weak (核心修复点) |
| `unanimous_emotion` | EM.1 | 主簇非 neutral 全员一致 strong |
| `dominant_emotion` | EM.2 | 主簇主导 80%+ |
| `mixed_emotion` | EM.3 | 主簇覆盖 50-80% |
| `scattered_emotion` | EM.4 | 主簇覆盖 < 50% 或无 |
| `no_emotion_signal` | EM.5 | N_valid ≤ 1 |

---

## 四、Case 验证 (8 个)

详见 `archive/specs/Path_B_Emotional_Aggregation_Spec.md` v0.2 §五. 摘要:

| Case | inputs | mock band | 真模型 band |
|---|---|---|---|
| 全 awe | [awe × 5] | EM.1 strong | strong |
| 同义不同字面 | [calm × 3, quiet × 2] | EM.4 weak (表外 md5) | EM.1 strong |
| **全 neutral** | [neutral × 5] | **EM.0 weak (preempt)** | EM.0 weak |
| 开放词主导 | [诗意 × 4, 喧闹 × 1] | EM.2 medium | EM.2 medium |
| 散乱 | [诗意, 喧闹, 怀旧, 温馨, 极简] | EM.4 weak | EM.4 weak |
| 违反红线 | [happy × 5] | EM.1 strong **+ inferred_count=5 落痕** | (LLM 上游可看到红线被违反) |
| 2 张同 | [诗意 × 2] | EM.1 strong | EM.1 strong |
| 2 张二选 | [诗意, 喧闹] | EM.4 weak (hit<2) | EM.4 weak |

---

## 五、不变性

1. band 4 档终值, 真值表直读
2. 双阈值 (聚类 0.75 + 主题 0.5) + hit_count ≥ 2
3. **EM.0 preempt 优先**: 主簇=neutral 强制 cap weak
4. **无次字段升降档** (单层 grid)
5. **字段保持 `str` 开放**, L1 prompt 引导, 算法层不硬校验
6. **红线落痕不阻断** (违规词仍进 distribution, `detected_inferred_*` 落痕)
7. N < 2 → none (红线 §3)
8. **复用 ADR-0013 `_two_tier_cluster` + `enable_secondary=False`**
9. rule_fired 必填
10. **emotional 是辅证**, 真值表 A 系列无 emotional=强单独成集

---

## 六、配置

完整见 `config/path_b_emotional.yaml`. 关键:

| 字段 | 默认 |
|---|---|
| `primary_field` | "emotional_tone" |
| `primary_hit_rate_threshold` | 0.5 |
| `min_hit_count` | 2 |
| `primary_band_thresholds.strong_coverage` | 1.0 |
| `primary_band_thresholds.medium_high` | 0.8 |
| `primary_band_thresholds.medium_low` | 0.5 |
| `neutral_baseline.enabled` | true |
| `neutral_baseline.cap_band` | "weak" |
| `neutral_baseline.neutral_token` | "neutral" |
| `inferred_emotion_blacklist.chinese` | [开心, 悲伤, 忧郁, ...] |
| `inferred_emotion_blacklist.english` | [happy, sad, depressed, ...] |
| `fallback.n_valid_min` | 1 |

---

## 七、与 ADR-0013/0014 关系

| | ADR-0013 theme | ADR-0014 anchor | **ADR-0015 emotional (本)** |
|---|---|---|---|
| 字段 | 多值 list[str] | 多值 list[str] (双字段) | **单值 str** |
| 算法 | 双层 + 升降档 | 双层 + 升降档 | **单层 + EM.0 preempt** |
| 工具 | `_two_tier_cluster(enable_secondary=True)` | 同 | **`enable_secondary=False`** |
| Grid 行数 | 5 + 升降档 | 5 + 升降档 | **6 (含 EM.0 preempt)** |
| 特殊处理 | 无 | 修订 OQ-008 §8e | **neutral cap + 红线诊断** |

⚠ L1 prompt 改: 7 白名单 → 开放画面氛围词 + 红线推断情绪阻拦.
