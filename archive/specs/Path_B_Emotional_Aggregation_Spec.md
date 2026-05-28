# L2 Path B · Emotional 维度判断规范

> **版本**: v0.2 (draft, 待 Ace 最终审核)
> **日期**: 2026-05-18
> **适用**: Seenful L2 Engine 路径 B (多张照片自身) emotional 维度
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (写 ADR-0015 + 后续 docs/src/config/tests).
> **v0.2 改动 (Ace 2026-05-18)**:
> 1. **算法范式切换** — v0.1 误把 emotional_tone 当封闭 Counter, v0.2 改为**开放字段 + 单层语义聚类** (复用 ADR-0013 `_two_tier_cluster` 工具但禁用 secondary phase)
> 2. **L1 prompt 改一行** — 从"7 白名单"扩到"画面情感氛围开放词", 红线区分: "画面属性词" 允许 (诗意/怀旧/静谧/喧闹/温馨/...), "推断用户情绪" 禁止 (happy/depressed/anxious/lonely/...)
> 3. **照片情感 ≠ 用户情绪** — 7 白名单 (relaxed/calm/awe...) 偏"用户体验词", 不能表达画面"诗意/怀旧/戏剧化" 等氛围 (Ace 洞察)

---

## 一、背景

### 1.1 · v0.1 误判 + 现状

v0.1 spec 把 `emotional_tone: str` 当**半封闭** Counter distribution 处理, 实际:
- 字段是 `str` (开放), 不是 Literal
- 7 白名单仅 L1 prompt 引导, 字段层不校验
- LLM 实际可输出任意字符串
- 算法范式应跟 theme/anchor 同 (开放词典 → 语义聚类), 不该用 Counter

### 1.2 · 7 白名单缺陷 (Ace 2026-05-18 提出)

老 7 白名单偏"用户情绪状态", 不是"照片氛围":

| 老 7 白名单 | 倾向 | 画面氛围表达 |
|---|---|---|
| relaxed / calm / quiet / awe / warm / busy | 用户体验词 | 不全 |
| neutral | 默认 | OK |

**缺**: 诗意 / 怀旧 / 静谧 / 戏剧化 / 极简 / 生机 / 神秘 / 喜庆 / 喧闹 / 温馨 / 沉思感 / 梦境感 等画面氛围词.

⚠ **"照片情感表达 ≠ 用户情绪表达"** (Ace 原话): "诗意" 描述画面属性, 是观者对画面的感受; "开心" 推断用户内心, 违反红线 §1.

### 1.3 · v0.1 算法失败模式 (Counter Distribution)

| 场景 | v0.1 Counter share | 应该 | 失败根因 |
|---|---|---|---|
| [calm × 3, quiet × 2] (邻近词) | primary=calm share=0.6 → medium | strong (同"平静"氛围) | Counter 不识同义 |
| [诗意 × 3, 怀旧 × 2] (开放词) | LLM 输出非白名单 → off-list → unknown → none | medium/strong | 不识画面氛围 |
| [neutral × 5] | share=1.0 → 老 0.85 strong (错!) | weak | neutral 是 baseline 不是强信号 |

### 1.4 · A 真值表约束

emotional 是 **辅证** (`auxiliary_signals` 跟 anchor 同档), 真值表 C/E 系列降档信号. **不会单独成集** (无 A-emotional 规则). strong 不需要双重门槛, 单层语义聚类够.

---

## 二、核心算法范式 (方向 B · 单层语义聚类)

### 2.1 · 设计哲学

| 维度 | v0.1 (误判) | **v0.2 (方向 B)** |
|---|---|---|
| 字段类型 | 当半封闭 Literal | **开放 str** (现实) |
| 算法 | Counter distribution | **单层语义聚类** (复用 ADR-0013 工具) |
| 字典 | 7 白名单硬约束 | **开放词典**, L1 prompt 引导 (不字段校验) |
| 邻近度 | 不识 | **embedder 语义识别** (calm ≈ quiet ≈ 静谧, 真模型识同义) |
| neutral 处理 | cap weak | cap weak (保留) |
| 跟 theme/anchor | 不同 | **算法骨架同源** (单层版本) |

