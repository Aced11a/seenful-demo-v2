# 24 · Feature Assembler 双版本开关 (L2 2.0 / L2 1.0)

> Path B 7 维度算法版本切换 demo 对比.
> 算法依据: [ADR-0018](../decisions/0018-feature-assembler-plan-ab-switch.md).
> L2 1.0 抄本来源: 外部 `L2 Association Engine 工程实现规范 v1.3.md` §3.2 §5.3.

---

## 一、版本对照

| | L2 2.0 (默认, plan A) | L2 1.0 (副, plan B) |
|---|---|---|
| **来源** | ADR-0010~0015 升级版 | v1.3 工程规范 §3.2 抄本 |
| **范式** | 各维度独立算法, 直出 4 档 band | score-based, score → 阈值表 → band |
| **配置 plan 值** | `"L2_2.0"` | `"L2_1.0"` |
| **典型差异场景** | K_outer 散沙识别 / 自然日归属 / 双层语义聚类 / EM.0 neutral preempt | max_distance / time_span / 字面 Jaccard / 字面情绪匹配 |
| **测试范围** | 437 测试全过 | 单元测试 + plan A/B 对比 scenarios |

⚠ 仅 path B 7 维度有版本差异. **Path A / Path C / 真值表 28 条 / HR-PRE / HR-POST / LLM judge / 仲裁器 全部跨版本共享**.

---

## 二、L2 1.0 七维度算法 (v1.3 §3.2 抄本)

### 2.1 · location (v1.3 §3.2.1)

```
max_pairwise_distance = max(haversine(p_i, p_j) for i,j in photos)
if not all photos have GPS: score=0.0
elif max_distance < 200m: score = 1.0 (高频地点 0.5)
elif max_distance < 500m: score = 0.8 (高频地点 0.4)
elif max_distance < 2000m: score = 0.5 (高频地点 0.2)
else: score = 0.1
```

### 2.2 · time (v1.3 §3.2.2)

```
time_span_hours = (max(captured_at) - min(captured_at)) / 3600
all_fallback = all(captured_at_source == "upload_time_fallback")
confidence_factor = 0.5 if all_fallback else 1.0

base_score:
  if time_span < 0.5h: 1.0
  elif time_span < 2h: 0.9
  elif time_span < 12h: 0.7
  elif time_span < 48h: 0.5
  else: 0.2

score = base_score × confidence_factor
```

### 2.3 · theme (v1.3 §3.2.3, schema 适配 scene_type=0)

```
theme_tags_jaccard = jaccard(set(p.theme_tags) for p in photos)
main_subjects_jaccard = jaccard(set(p.semantic_facts.main_subjects) for p in photos)
# scene_type 已从 SemanticFacts 删除 (ADR-0013), 子信号设 0
scene_consistent = 0     # ← ADR-0018 适配, 不破代码

score = 0.5 × theme_tags_jaccard + 0.4 × main_subjects_jaccard + 0.1 × scene_consistent
      ∈ [0, 0.9]
```

### 2.4 · event (v1.3 §3.2.5)

```
event_hints = [p.semantic_facts.event_hint for p in photos]
activities = [p.semantic_facts.activity for p in photos]

event_consistent = len(set(event_hints)) == 1 and event_hints[0] not in ["unknown", None]
activity_consistent = len(set(activities)) == 1 and activities[0] not in ["unknown", None]

if event_consistent: score = 0.9
elif activity_consistent: score = 0.6
else: score = 0.0
```

### 2.5 · anchor (v1.3 §3.2.4)

```
meaning_overlap = jaccard(set(p.semantic_facts.meaning_anchors) for p in photos)
object_overlap = jaccard(set(p.semantic_facts.object_anchors) for p in photos) if 有 else 0
score = max(meaning_overlap, object_overlap)
```

### 2.6 · emotional (v1.3 §3.2.6, 保留 neutral bug)

```
tones = [p.emotional_tone for p in photos]
unique_tones = set(tones)
if len(unique_tones) == 1: score = 0.8   ← ⚠ 5 张 neutral 也 0.8 strong (v1.3 bug 保留)
elif len(unique_tones) <= 2: score = 0.4
else: score = 0.0
```

### 2.7 · people (v1.3 §3.2.7, 复用现简化版)

P0 上限 0.65 不允许 strong, 跟 L2 2.0 一致 (现 `src/features/people.py::compute_people_score` 就是 v1.3 §3.2.7 实现).

**plan A plan B 共享同一份 people 实现** (OQ-009 §9c 未决).

---

## 三、L2 1.0 阈值表 (v1.3 §5.3.5)

