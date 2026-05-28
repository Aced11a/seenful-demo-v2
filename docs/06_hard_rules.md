# 06 · 全路径硬规则

> Policy Engine 100% 执行,LLM 无权覆盖。配置:不可热更,定义在代码内(常量)以避免被误调。
> 全路径分三层:**前置 (pre)** / **后置 (post)** / **仲裁 (arbitration)**。

---

## 一、路径 B (L2 主) 硬规则

### 前置硬规则 (Stage 1) · 命中即 suppress

| ID | 规则 | 触发条件 | 处置 |
|---|---|---|---|
| HR-PRE-01 | 敏感照片 | 任一 photo `sensitive_level >= medium` | display=suppress, decision_source=pre_filter_reject |
| HR-PRE-02 | 全部敏感 | 100% 照片 `sensitive_level >= medium` | suppress, reason=all_sensitive |
| HR-PRE-03 | 全部 fallback 时间且无 GPS | 所有 `captured_at_source=upload_time_fallback` 且无 `exif_location` | suppress, reason=weak_fallback_time_only |
| HR-PRE-04 | 最低 3 张门槛 | photo_count < 3 | 不进 L2 评估(v0.1 直接 suppress; v0.2 加 light_judge_only 2 张路径) |

### 分档阶段 · 高频低质量地点降一档 (ADR-0006)

| ID | 规则 |
|---|---|
| HR-BANDS-01 | 命中 cluster 的 `is_low_quality=true`(高频 + 双 density 低)→ location band 降一档 (strong→medium, medium→weak, weak→none) |

⚠ **语义变更 (ADR-0006)**: 老语义是"位置访问频次"降档(把"家附近的公园"和"家"一起降);新语义是"高频 + 低质量"合取(只降"流水账类"高频地点)。详见 [docs/13_low_quality_place_detection.md](./13_low_quality_place_detection.md)。

判定**实时计算, 不持久化** — 由 `src/mini_album/low_quality_place.py::is_low_quality_place` 在 match_against_cluster 时调用, 依赖 `user_context` (user / user_history / l1_data / baseline)。

v0.1 demo: `user_context=None` → 不判低质量 → 不降档 (兼容当前测试)。

⚠ **距离档位 (ADR-0007 v0.1 测试期)**: location band 计算用**单一档** strong/medium/weak = 500m/1000m/2000m, 不下钻 context. 三档表保留为 yaml 注释, OQ-017 触发回切. 本规则 (HR-BANDS-01) 对 band 的降档语义不受 ADR-0007 影响.

### 后置硬规则 (Stage 6)

| ID | 规则 | 触发条件 | 处置 |
|---|---|---|---|
| HR-POST-01 | 弱关联绝不成集 | final_strength = `weak`/`light` | display=show_inline_hint |
| HR-POST-02 | none 强度静默 | final_strength = `none` | display=suppress |
| HR-POST-03 | 高频地点 + 无叠加 | location=强(降档前) + theme/event 均 < 中 | 强制 final_strength ≤ medium |
| HR-POST-04 | medium 及以上成集 | final_strength ∈ {medium, strong} 且 photo_count ≥ 3 | display=show_mini_album |
| HR-POST-05 | path_hint=light_judge_only | 2 张模式 (v0.2 才接入) | 上限 light |

---

## 二、路径 A (动态生长) 硬规则

### 前置硬规则 (候选集层) · 已在 `candidate_builder/growth_scan.py` 实现

| ID | 规则 |
|---|---|
| HRG-PRE-01 | 新照片 `sensitive_level >= medium` → 整个路径 A 跳过 |
| HRG-PRE-02 | 老相册 `is_growing=false` → 该相册不进候选 |
| HRG-PRE-03 | 老相册 `growth_lock_at <= now` (已过 30 天锁) → 该相册不进候选 |
| HRG-PRE-04 | 老相册 `photo_count >= max_photo_capacity` → 该相册不进候选 (触发续集机制) |
| HRG-PRE-05 | 新照片 `photo_id in excluded_photo_ids` → 该相册不进候选 |

### 后置硬规则 (Step 5 · `policy/growth_engine.py`)

| ID | 规则 | 触发条件 | 处置 |
|---|---|---|---|
| HRG-POST-01 | 敏感照片兜底 | new_photo `sensitive_level >= medium` | decision_tier 强制 = no_merge |
| HRG-POST-02 | 高频地点抑制 | `is_high_frequency_place=true` + bands.theme/event 均 < medium + 真值表 auto_merge | auto_merge 降为 ask_user |
| HRG-POST-03 | 多相册冲突仲裁 | new_photo 命中 ≥ 2 本相册 | 按 (location_band 优先 → last_updated_at 最新) 排序选一本, 其他作废 |
| HRG-POST-04 | 容量满触发续集 | 命中相册 `photo_count >= max_photo_capacity` | 创建续集 (v0.1 未实现, 跳过) |
| HRG-POST-05 | 排除列表兜底 | new_photo.photo_id in album.excluded_photo_ids | 强制 no_merge (候选集层应已过滤, 兜底防御) |
| LLM_REJECT_DOWNGRADE | LLM 复核反对 | `LLMJudgement.accept=False` 且 tier ≠ no_merge | auto_merge → ask_user, ask_user → no_merge |