### 2.2 · 跟 ADR-0013 复用边界

```
ADR-0013 _two_tier_cluster.build_two_tier_feature 加 enable_secondary 参数:

theme (ADR-0013):  enable_secondary=True, primary=theme_tags, secondary=main_subjects
anchor (ADR-0014): enable_secondary=True, primary=meaning_anchors, secondary=object_anchors
emotional (本):    enable_secondary=False, primary=emotional_tone (单值 list), secondary 跳过
```

emotional 没次字段, 跳过 Phase 3 升降档. **仅用 primary 算 coverage + 主 5 行 grid 判定 band**.

### 2.3 · L1 prompt 改一行 (路径 B 实施时同步)

`src/contracts/l1_output.py::L1Output.emotional_tone` 描述改:

```diff
- "中性情绪基调单字符串. "
- "允许: relaxed / calm / neutral / awe / quiet / warm / busy. "
- "禁止: 推断性情绪(depressed/anxious/lonely/happy). "
- "符合产品红线 §1 '不做情绪推断'."

+ "画面情感氛围单字符串 (中/英文均可, 3-10 字). "
+ "允许: 描述画面属性的氛围词. 例: 静谧 / 诗意 / 怀旧 / 喧闹 / 温馨 / 戏剧化 / 极简 / 生机 / 神秘 / 喜庆 / relaxed / calm / awe / quiet / warm / busy / serene / nostalgic. "
+ "默认: neutral (中性, 无明显氛围). "
+ "禁止: 推断用户内心情绪. 反例: depressed / anxious / lonely / happy / sad / joyful / melancholic. "
+ "区分: '诗意' (画面属性, 允许); '开心' (用户情绪, 禁止). 符合产品红线 §1 '不做情绪推断'."
```

⚠ 字段类型仍 `str` 不变. L1 prompt 阻拦"推断情绪" 词, 但算法层不硬校验.

### 2.4 · 红线诊断 (落痕, 不阻断)

算法层维护**硬编码黑名单** (推断性情绪词):
```python
INFERRED_EMOTION_BLACKLIST = {
    # 中文
    "开心", "悲伤", "忧郁", "焦虑", "孤独", "抑郁", "愤怒", "恐惧",
    # 英文
    "happy", "sad", "depressed", "anxious", "lonely", "melancholic",
    "joyful", "angry", "fearful",
}
```

LLM 若输出黑名单值, 算法**仍正常进 distribution**, 但 EmotionalFeature 落痕字段 `detected_inferred_emotion_count + detected_inferred_emotions` 给上游 LLM / 监控看到"L1 prompt 失效, 红线 §1 被违反", v0.2 触发改 L1 prompt.

---

## 三、核心变量定义 (跟 theme/anchor v0.3 同结构, 仅命名)

| 变量 | 定义 |
|---|---|
| N | 总照片数 |
| N_valid | emotional_tone 非空非默认 ("neutral" 算 valid) 的 photo 数 |
| tag_pool | ⋃ photos.emotional_tone 跨 photos 去重 (单值收集) |
| primary_clusters | 层次聚类后簇 (cosine ≥ 0.75) |
| cluster.hit_rate | 命中该簇的 photo 数 / N |
| emotion_clusters | hit_rate ≥ 0.5 AND hit_count ≥ 2 的簇 |
| primary_coverage | ⋃ emotion_clusters.photos / N |
| primary_dominant_tone | coverage 最高的簇的代表词 |
| is_neutral_baseline | primary_dominant_tone == "neutral" |

---

## 四、判定网格 (6 行)

按行顺序匹配, **EM.4 (neutral_baseline) 优先检测**:

| # | 条件 | band | shape |
|---|---|---|---|
| EM.0 (preempt) | primary 主簇代表词 = "neutral" | weak | neutral_baseline |
| EM.1 | coverage = 1.0 (主簇非 neutral) | **strong** | unanimous_emotion |
| EM.2 | 0.8 ≤ < 1.0 (非 neutral) | medium | dominant_emotion |
| EM.3 | 0.5 ≤ < 0.8 (非 neutral) | medium | mixed_emotion |
| EM.4 | < 0.5 OR no emotion_clusters, N_valid ≥ 2 | weak | scattered_emotion |
| EM.5 | N_valid ≤ 1 (含全 unknown 全空) | none | no_emotion_signal |

