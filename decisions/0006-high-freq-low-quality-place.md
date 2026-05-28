# ADR-0006 · 高频低质量地点判定 (Low Quality Place Detection)

| 字段 | 值 |
|---|---|
| 状态 | accepted (Plan A 默认启用; Plan B 留待 L1 验证失败后) |
| 决策日期 | 2026-05-13 |
| 决策人 | Ace (产品/增长) — 来自 `archive/specs/high_frequency_Place_Detection_Spec.md` v0.2 (2026-05-12, 已归档) |
| 影响范围 | `src/contracts/{low_quality_place,place_anchor}.py` + `src/mini_album/low_quality_place.py` (新) + `src/mini_album/place_anchor.py` (改) + `config/low_quality_place.yaml` (新) + `docs/{10,13,06,02,11,12}` + `tests/fixtures/albums/*.json` |
| 相关文档 | [docs/13_low_quality_place_detection.md](../docs/13_low_quality_place_detection.md) (实现规范) |
| 关联 ADR | 修订 [ADR-0005 §2.1](./0005-place-anchor-dbch.md) 的 `Cluster.is_high_freq` 字段语义 |
| 关联 OQ | 重新决策 [OQ-008 §8g](../docs/12_open_questions.md); 引发 OQ-013/014/015/016 |

---

## 1 · 背景 — 老语义的错

ADR-0005 引入 `Cluster.is_high_freq` 字段, 在 `match_against_cluster` 命中后做"高频地点降一档"(strong→medium...)。

**老逻辑的错**:`is_high_freq` 当时被理解为"位置访问频次"(去得多就降档)。这导致**家附近常去的公园**(高频但纪念意义强)和**家/公司本身**(高频但流水账)同样被降档,把好相册也判散了。

**关键区分**:

| 类型 | 例子 | 是否应降档 |
|---|---|---|
| 高频 + 高质量 | 家附近常去的公园 / 喜欢的咖啡馆 | ❌ 不降档 |
| 高频 + 低质量 | 家 / 公司 / 学校 / 通勤路上 | ✅ 降档 |

判定的实际目标是 **"高频 **+** 低质量"** 的合取,不是单独"高频"。

## 2 · 决策

### 2.1 · 重命名字段语义

`Cluster.is_high_freq` → **`Cluster.is_low_quality`**

- 命名匹配实际语义("高频低质量地点")
- 字段在 `match_against_cluster` 里仍用于触发降档,逻辑无变化
- 但**判定方式**从"build 时投票"改为"match 时实时计算"(见 2.3)

### 2.2 · 双信号判定 (Plan A 默认)

**频率门槛** (必须信号, 不过直接 return False):

```
· user.account_age_days >= 30      (新用户保护期)
· len(user_history) >= 10           (数据量门槛)
· 30 天内该簇 ≥ 5 个不同日子拍摄    (频率信号)
```

**Plan A · L1 双 density** (Plan A 启用时的质量信号):

```
· UserDensityBaseline = user 历史照片 meaning_density / aesthetic_density 各取 25 分位数
· user_history 满足 L1 的照片 < 25 张 → baseline=None → return False (保守)
· 簇内 ≥ 50% 照片满足 (meaning < baseline.meaning AND aesthetic < baseline.aesthetic)
  → 低质量
```

### 2.3 · 实时计算, 不持久化

判定**每次 match 时实时算**:
- 自动遗忘(用户搬家后,旧家自然失去频率)
- 不需要后台 cron job 重算
- `build_place_anchor` 不再决定 cluster.is_low_quality

## 3 · 评估过的备选项与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| 单"高频"信号 (ADR-0005 原版) | 把高频高质量公园误判为低质量,产品偏差大 |
| POI 黑名单 (residential / office) | iOS CLPlacemark 分类粒度粗, "park" 子类经常被错标为 "residential" |
| 用户手动标记 | 体验差,大多数用户不会主动维护 |
| **Plan A: 双 density + 频率门槛** ✅ | 数据已有 (L1 字段), 用户 baseline 防"不会拍照"用户全部误判, 实时计算自动遗忘 |
| Plan B: POI + NIMA + 行为信号 (B/C/D) | Plan A 上线观察后, 验证 L1 双 density 不可用时切换。需 L1 改输出 NIMA |

## 4 · 影响范围