---

## 三、路径 C (兜底回扫) 硬规则

### 前置硬规则 (`candidate_builder/backfill_scan.py`)

| ID | 规则 |
|---|---|
| HRC-PRE-01 | 新照片 `sensitive_level >= medium` → 整个路径 C 跳过 |
| HRC-PRE-02 | 候选池过滤: `uploaded_at < now - 30 days` 的沉淀单图剔除 |
| HRC-PRE-03 | 候选池过滤: `sensitive_level >= medium` 的沉淀单图剔除 |
| HRC-PRE-04 | 候选池过滤: 已在任何 mini_album 的照片剔除 (传入 `already_in_album_ids`) |
| HRC-PRE-05 | 候选池过滤: `backfill_excluded_global=true` 的照片永不再回扫 |

### 粗筛 (`backfill_scan._passes_coarse`) · 任一命中即视为候选

- GPS 距离 < 1 km
- theme_tags Jaccard > 0.5
- event_hint 一致 (且非 unknown)

最多保留 **5 张候选** (配置 `backfill.coarse_filter.max_candidates`)。

### 兜底封顶 (Step 4 · `policy/backfill_engine.py`)

⚠ **三条 cap 必须同时全部满足**才允许 `create_new_album`,否则 `no_backfill`:

| ID | 规则 | 通过条件 |
|---|---|---|
| BACKFILL-CAP-01 | bounds_max 必须 strong | 主真值表命中 A 系或 B7/8/9 (bounds_max=strong) |
| BACKFILL-CAP-02 | LLM 必须 strong | LLM.proposed_strength = strong |
| BACKFILL-CAP-03 | 召回数量足够 | 召回沉淀单图 ≥ 2 张 (加新照片满足 ≥3 张最低成集) |

任何一条失败 → `decision_tier = no_backfill`。
召回 < 2 张时直接 `decision_tier = insufficient_candidates` (与 no_backfill 区分,语义更精确)。
通过后最多取**前 4 张**沉淀单图 + 新照片 (`backfill.max_recall_photos=4`)。

> ⚠ **ADR-0017** (2026-05-19): 三条 caps **完全保留, 不删不改**. cascade_backfill_single (ADR-0017 新入口) 仍然调 `apply_backfill_caps`. v0.2 spec "删 caps + 改调 run_l2_path_b 内核" 路线**作废** (违反 PRD §3.10.5 "strong 以上" 门槛).
>
> ADR-0017 在 caps 之前加一层"维度强度总分排序选 top 4" (event 权重 0.5), 详见 [docs/23](./23_pipeline_cascade_backfill.md). HR-PRE / HR-POST 仍是 path B 单独跑, **cascade 不共享 path B HR-PRE/POST** (cascade 走的是 caps 三条).

---

## 四、三路仲裁 (`arbitration/merge_results.py`)

### 严格优先级 (4 个 Case)

| Case | 触发 | 走 | 作废 |
|---|---|---|---|
| Case 1 | 路径 A 命中 (auto_merge / ask_user) | path_A | B + C 全部作废 |
| Case 2 | A 未命中 + B 命中 (show_mini_album) | path_B | C 作废 |
| Case 3 | A + B 都未命中 + C 命中 (create_new_album) | path_C | — |
| Case 4 | 三路全空 | 单图沉淀 | — |

### 策略 3 禁用 (硬规则)

❌ **不允许"搭车并入"**:路径 A 命中时, 不允许同时把沉淀单图也搭车并入老相册。
**理由**: 避免相册边界漂移和身份稀释。
**实现**: Case 1 命中后, 路径 C 结果整体作废 (即使 C 命中 strong), 不去找"可一起并入"的沉淀单图。

### A.ask_user 用户拒绝后

⚠ 用户拒绝并入 ask_user 提示后:
- 该照片**单图沉淀**, **不重新走任务 C** (避免循环)
- 写入候选老相册 `excluded_photo_ids`

v0.1 不模拟用户响应, ask_user 的最终 ending 标记为 `ask_user_pending`。

---

## 五、不可逾越的产品红线

来自 `CLAUDE.md`,**任何代码分支违反以上任一,视为 P0 bug**:

1. 不做情绪推断
2. 不引用人的缺席
3. 2 张永远不成集
4. 同图唯一归属
5. 弱关联绝不成集
6. 敏感照片强制 suppress
7. 高频地点不能仅凭 GPS 自动并入
8. L1 落库即权威

| 红线 | 体现在哪 |
|---|---|
| 1 / 2 | L1 文学化字段语义边界 (见 `docs/02_data_contracts.md` §L1 文学化字段语义边界) |
| 3 | HR-PRE-04 |
| 4 | 路径 A 候选集筛选 + 仲裁器策略 3 禁用 |
| 5 | HR-POST-01 / HR-POST-02 |
| 6 | HR-PRE-01 / HR-PRE-02 + HRG-POST-01 + HRC-PRE-01 |
| 7 | HR-BANDS-01 (新语义见 ADR-0006: 高频低质量地点降档) + HR-POST-03 + HRG-POST-02 |
| 8 | (架构层约束, 任何下游不得回写 L1 字段) |