| 维度 | 强(≥) | 中(≥) | 弱(≥) | 无(<) |
|---|---|---|---|---|
| location | 0.85 | 0.65 | 0.40 | 0.40 |
| theme | 0.75 | 0.55 | 0.30 | 0.30 |
| event | 0.70 | 0.50 | 0.30 | 0.30 |
| people | 0.70 | 0.50 | 0.30 | 0.30 |
| time | 0.85 | 0.65 | 0.40 | 0.40 |
| anchor | 0.70 | 0.50 | 0.30 | 0.30 |
| emotional | 0.75 | 0.55 | 0.30 | 0.30 |

在 `config/feature_assembler.yaml::legacy_thresholds` 段, 仅 plan=L2_1.0 时生效.

---

## 四、分发实施视图

```
[用户上传 N 张] → run_l2_path_b(photos)
                     │
                     ▼
            assemble_features(photos):
                ├─ if config.plan == "L2_2.0" (默认):
                │     调 build_location_feature / build_time_feature / ...
                │     (ADR-0010~0015, 直出 band)
                │     → FeaturePackage(plan="L2_2.0", location=<LocationFeature>, ...)
                │
                └─ if config.plan == "L2_1.0":
                      调 plan_b/location.py::compute_location_score_legacy / ...
                      → FeaturePackage(
                            plan="L2_1.0",
                            location_score=0.X,
                            location=None,            ← 子 Feature 不填
                            ...
                        )
                     │
                     ▼
            compute_bands(features):
                if features.plan == "L2_1.0":
                    db = config.feature_assembler.legacy_thresholds
                else:
                    db = config.dimension_thresholds.dimension_bands
                # 复用现 _classify(score, db[...]) 逻辑
                     │
                     ▼
            truth_table.lookup(bands) → A1-F1 (共享 28 条, 不分版本)
                     │
                     ▼
            LLM judge / HR-POST / Association (共享)
                     │
                     ▼
            DecisionLog(feature_assembler_plan="L2_2.0" or "L2_1.0", ...)
```

---

## 五、Plan A vs Plan B 行为对比 (5 个边界 case)

### Case 1 · 一致组 (双方 strong)
- 5 张西湖照片, 都在西湖 200m 内, theme=lake×5, event=outing×5
- L2 2.0: location DBSCAN K_outer=1 → strong, theme TH.1 coverage=1.0 → strong → A1
- L2 1.0: max_distance<200m → score=1.0 → strong, theme Jaccard 1.0 → score≈0.5 (主) + 0.4 (次)=0.9 → strong → A1
- **结果一致**: 命中 A1, 成集

### Case 2 · K_outer 散沙
- 4 张西湖 + 1 张商场 (距离 8km)
- L2 2.0: location K_outer=2 SCATTERED → none
- L2 1.0: max_distance ≈ 8000m > 2000m → score=0.1 → none
- **结果一致** (此 case)

### Case 3 · neutral bug 体现 (核心差异)
- 5 张普通日常照片, emotional_tone 都 "neutral"
- L2 2.0: emotional 单层聚类主簇=neutral → EM.0 preempt cap weak
- L2 1.0: 字面一致 → score=0.8 → emotional=strong
- **结果不同**: L2 1.0 可能命中真值表叠加规则出强相册, L2 2.0 weak 不出. **ADR-0015 价值演示**

### Case 4 · 跨日 outing (time 算法差异)
- 6 张周末两天的 outing 照片, 跨 36 小时
- L2 2.0: time T2.1 自然日归属识别"跨日 outing" → strong (ADR-0011)
- L2 1.0: time_span=36h, base=0.5 (12h≤<48h), all_fallback=False → score=0.5 → weak (因 weak 阈值 0.4)
- **结果不同**: L2 2.0 可能 G1/B 类成集, L2 1.0 time 拉低整体. **ADR-0011 价值演示**

### Case 5 · 同义词主题 (theme 语义聚类 vs 字面)
- 5 张照片 tags 分别: [湖边, 水景], [lakeside, lake], [水边], [湖面], [waterfront]
- L2 2.0 (ADR-0013): MockEmbedder fixture 把这些归一到 "lake" 同义簇 → coverage=1.0 → TH.1 strong
- L2 1.0: theme_tags_jaccard = |∩| / |∪| = 0 / 8 = 0.0 → score=0 → none
- **结果不同**: L2 2.0 命中, L2 1.0 不命中. **ADR-0008/0013 语义簇价值演示** (真接 Qwen 后差距更大)

---

## 六、配置

