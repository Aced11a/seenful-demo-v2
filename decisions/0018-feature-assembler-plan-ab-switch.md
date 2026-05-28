# ADR-0018 · Path B Feature Assembler 双版本开关 (L2 2.0 / L2 1.0)

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-19 |
| 决策人 | Ace — 拍板 L2 2.0 主 + L2 1.0 副 / 全局开关 / 保留 v1.3 算法误判 (除 schema 兼容外) |
| 影响范围 | 新增 `src/features/plan_b/` 模块 (7 维 v1.3 §3.2 抄本) + 改 `src/features/assemble.py` 加 plan 分发 + 改 `src/policy/bands.py::compute_bands` 加 plan 阈值源切换 + `src/contracts/features.py::FeaturePackage` 加 `plan` 字段 + `src/contracts/decision.py::DecisionLog` 加 `feature_assembler_plan` 字段 + 新增 `config/feature_assembler.yaml` (含 plan + legacy_thresholds) + 改 `scripts/run_demo.py` 加 `--plan` CLI flag + 新增 `docs/24_feature_assembler_plan_ab.md`; 改 `docs/{00,01,02,07,11,12}` |
| 相关文档 | `docs/24_feature_assembler_plan_ab.md`; 外部规范 `L2 Association Engine 工程实现规范 v1.3.md` §3.2 §5.3 (作 L2 1.0 抄本来源) |
| 关联 OQ | 新增 [OQ-029](../docs/12_open_questions.md#oq-029-plan-ab-真实数据对比) (含 plan A/B 真实数据 commitment_rate / suppress_rate / 误聚合率对比) |
| 关联 ADR | **不 supersede** 任何 ADR; **不影响** ADR-0010~0015 (default plan=L2_2.0 默认走 ADR 升级版); **不动**真值表 28 条 / 生长真值表 10 条 / HR-PRE / HR-POST / Path A / Path C |

---

## 1 · 背景

### 1.1 · 现状

Path B 7 维度算法已经走过两代:
- **L2 1.0** = `L2 Association Engine 工程实现规范 v1.3.md` §3.2.1-3.2.7 的 score-based 实现 (location 单一 max_distance / time 单一 time_span / theme 字面 Jaccard 加权 / event event_hint 一致 / emotional 字面 / anchor Jaccard / people v0.1 简化)
- **L2 2.0** = ADR-0010~0015 升级版 (各维度独立算法, 直出 4 档 band, location 分级 DBSCAN + PCA / time 自然日 + 链式切分 / theme 双层语义聚类 / event primary_share + activity / emotional EM.0 neutral preempt / anchor 双层语义聚类)

L2 2.0 已经在 demo v0.1 跑通, 437 测试全过.

### 1.2 · 引发本 ADR

**演示价值**: KY / Wenyi 看 demo 时, 难以直观感受 ADR-0010~0015 升级的产品价值. 需要"同一组照片, 两种实现给出什么结论"的对比 demo.

**对照成本**: 已经升级的 ADR 想验证收益, 没有"老方案 baseline" 可对比. 真实数据上线 (OQ-021/022/023/024/025/026 共享数据集) 时也需要 baseline 跑分.

**v0.1 demo 阶段实施容易**: 真值表 / HR / LLM / Path A / Path C / 仲裁器都不动, 只换 7 维度内部算法 + score → band 转换. 接入点统一.

### 1.3 · Ace 拍板路线 (2026-05-19)

1. **正规化 ADR** (而非 MVP)
2. **全局开关**: 单一 plan, 所有 7 维一起切, 不混合
3. **L2 2.0 为主**, L2 1.0 副 (demo 对比)
4. **L2 1.0 保留 v1.3 原汁原味**: 算法误判 (emotional neutral / location max_distance / theme 字面 / scene_type) **不修**, 真实展示老方案产品体感
5. **L2 1.0 范围内修**: 仅"跑不起来" 的 schema 兼容 (scene_type 字段已从 SemanticFacts 删除, 用 0 适配)
6. **命名**: Plan A → L2 2.0, Plan B → L2 1.0

---

## 2 · 决策

### 2.1 · 全局开关位置

`config/feature_assembler.yaml` 新建:

```yaml
feature_assembler:
  plan: "L2_2.0"                  # 默认 L2_2.0, demo 切换改 "L2_1.0"

  # L2_1.0 专用阈值表 (v1.3 §5.3.5, 仅 plan=L2_1.0 时生效)
  legacy_thresholds:
    location: {strong: 0.85, medium: 0.65, weak: 0.40}
    theme:    {strong: 0.75, medium: 0.55, weak: 0.30}
    event:    {strong: 0.70, medium: 0.50, weak: 0.30}
    people:   {strong: 0.70, medium: 0.50, weak: 0.30}
    time:     {strong: 0.85, medium: 0.65, weak: 0.40}
    anchor:   {strong: 0.70, medium: 0.50, weak: 0.30}
    emotional:{strong: 0.75, medium: 0.55, weak: 0.30}
```

### 2.2 · 分发点

```
src/features/assemble.py::assemble_features(photos)
  ├─ if plan == "L2_2.0" (默认):
  │    走现 build_*_feature (ADR-0010~0015) → 各维度直出 band
  │    FeaturePackage 含 location/time/event/theme/anchor/emotional 子 Feature 对象
  │
  └─ if plan == "L2_1.0":
       走 src/features/plan_b/*.py (v1.3 §3.2 抄本) → 各维度算 score
       FeaturePackage 子 Feature 字段全部 None, 只填 *_score 字段
       compute_bands 自动 fallback 走 score → 阈值 (legacy_thresholds)
```

### 2.3 · compute_bands 阈值源切换

`src/policy/bands.py::compute_bands` 加 plan 检测:

```python
def compute_bands(features: FeaturePackage) -> Bands:
    if features.plan == "L2_1.0":
        cfg = load_config("feature_assembler.yaml")
        db = cfg["feature_assembler"]["legacy_thresholds"]
    else:  # L2_2.0 默认
        cfg = load_config("dimension_thresholds.yaml")
        db = cfg["dimension_bands"]
    # ... 后续 _classify(score, db[...]) 逻辑共享
```

### 2.4 · DecisionLog 落痕

`DecisionLog.feature_assembler_plan: Literal["L2_2.0", "L2_1.0"]` 每个 log 标版本, 审计 + KY 演示对比都看得到.

### 2.5 · 7 维度 L2 1.0 算法 (抄 v1.3 §3.2 + schema 适配)

| 维度 | L2 1.0 算法 (v1.3 §3.2 抄本) | schema 适配 |
|---|---|---|
| **location** | `max_pairwise_distance` → 200m=1.0 / 500m=0.8 / 2000m=0.5 / 否则 0.1; 高频地点对半折扣 | 无 |
| **time** | `time_span_hours` → 0.5h=1.0 / 2h=0.9 / 12h=0.7 / 48h=0.5 / 否则 0.2; all_fallback ×0.5 | 无 |
| **theme** | `0.5 × theme_tags_jaccard + 0.4 × main_subjects_jaccard + 0.1 × scene_type_consistent` | **scene_type 子信号设 0** (字段已删, 见 §3.1) |
| **event** | event_hint 一致 0.9 / activity 一致 0.6 / 否则 0.0 | 无 |
| **anchor** | `max(meaning_anchors_jaccard, object_anchors_jaccard)` | 无 |
| **emotional** | emotional_tone 字面: 完全一致 0.8 / ≤2 种 0.4 / 否则 0 | **保留 neutral bug** (5 张 neutral → 0.8 strong, 见 §3.2) |
| **people** | people_presence + face_count 粗匹配, P0 上限 0.65 | 复用现 `src/features/people.py::compute_people_score` (已经是 v1.3 简化版, 无需新写) |

---

## 3 · L2 1.0 范围内的 schema 兼容 + 保留 bug

### 3.1 · scene_type 字段已删 (必修 schema 兼容)

v1.3 §3.2.3 theme 加权:
```python
score = 0.5 × theme_tags_jaccard + 0.4 × main_subjects_jaccard + 0.1 × scene_consistent
```

但 `scene_type` 在 ADR-0013 落地时已从 `SemanticFacts` 删除. 直接抄 v1.3 代码 → `AttributeError`.

**适配**: L2 1.0 theme 实现把 `scene_consistent` 当作 0 (相当于权重 0.1 自动从分数里扣掉), score ∈ [0, 0.9]. 不重新归一化 0.5/0.4 (保持 v1.3 原始权重比例).

### 3.2 · emotional neutral bug 保留 (Ace 5/19 拍板)

v1.3 §3.2.6 字面匹配 → 5 张 `emotional_tone="neutral"` 字面一致 → `score=0.8` → strong → 命中真值表 emotional 强叠加 → 出"平淡日常"强相册.

ADR-0015 修了这个 bug (EM.0 preempt 强制 cap weak). L2 2.0 走 ADR-0015, L2 1.0 **保留 bug** 真实展示 v1.3 弱点.

### 3.3 · 不修的其他 v1.3 误判

| v1.3 算法弱点 | L2 1.0 行为 | L2 2.0 对应 ADR |
|---|---|---|
| location 单 max_pairwise_distance 不识别 K_outer 散沙 | 保留, 4 张聚簇 + 1 张远点 = max=远 → weak | ADR-0010 PCA OBB + 形状校正 |
| time 单 time_span 不区分单日/跨日 | 保留, 12h base=0.7 不区分同一天 vs 跨两天 | ADR-0011 自然日归属 + 链式切分 |
| event 单 event_hint 一致 0.9 不识别 activity 一致 边界 | 保留 | ADR-0012 primary_share + activity 二次门槛 |
| theme 字面 Jaccard 跟"同义簇"无关 (湖边 vs lake) | 保留, mock 无差别 (基础 dict 翻译已在 ADR-0008 加, 不通用) | ADR-0013 双层语义簇 |
| anchor 字面 Jaccard | 保留 | ADR-0014 双层语义簇 |

---

## 4 · 替代方案 (评估后未采用)

### 4.1 · MVP 模式 (3 天 不写 ADR)
- **作废**: Ace 5/19 拍板正规化, 走完整 ADR-0018 + docs/24 + 跨文档矩阵

### 4.2 · 每维度独立开关 (混合 plan)
- **作废**: Ace 5/19 拍板全局单一开关, 不混合 (混合配置复杂, 易漂移)

### 4.3 · 修所有 v1.3 误判
- **作废**: Ace 5/19 拍板保留原貌, 真实对比 (修 bug 破坏对比纯度, plan A/B 输出趋同则失去演示价值)

---

## 5 · 实施清单

详见 `docs/24_feature_assembler_plan_ab.md`, 共 12 步, 约 5 天工程量:

1. ADR-0018 (本文档) + docs/24
2. config/feature_assembler.yaml (新建)
3. contracts: FeaturePackage 加 plan / DecisionLog 加 feature_assembler_plan
4. src/features/plan_b/ 7 维 (抄 v1.3 §3.2)
5. src/features/assemble.py 加 plan 分发
6. src/policy/bands.py::compute_bands 加 plan 阈值源切换
7. src/pipeline.py 透传 plan 到 DecisionLog
8. scripts/run_demo.py 加 --plan CLI flag
9. 跨文档矩阵
10. 单测 plan_b 7 维
11. 对比 scenarios (plan A vs plan B 同输入)
12. 收尾 grep + memory + 报告 plan A 影响

---

## 6 · 验证

### 6.1 · 默认行为不变
- 437 现有测试 plan=L2_2.0 (默认), 不破
- `python scripts/run_demo.py` 不带 `--plan` 跑默认 L2_2.0

### 6.2 · Plan A/B 对比 (4 个 scenario)
- `plan_compare_lakeside_5.yaml`: 5 张西湖一致 → 双方 strong
- `plan_compare_kouter_scattered.yaml`: 4 张西湖 + 1 张商场 → plan A SCATTERED none, plan B max_distance 远 none (一致)
- `plan_compare_neutral_5.yaml`: 5 张普通日常 emotional=neutral → plan A weak (EM.0 cap), plan B strong (bug 体现)
- `plan_compare_cross_day_outing.yaml`: 跨 2 天 6 张 outing → plan A T2.1 strong, plan B time_span=36h base=0.5

### 6.3 · grep 自检
- `grep -r "feature_assembler_plan" docs/`
- `grep -r "L2_2.0\|L2_1.0" docs/`

---

## 7 · 关联

**ADR**:
- 不 supersede 任何 ADR
- 扩展 [ADR-0010~0015] (plan=L2_2.0 默认走它们)

**docs**:
- [docs/24_feature_assembler_plan_ab.md](../docs/24_feature_assembler_plan_ab.md) (本算法实施文档)
- [docs/07_dimension_thresholds.md](../docs/07_dimension_thresholds.md) (现 v1.3.2 阈值 + plan B legacy_thresholds 说明)

**代码**:
- `src/features/plan_b/{location,time,theme,event,anchor,emotional}.py` (v1.3 §3.2 抄本)
- `src/features/assemble.py::assemble_features` (plan 分发)
- `src/policy/bands.py::compute_bands` (plan 阈值源切换)
- `src/contracts/features.py::FeaturePackage.plan`
- `src/contracts/decision.py::DecisionLog.feature_assembler_plan`
- `config/feature_assembler.yaml`

**OQ**:
- [OQ-029](../docs/12_open_questions.md#oq-029-plan-ab-真实数据对比) (plan A vs B 真实数据 commitment_rate / suppress_rate / 误聚合率对比)