⚠ **EM.0 优先级最高**: 即使 primary 主簇 coverage=1.0, 主簇代表词是 "neutral" 也强制 cap weak.

⚠ 跟 theme/anchor 主 grid 区别:
- theme/anchor 主 grid 5 行 + medium 段触发次字段升降档
- emotional 主 grid 6 行 (含 neutral preempt) + 无次字段升降档

---

## 五、Case 验证 (8 个 case 走完整 phase)

### Case A · 全员 awe (EM.1 strong)
```
inputs = [awe, awe, awe, awe, awe]
Phase 1: tag_pool = {awe}, 1 cluster
Phase 2 cluster: hit_rate=1.0, hit_count=5 ≥ 2 ✓ → emotion_cluster
Phase 3 coverage = 5/5 = 1.0
Phase 4 grid: primary_dominant_tone="awe" 非 neutral, coverage=1.0
  → EM.1 strong / shape=unanimous_emotion / rule="EM.1"
```

### Case B · 同义不同字面 (EM.1 strong, v0.2 关键赢点)
```
inputs = [calm, quiet, calm, quiet, relaxed]
Phase 1: tag_pool = {calm, quiet, relaxed}
Phase 2 cluster (复用 ADR-0008 MockEmbedder + 0.75):
  ⚠ mock 表内是否含 calm/quiet/relaxed 同 group? 看 _MOCK_FIXTURE — 当前不含
  mock 跑: 3 个独立簇, 各 hit_count={calm:2, quiet:2, relaxed:1}
  hit_rate: calm=0.4, quiet=0.4, relaxed=0.2 都 < 0.5 → 无 emotion_cluster
Phase 3 coverage = 0 → EM.4 weak

真模型跑 (v0.2 OQ-018 后):
  embedder 识别 calm/quiet/relaxed 同义 → 合并 1 簇
  hit_count=5, coverage=1.0 → EM.1 strong
```

⚠ Case B 暴露 mock 局限 (跟 theme v0.3 Case E 同问题). v0.2 真 Qwen 接入后此 case 自然救.

### Case C · 全员 neutral (EM.0 preempt weak, v0.2 关键修复)
```
inputs = [neutral, neutral, neutral, neutral, neutral]
Phase 1: tag_pool = {neutral}, 1 cluster
Phase 2 cluster: hit_rate=1.0, hit_count=5
Phase 3 coverage = 1.0
Phase 4 grid:
  primary_dominant_tone = "neutral" → is_neutral_baseline=True
  EM.0 preempt → weak / shape=neutral_baseline / rule="EM.0"
(老 v0.1 给 0.85 strong, v0.2 cap weak 修复)
```

### Case D · 4:1 主导 (EM.2 medium)
```
inputs = [诗意, 诗意, 诗意, 诗意, 喧闹]
Phase 1: tag_pool = {诗意, 喧闹}
Phase 2 cluster: 2 簇
  诗意 hit_rate=0.8 ≥ 0.5 ✓
  喧闹 hit_count=1 < 2 ✗ (不入 emotion_cluster)
Phase 3 emotion_clusters = {诗意}, coverage = 4/5 = 0.8
Phase 4 grid:
  primary_dominant_tone="诗意" 非 neutral, coverage=0.8
  → EM.2 medium / shape=dominant_emotion
```

### Case E · 3:2 主导 (EM.3 medium)
```
inputs = [静谧, 静谧, 静谧, 戏剧化, 戏剧化]
Phase 2: 静谧 hit_rate=0.6, 戏剧化=0.4 (< 0.5 不入)
Phase 3 coverage = 3/5 = 0.6
Phase 4: 0.5 ≤ < 0.8, primary="静谧" 非 neutral
  → EM.3 medium / shape=mixed_emotion
```

### Case F · 散乱 (EM.4 weak)
```
inputs = [诗意, 喧闹, 怀旧, 温馨, 极简]
Phase 1: 5 unique tags, mock 表外 → 5 独立簇
Phase 2: 各 hit_count=1 < 2 → 无 emotion_cluster
Phase 3 coverage = 0
Phase 4 grid: < 0.5 + N_valid=5 ≥ 2
  → EM.4 weak / shape=scattered_emotion
```