### 契约变更

新增 `src/contracts/low_quality_place.py`:
- `UserDensityBaseline` (meaning_threshold / aesthetic_threshold / last_computed_at)
- `LowQualityResult` (is_low_quality / signal_source / diagnostics)

现有契约修改:
- `src/contracts/place_anchor.py::Cluster`: `is_high_freq: bool` **→** `is_low_quality: bool`(字段名 + description)

### 算法变更

新增 `src/mini_album/low_quality_place.py`:
- `pass_frequency_check(cluster, user, user_history, cfg)` — 频率门槛
- `compute_user_density_baseline(user_history, cfg)` — 用户个人 25 分位
- `signal_l1_density(cluster, l1_data, baseline)` — Plan A 双低占比
- `is_low_quality_plan_a(...)` — Plan A 主入口
- `is_low_quality_plan_b(...)` — 留 stub, NotImplementedError
- `is_low_quality_place(...)` — 主分发(按 config plan_a.enabled / plan_b.enabled 路由)

修改 `src/mini_album/place_anchor.py`:
- `build_place_anchor` 不再 vote `is_high_freq`(因实时计算)。新建 cluster 时 `is_low_quality=False` 默认值。
- `match_against_cluster(new_photo, cluster, context, cfg, user_context=None)` 新增可选参数;有 user_context 时实时调 `is_low_quality_place`, 决定是否降档。

**v0.1 简化**: `user_context=None` 时直接跳过低质量判定(等价不降档), 保证当前 demo 行为不变 (lakeside_album 仍 band=strong, 不被降档)。

### 配置

新增 `config/low_quality_place.yaml`:
- frequency (radius / lookback / min_distinct_days / new_user 保护)
- plan_a (enabled / baseline_percentile / min_samples / double_low_ratio)
- plan_b (默认 disabled, 留 yaml 框架)

### 文档

- 新建 `docs/13_low_quality_place_detection.md` (完整规范)
- 改 `docs/10_mini_album_schema.md` (Cluster 字段 + 降档语义)
- 改 `docs/06_hard_rules.md` (HR-BANDS-01 改为引 ADR-0006)
- 改 `docs/02_data_contracts.md` (UserDensityBaseline + Cluster.is_low_quality)
- 改 `docs/11_observability.md` (match diagnostics 加 `is_low_quality` + `low_quality_reason`)
- 改 `docs/12_open_questions.md` (OQ-008 §8g 重新决策, 新增 OQ-013~016 from spec §九)
- 改 `docs/00_index.md` (索引加 13)
- 改 `docs/01_architecture.md` (mini_album 段)

## 5 · 决策回滚条件

如果 Plan A 在 v0.2 真实数据上验证失败(OQ-013), 触发以下任一即切 Plan B:

- L1 双 density 字段**未准确反映质量**(回放 100 张人工标 case 准确率 < 70%)
- 用户个人 baseline 25 分位**偏差过大**(对 30% 以上用户产生反直觉判定)

回滚动作: `config/low_quality_place.yaml` 设 `plan_a.enabled: false, plan_b.enabled: true`, 代码层 dispatch 切换。

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-008 §8g (is_high_frequency_anchor 判定) | "多数派 is_high_frequency_place 投票" | **被本 ADR 替换** — 改为实时计算 `is_low_quality_place`, 字段重命名 |
| OQ-013 (新增) | — | L1 双 density 字段验证标准 (spec §九 OQ-1) |
| OQ-014 (新增) | — | baseline 25 分位是否合理 (spec §九 OQ-2) |
| OQ-015 (新增) | — | Plan A 失败的判定标准 (spec §九 OQ-3) |
| OQ-016 (新增) | — | Plan B 启用时 L1 改输出 NIMA 的工程改造 (spec §九 OQ-4) |

## 7 · 后续动作

1. ✅ 本 ADR
2. ✅ docs/13 完整规范
3. ✅ 跨文档同步 (10/06/02/11/12/00/01)
4. ✅ 配置 + 契约
5. ✅ 算法实现 + 实时判定接入
6. ✅ Fixture + 单测改造
7. ✅ spec 归档
8. ⏳ v0.2: 接入真实 user_history + L1 baseline 验证 (OQ-013)
9. ⏳ v0.2: 若 Plan A 失败, 切 Plan B (OQ-015/016)