`config/feature_assembler.yaml` (ADR-0018 新建):

```yaml
feature_assembler:
  # 默认 L2_2.0 (现 ADR-0010~0015), 切 "L2_1.0" 走 v1.3 抄本
  plan: "L2_2.0"

  # L2_1.0 阈值表 (v1.3 §5.3.5, 仅 plan=L2_1.0 时生效)
  legacy_thresholds:
    location: {strong: 0.85, medium: 0.65, weak: 0.40}
    theme:    {strong: 0.75, medium: 0.55, weak: 0.30}
    event:    {strong: 0.70, medium: 0.50, weak: 0.30}
    people:   {strong: 0.70, medium: 0.50, weak: 0.30}
    time:     {strong: 0.85, medium: 0.65, weak: 0.40}
    anchor:   {strong: 0.70, medium: 0.50, weak: 0.30}
    emotional:{strong: 0.75, medium: 0.55, weak: 0.30}
```

---

## 七、CLI 切换

```bash
# 默认 L2_2.0
python scripts/run_demo.py full_case5_dispatch_smoke

# 显式 L2_1.0 (覆盖 config)
python scripts/run_demo.py full_case5_dispatch_smoke --plan b

# 或改 config/feature_assembler.yaml plan: "L2_1.0" 重启
```

---

## 八、契约变更

```python
# src/contracts/features.py::FeaturePackage 加 plan 字段
class FeaturePackage(BaseModel):
    plan: Literal["L2_2.0", "L2_1.0"] = "L2_2.0"     # ← ADR-0018 新增, 默认向后兼容
    # ... 原字段不变 (location/time/event/theme/anchor/emotional 子 Feature 都允许 None)

# src/contracts/decision.py::DecisionLog 加 plan 字段
class DecisionLog(BaseModel):
    feature_assembler_plan: Literal["L2_2.0", "L2_1.0"] = "L2_2.0"   # ← ADR-0018 新增
    # ...
```

---

## 九、性能预算

| 操作 | L2 2.0 | L2 1.0 |
|---|---|---|
| location (5 张) | <5ms (DBSCAN + PCA) | <1ms (max_distance) |
| time (5 张) | <2ms (链式切分) | <0.5ms (time_span) |
| theme (5 张) | <10ms (聚类 + 双层 + MockEmbedder) | <0.5ms (Jaccard) |
| event (5 张) | <3ms (primary_share + activity) | <0.5ms (一致性) |
| anchor (5 张) | <10ms (双层聚类) | <0.5ms (Jaccard) |
| emotional (5 张) | <5ms (单层聚类 + neutral preempt) | <0.5ms (字面) |
| people (5 张) | <0.5ms (共享 v0.1) | <0.5ms (共享) |
| **总** | **<40ms** | **<4ms** |

L2 1.0 mock 阶段快 10x. 真 Qwen 接入后两边都被 embedding 调用主导 (~250ms), 算法本身差异淹没.

---

## 十、不变性

1. **真值表 28 条不动**, 跨版本共享
2. **HR-PRE / HR-POST / LLM judge 不动**, 跨版本共享
3. **Path A / Path C 不动**, 跨版本共享
4. **People 维度共享** v0.1 简化版 (OQ-009 §9c 未决)
5. **scene_type 在 L2 1.0 子信号 = 0** (字段已删, 不重新归一化)
6. **emotional neutral bug 在 L2 1.0 保留** (v1.3 原貌)
7. **默认 plan=L2_2.0**, 现 437 测试全过, plan A 不受影响
8. **DecisionLog 标版本号**, 审计可追溯

---

## 十一、关联

**ADR**:
- [ADR-0018](../decisions/0018-feature-assembler-plan-ab-switch.md) (本算法决策)
- 不 supersede 任何 ADR

**docs**:
- [docs/03_truth_table_main.md](./03_truth_table_main.md) (真值表 28 条, 跨版本共享)
- [docs/07_dimension_thresholds.md](./07_dimension_thresholds.md) (v1.3.2 阈值是 L2 2.0 用; legacy_thresholds 在 feature_assembler.yaml 是 L2 1.0 用)
- 各维度 ADR 文档 (ADR-0010~0015), 这些是 L2 2.0 的具体算法

**外部规范**:
- `L2 Association Engine 工程实现规范 v1.3.md` §3.2 §5.3 (L2 1.0 抄本来源)

**OQ**:
- [OQ-029](./12_open_questions.md#oq-029-plan-ab-真实数据对比) (真实数据上线后 commitment_rate / suppress_rate / 误聚合率 对比验证 ADR-0010~0015 价值)