### Case G · LLM 违反红线 (落痕但仍计算)
```
inputs = [happy, happy, sad, happy, depressed]
Phase 1: 全部仍进 distribution (字段不校验)
  detected_inferred_emotion_count = 5
  detected_inferred_emotions = ["happy", "sad", "depressed"]
Phase 2: happy hit_rate=0.6, sad=0.2, depressed=0.2
  happy hit_count=3 ≥ 2 ✓
Phase 3 emotion_clusters = {happy}, coverage = 3/5 = 0.6
Phase 4: EM.3 medium (假如不 cap)

⚠ 怎么处理? 候选:
  (a) 当成普通 tag, 算法不阻断, 仅落痕 (推荐, 跟红线"软阻拦"对齐)
  (b) 算法层强制 → unknown (违反字段开放性, 不推荐)

(a) 结果: medium + 落痕 inferred_emotion_count=5 给上游 LLM 看到红线被违反
```

⚠ Case G 我推荐 **(a) 仅落痕不阻断**. L1 prompt 才是阻拦的第一道关.

### Case H · 2 张 (EM.1 strong / EM.4 weak 边界)
```
inputs A = [诗意, 诗意]
Phase: 1 cluster, hit_count=2 ≥ 2 ✓, coverage=1.0 → EM.1 strong

inputs B = [诗意, 喧闹]
Phase: 2 簇 each hit_count=1 < 2 → 无 emotion_cluster → coverage=0
  N_valid=2 ≥ 2 → EM.4 weak
```

---

## 六、数据结构 (EmotionalFeature v0.2)

```python
class EmotionalShape(str, Enum):
    """EmotionalFeature.shape 落痕枚举 (ADR-0015 v0.2)."""
    UNANIMOUS_EMOTION = "unanimous_emotion"          # EM.1 strong
    DOMINANT_EMOTION = "dominant_emotion"            # EM.2 medium
    MIXED_EMOTION = "mixed_emotion"                  # EM.3 medium
    NEUTRAL_BASELINE = "neutral_baseline"            # EM.0 weak (preempt)
    SCATTERED_EMOTION = "scattered_emotion"          # EM.4 weak
    NO_EMOTION_SIGNAL = "no_emotion_signal"          # EM.5 none


class EmotionalFeature(BaseModel):
    band: BandLevel
    rule_fired: str = Field(min_length=1)           # "EM.0" / "EM.1" / "EM.3" 等
    score: float = Field(ge=0.0, le=1.0)

    # ─── 聚类诊断 (跟 ThemeFeature / AnchorFeature 同结构) ───
    total_photos: int
    valid_photo_count: int
    tag_pool_size: int
    cluster_count: int
    emotion_clusters: list[list[str]]                # 过阈值簇
    hit_rates: list[float]
    coverage: float
    outlier_photo_ids: list[str]

    # ─── neutral baseline 检测 ──────────────────────────────
    primary_dominant_tone: str | None                # 主簇代表词 (None 表示无主簇)
    is_neutral_baseline: bool                        # primary_dominant_tone == "neutral"

    # ─── 红线诊断 (推断情绪词违规落痕) ─────────────────────
    detected_inferred_emotion_count: int             # 违反红线 §1 的 photo 数
    detected_inferred_emotions: list[str]            # 出现的违规词 (去重)

    # ─── 落痕 ────────────────────────────────────────────────
    shape: EmotionalShape
    primary_signal: str = "emotional_tone"
```

---

## 七、与已落 ADR 关系

| ADR | 共享 / 独立 |
|---|---|
| ADR-0008 MockEmbedder + agglomerative_cluster_cosine | 共享 (跟 theme/anchor 共享 embedder) |
| **ADR-0013 `_two_tier_cluster`** | **共享主字段 phase**, 加 `enable_secondary=False` 参数 跳过 Phase 3 |
| ADR-0014 anchor | 算法骨架同源, 字段不同 |
| ADR-0010/0011/0012 | 输出范式同 (band + shape + rule_fired) |

---

## 八、不变性

1. band 4 档终值, 真值表直读
2. 双阈值 (聚类 0.75 + 主题 0.5) + hit_count ≥ 2
3. **strong 唯一通道**: EM.1 (coverage=1.0 + 主簇非 neutral)
4. **EM.0 preempt 优先**: 主簇代表词=neutral 时强制 cap weak
5. **无次字段**, 单层 grid (跟 theme/anchor 双层不同)
6. **字段保持 `str` 开放**, 不引入 Literal 校验
7. **红线落痕不阻断**: LLM 违反"推断情绪" 仍进 distribution, 仅落痕给上游
8. **L1 prompt 改一行**: 引导画面氛围词, 阻拦推断情绪词
9. **复用 ADR-0013 `_two_tier_cluster` 工具 + `enable_secondary=False`**
10. **emotional 是辅证** (C/E 系列降档信号), 不会单独成集

---

## 九、配置 (新增 `config/path_b_emotional.yaml`)

```yaml
path_b_emotional:

  primary_field: "emotional_tone"

  # 跟 theme/anchor 同阈值
  primary_hit_rate_threshold: 0.5
  min_hit_count: 2

  primary_band_thresholds:
    strong_coverage: 1.0
    medium_high: 0.8
    medium_low: 0.5

  # ─── neutral baseline (emotional 独有) ──────────────
  neutral_baseline:
    enabled: true
    cap_band: "weak"
    neutral_token: "neutral"          # 主簇代表词等于此值 → cap

  # ─── 红线诊断 (硬编码推断情绪黑名单) ────────────────
  inferred_emotion_blacklist:
    chinese: ["开心", "悲伤", "忧郁", "焦虑", "孤独", "抑郁", "愤怒", "恐惧", "高兴", "难过"]
    english: ["happy", "sad", "depressed", "anxious", "lonely", "melancholic", "joyful", "angry", "fearful"]

  # 复用 ADR-0008 配置
  # cluster.merge_similarity = 0.75
  # embedder = MockEmbedder (待 OQ-018 切 Qwen)

  fallback:
    n_valid_min: 1                    # N_valid ≤ 此值 → EM.5 none
```

---

## 十、待决 OQ

### OQ-26a · L1 prompt 改一行的真接入风险
- v0.1 demo 是 mock, prompt 改不影响测试
- v0.2 真 LLM 接入时验证 LLM 是否遵守新指令 (画面氛围 vs 推断情绪)
- 失败率 > 30% → 触发 prompt few-shot 微调

### OQ-26b · 推断情绪黑名单 (中/英) 是否完整
- 当前各 9-10 个常见词, 可能漏 (例: "exhausted" / "frustrated" / "亢奋" / "失落")
- v0.2 真实数据观察 detected_inferred_emotion_count 分布, 扩黑名单

### OQ-26c · neutral cap 严格度
- 当前 EM.0 preempt 主簇代表词=neutral 直接 cap weak
- 候选: 仅当 coverage ≥ 0.6 cap (允许 neutral × 2 + awe × 3 → EM.3 medium)
- 推荐保持严格 (主簇是 neutral 就 cap)

### OQ-26d · MockEmbedder 表外 (跟 theme v0.3 OQ-24d 共享)
- 现 mock 表覆盖小, "诗意/怀旧/静谧" 等画面氛围词全表外
- v0.2 真 Qwen 接入后此问题自然消除

### OQ-26e · 是否引入邻近度 group (方向 A 备选)
- 当前不引入, 信任 embedder 识同义
- v0.2 真实数据若发现"calm/quiet 都 hit_count<2 各自落 weak" 频繁, 考虑加 emotion_groups config

---

## 十一、与老 docs/07 边界对照

| 场景 | 老 v0.1 score | v0.2 band | 体感 |
|---|---|---|---|
| [awe × 5] | 0.85 strong | EM.1 strong | ✓ |
| [awe × 4, busy × 1] | 0.55 weak | EM.2 medium | **新好** |
| [awe × 3, busy × 2] | 0.55 weak | EM.3 medium | **新好** |
| **[neutral × 5]** | 0.85 **strong** ❌ | **EM.0 weak** ✓ | **新好** (neutral 不该 strong) |
| [calm × 3, quiet × 2] (同义) | 0.55 weak | mock: EM.4 / 真模型: EM.1 strong | mock 局限 |
| [诗意 × 5] (开放词) | 0.10 none (off-list) | **EM.1 strong** | **新好** (开放词识别) |
| [happy × 5] (违反红线) | 0.85 strong (错!) | EM.1 strong + 落痕违规 | 仍 strong, 但 LLM 上游可看到 detected_inferred=5 |
| 2 张 [诗意 × 2] | 0.85 strong | EM.1 strong | ✓ |
| 2 张 [诗意, 喧闹] | 0.10 none | EM.4 weak (hit<2) | 微升 |

⚠ **主要变化**:
1. neutral 从 strong 降 weak (修核心 bug)
2. 开放画面氛围词识别 (老算法都 off-list none, 新算法 strong)
3. 推断情绪词违规仍计算 + 落痕诊断 (软阻拦)

---

## 十二、实施清单 (12 步)

| Step | 动作 |
|---|---|
| 1 | 写 `decisions/0015-path-b-emotional-single-tier-cluster.md` |
| 2 | 写 `docs/21_path_b_emotional.md` |
| 3 | 改 `docs/02_data_contracts.md` (EmotionalFeature + EmotionalShape) |
| 4 | 改 `docs/07_dimension_thresholds.md` §emotional 段 (引用 ADR-0015) |
| 5 | 改 `docs/00/01/11/12` (索引 + 架构 + observability + 新增 OQ-026) |
| 6 | 改 `src/contracts/l1_output.py` (emotional_tone description prompt 改一行) |
| 7 | 写 `config/path_b_emotional.yaml` |
| 8 | 改 `src/features/_two_tier_cluster.py` (加 `enable_secondary: bool = True` 参数) |
| 9 | 改 `src/contracts/features.py` (EmotionalFeature + EmotionalShape + FeaturePackage.emotional 字段) + `__init__.py` 导出 |
| 10 | 重写 `src/features/emotional.py` (build_emotional_feature + 调 `_two_tier_cluster.build_two_tier_feature(enable_secondary=False)` + neutral cap 检测 + 红线诊断) |
| 11 | 改 `src/features/assemble.py` (注入 EmotionalFeature) + `src/policy/bands.py` (Bands.emotional 直读) |
| 12 | 单测 + 重生 golden + grep 自检 + 归档 spec |

⚠ **依赖 ADR-0013 (theme) 已落** — 通用工具 `_two_tier_cluster.py` 已存在, 仅加 `enable_secondary` 参数.

---

## 十三、待 Ace 最终审核 (v0.2)

1. **方向 B 范式**: 开放字段 + 单层语义聚类 + 复用 `_two_tier_cluster(enable_secondary=False)`. 确认?
2. **L1 prompt 改一行**: 引导画面氛围词 + 阻拦推断情绪词. 确认?
3. **EM.0 preempt neutral cap weak**: primary 主簇=neutral 整体 cap weak. 确认?
4. **红线落痕不阻断**: 违规词 (happy/sad 等) 仍进 distribution, 仅落痕 `detected_inferred_emotion_count`. 确认?
5. **`enable_secondary` 参数加到 ADR-0013 工具**: 跟 theme/anchor 共享但 emotional 禁用 secondary. 影响向后兼容? (theme/anchor 默认 True, 不破)
6. **关闭/新增 OQ**: 新增 OQ-026 跟踪 5 子问题 (a-e). 无 OQ 关闭 (emotional 之前没独立 OQ).

---

## 十四、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-18 | 初版, 误把 emotional_tone 当半封闭 Counter, 7 行 grid + 白名单硬校验 + neutral baseline |
| v0.2 (draft) | 2026-05-18 | **方向 B 范式**: 开放字段 + 单层语义聚类 (复用 `_two_tier_cluster` 加 `enable_secondary=False`); **L1 prompt 改一行** 扩到画面氛围开放词; 8 个 case 重跑; 6 行 grid + EM.0 preempt; **红线落痕不阻断**; OQ-026 5 子问题; 修订老白名单 7 个 → 开放画面氛围词典 |
