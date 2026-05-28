# 12 · Open Questions

> 实现中遇到的歧义清单。解决后转 ADR 保留追溯。
>
> 格式约定:
> - 每条 OQ 含 **状态 / 优先级 / 子问题清单 (checkbox) / 完成条件 (DoD) / 关联追溯 / 状态变更**
> - 子问题用 markdown `- [ ]` checkbox, 决策后改 `- [x]` + 写上选定方案
> - 全部子问题 + DoD 完成 → 这条 OQ 转 ADR 归档

## P0 未决问题速查

| OQ | 标题 | 优先级 | 状态 |
|---|---|---|---|
| [OQ-008](#oq-008-小集指纹合成-mini-album-fingerprint-synthesis) | 小集指纹合成 | **P0** | 部分解决 (§8a/8b/8c/8f/8g 完成, §8d/8e/8h/8i 待决) |
| [OQ-009](#oq-009-多维度匹配分档-multi-cross-算法严格度) | 多维度匹配分档 (multi-cross) | **P0** | 待决策, Ace 接 OQ-008 后处理 |
| [OQ-010](#oq-010-user_home_city-推断模块实现) | user_home_city 推断模块 | **P0** | 临时 stub (硬编码), v0.2 实现 |
| [OQ-011](#oq-011-相册-anchor-完全为空场景) | 相册 anchor 完全为空场景 | P1 | 待澄清 |
| [OQ-012](#oq-012-dbscan-eps-参数调优) | DBSCAN eps 参数调优 | P0.5 | 临时经验值 |
| [OQ-013](#oq-013-l1-双-density-字段验证标准) | L1 双 density 验证标准 (Plan A 可用性) | **P0** | 待 L1 真实数据回放 |
| [OQ-014](#oq-014-baseline-25-分位是否合理) | baseline 25 分位是否合理 | P0.5 | 临时经验值 |
| [OQ-015](#oq-015-plan-a-失败的判定标准) | Plan A 失败的判定标准 | **P0** | 待 v0.2 上线观察 |
| [OQ-016](#oq-016-plan-b-启用时-l1-改输出-nima-的工程改造) | Plan B 启用时 L1 改输出 NIMA | P0.5 | Plan A 失败后启动 |
| [OQ-017](#oq-017-poi-城市判定接入后-location-档位回切计划) | POI 城市判定接入后 location 档位回切 | P0.5 | OQ-010 完成后触发 |
| [OQ-018](#oq-018-qwen-真实-embedding-接入与基准测试) | Qwen3-Embedding-0.6B 接入 + 基准测试 | **P0** | v0.2 接入, 当前 mock |
| [OQ-019](#oq-019-语义聚类参数调优) | 语义聚类参数调优 (merge_similarity / relative_threshold / bands) | P0.5 | 真数据上线后调 |
| [OQ-020](#oq-020-event-枚举与聚合调优) | event 枚举与聚合调优 (含 spec §十 6 个 OQ-EV) | P0/P0.5 | L1 真接入 + 真数据后调 |
| [OQ-021](#oq-021-adr-0010-接受边界的真实数据验证) | ADR-0010 接受边界的真实数据验证 (市内 chain / 沿江长条 / U 形栈道) | P0.5 | v0.2 真实数据上线后 |
| [OQ-022](#oq-022-adr-0011-接受边界的真实数据验证) | ADR-0011 接受边界的真实数据验证 (eps / T1.5 升 strong / T3 收紧 / 凌晨归属 vs overnight 冗余 / 时区 / T2.3 误伤) 10 子问题 | P0.5 | v0.2 真实数据上线后 |
| [OQ-023](#oq-023-adr-0012-接受边界的真实数据验证) | ADR-0012 接受边界的真实数据验证 (band 阈值 / activity 2/3 / 兜底范围 / sports 子类接受 / B 系列兼容性) 6 子问题 | P0.5 | v0.2 真实数据上线后 |
| [OQ-024](#oq-024-adr-0013-接受边界的真实数据验证) | ADR-0013 path B theme 接受边界 (双阈值 / min_hit_count / 次字段聚类 / mock 局限 / 升降档幅度) 5 子问题 | P0.5 | v0.2 真实数据上线后 |
| [OQ-025](#oq-025-adr-0014-接受边界的真实数据验证) | ADR-0014 path B anchor 接受边界 (修订 OQ-008 §8e / 阈值独立 / mock 中文 / 辅证地位) 5 子问题 | P0.5 | v0.2 真实数据上线后 |
| [OQ-026](#oq-026-adr-0015-接受边界的真实数据验证) | ADR-0015 path B emotional 接受边界 (L1 prompt 改一行风险 / 黑名单完整性 / neutral cap / mock 局限 / 邻近度 group) 5 子问题 | P0.5 | v0.2 真实数据上线后 |
| [OQ-027](#oq-027-adr-0016-接受边界的真实数据验证) | ADR-0016 location geocoder + 4 档接受边界 (GPS 量化 / 海外 fallback / 重试 / 缓存持久化 / 搬家检测) 5 子问题 | P0.5 | v0.2 真实数据上线后 |
| [OQ-005](#oq-005-用户-home_city-数据缺失时默认按哪种上下文走) | home_city 缺失默认 | P1 | 临时决策 (与 OQ-010 重叠) |
| [OQ-006](#oq-006-embedding-模型在生产环境的部署形态) | embedding 部署形态 | P1 | 待决策 |
| [OQ-007](#oq-007-embedding-缓存的失效策略) | embedding 缓存失效 | P2 | 临时决策 |

---

## OQ-001: G1 evidence 质量分门槛在 v0.1 mock 阶段如何处理?

**状态**: 临时决策
**发现时间**: 2026-05-12
**发现场景**: 实现 truth_table.py G 系列时
**问题**:
  G1 文档要求 "LLM evidence 质量分 ≥ 2 才允许 strong,否则封顶 medium"。
  v0.1 用 mock LLM,evidence 是构造的,没有真实质量评分。

**临时决策**:
  v0.1 mock 阶段默认 evidence_quality = 1 (不达标),G1 上限 medium。
  v0.2 真 LLM 接入时重新讨论实现方式。

**影响范围**: G1 真值表行为
**关联代码**: `src/policy/truth_table.py` G1 分支

---

## OQ-002: B8 / B9 与 B1-B6 优先级在"三个主载体=中"时如何排序?

**状态**: 临时决策
**问题**:
  当 location=中 + theme=中 + event=中 时,B1 (location+theme) 和 B7 (location+theme+event) 都满足。
  按"信息量更高优先"原则应命中 B7。

**临时决策**:
  实现顺序 B7 → B8 → B9 → B1-B6。即 B7 优先,B8 / B9 优先于 B1-B6。
  B 系列内部按"覆盖度高的优先",符合"strong→strong"应被优先识别。

**影响范围**: B 系列命中顺序
**关联代码**: `src/policy/truth_table.py`

---

## OQ-003: time_is_fallback 的全局降权是否进入 time_score 本身?

**状态**: 已决策
**决策**:
  fallback 降权在 `features/time.py` 内 ×0.5,score 已经降权后输出。
  分档时直接用 score 查表,不再额外处理。
  这样 decision_log step2 的 `time_score` 就是"考虑了 fallback 后的最终分",一目了然。

**关联代码**: `src/features/time.py`

---

## OQ-004: E1 / E2 中"≥2 个主载体=弱"如何统计?

**状态**: 已决策
**决策**:
  统计 4 个主载体 (location, theme, event, people) 中 band ∈ {"weak"} 的数量 ≥ 2 视为触发。
  band="none" 不算"弱",不参与计数。

**关联代码**: `src/policy/truth_table.py` E 分支

---

## OQ-005: 用户 home_city 数据缺失时,默认按哪种上下文走?

**状态**: **已关闭 (ADR-0016, 2026-05-18)** — 高德 reverse geocoding API 返回 country 默认 "中国"; admin=None 时兜底 "市内" (跟老 home_city 保守策略一致)
**发现时间**: 2026-05-12
**发现场景**: 实现 v1.3.2 location_score 新方案时
**问题**:
  新方案 §3.2.1 需要 user_profile.home_city 来判定 LocationContext。
  当用户是新注册 / 30 天内上传 < 10 张 / GPS 长期缺失时, home_city 无法计算,
  context=unknown。此时应该套哪张阈值表?

**候选**:
  - (A) 按 home_city 表 (最严)        → 容易判散, 但避免误聚合
  - (B) 按 cross_province 表 (适中)   → 允许同省内更大跨度
  - (C) 抛出错误, score=0.0           → 用户体验崩坏

**推荐方案**: (A) home_city 保守
**理由**:
  - Seenful 早期用户大概率本地拍照,home_city 表语义对齐度最高
  - "宁少误聚合,不要错聚合" (符合 CLAUDE.md 红线 §5 弱关联绝不成集)
  - 数据足够后自动切换,无需用户感知

**配置位置**: `config/dimension_thresholds.yaml` `home_city_detection.fallback_context: home_city`
**待决策人**: Ace
**关联代码**: `src/features/location.py` (待实现)

---

## OQ-006: embedding 模型在生产环境的部署形态?

**状态**: 待决策
**发现时间**: 2026-05-12
**发现场景**: 实现 v1.3.2 theme_overlap_score 新方案时
**问题**:
  §3.2.3 需要调 embedding 服务 (BGE-M3 / Qwen3-Embedding-0.6B)。
  部署形态会影响延迟、成本、隔离性。

**候选**:
  - (A) **本地推理服务** (Docker + Triton / vLLM-embedding)
    - 优点: 延迟低 (<50ms), 数据不出网, 单 tag 成本接近 0
    - 缺点: 占 GPU 资源, 自己维护
  - (B) **第三方 API** (硅基流动 / TogetherAI / Anthropic 暂无)
    - 优点: 零运维, 按调用量计费
    - 缺点: 延迟 200ms+, 长期成本随调用量线性, 数据外发
  - (C) **混合: 本地 + 缓存 + 异步 fallback**
    - 优点: 综合最优
    - 缺点: 复杂度高

**推荐方案**: 长期 (A),短期 (B) 验证产品形态后再决
**理由**:
  - L2 Feature Assembler 是 hot path,延迟敏感
  - BGE-M3 模型 ~600MB,单 GPU 可承载,本地化可行
  - 但 P0 阶段先用 (B) 验证产品判定正确性,避免过早投入

**关联文档**: ADR-0004 §6 回滚条件 (embedding 服务 P99 > 800ms 触发)
**待决策人**: KY (工程)
**关联代码**: `src/features/theme.py` (待实现)

---

## OQ-007: embedding 缓存的失效策略?

**状态**: 临时决策 (推荐永不失效)
**发现时间**: 2026-05-12
**发现场景**: 实现 v1.3.2 theme_overlap_score 工程考量时
**问题**:
  tag 级 embedding 调用频次极高 (每张照片 5-10 tag, 每天数万张),
  必须缓存。但 embedding 模型迭代 (BGE-M3 → BGE-M4) 时, 缓存内向量与新模型不兼容。

**候选**:
  - (A) **永不失效**, 仅在切换 embedding_model 时手动清缓存
  - (B) TTL 30 天滚动失效
  - (C) 按模型版本分 key (key = tag + model_version)

**推荐方案**: (C) 按模型版本分 key
**理由**:
  - tag 语义本身极稳定 ("夕阳" 一年后仍是夕阳),不需要 TTL
  - 切换 embedding_model 时, 新 key 不冲突, 旧 key 自然冷却退场
  - 操作简单, 无需手动清

**当前配置**: `config/dimension_thresholds.yaml` `theme_overlap.cache.ttl_seconds: null` (永不失效, 待 (C) 方案确认后增加 model_version 维度)
**待决策人**: KY (工程)
**关联代码**: `src/features/theme.py` (待实现)

---

## OQ-008: 小集指纹合成 (Mini Album Fingerprint Synthesis)

**状态**: 待决策, **未实现**
**优先级**: **P0** (路径 A 的全部前置, 当前 fixture 手填)
**发现时间**: 2026-05-13
**发现场景**: Ace 审计 fingerprint 生成流程
**当前 hack**: `tests/fixtures/albums/lakeside_album.json` 手填; `src/mini_album/` 目录不存在

**问题**:
  路径 A (动态生长) 需要老相册的"指纹"做匹配, 包括 `place_anchor.gps_center` / `theme_tags_set` / `dominant_theme` / `dominant_event_hint` / `anchors_set`. v0.1 没有实现从照片 L1 聚合的代码, 也没决定指纹**生成**和**更新**算法.

### 子问题清单 (逐项决策, 每项独立可处理)

- [x] **8a · gps_center 算法** — **2026-05-13 已解决 (ADR-0005)**
  - **选定**: DBSCAN 簇 centroid (多簇, 非单一几何中心)
  - 实现: `src/mini_album/place_anchor.py::build_place_anchor`
  - 后果: 相册可有多 cluster, 每 cluster 自己的 centroid

- [x] **8b · theme_tags_set 聚合规则** — **2026-05-14 已解决 (ADR-0008)**
  - **选定**: 字面集合 → **语义簇** (theme_clusters), 跳过 ①②③ 三个原方案
  - 实现: `src/mini_album/theme_aggregation.py::aggregate_theme_clusters`
  - 算法: 层次聚类 (cosine + average linkage, threshold = 1 - 0.75) + 频次加权聚合 + 自然断层截断
  - 后果: `MiniAlbumFingerprint.theme_tags_set` 字段被删, 替换为 `theme_clusters: list[SemanticCluster]`

- [x] **8c · dominant_theme 计算** — **2026-05-14 失效 (ADR-0008)**
  - **选定**: 移到 Mini Album 完整 schema (LLM 综述展示字段), 不在 fingerprint 内, 算法不用
  - 后果: `MiniAlbumFingerprint.dominant_theme` 字段被删

- [x] **8d · dominant_event_hint 计算** — **2026-05-14 已解决 (ADR-0009)**
  - **选定**: 字面单值 → **EventAggregation 三级分层** (primary/secondary/tertiary), 跳过"最高频"原方案
  - 实现: `src/mini_album/event_aggregation.py::aggregate_event`
  - 算法: 占比 ≥ 0.6 为 primary, ≥ 0.2 为 secondary, count ≥ 1 为 tertiary
  - 后果: `MiniAlbumFingerprint.dominant_event_hint` 字段被删, 替换为 `event_agg: EventAggregation`
  - L1 枚举从 6 扩到 10 (删 family_visit/festival, 新增 gathering/celebration/performance/sports/work/study)

- [x] **8e · anchors_set 聚合** — **2026-05-18 修订 (ADR-0014)**
  - **老推荐**: 合并 set, 不频次过滤
  - **v0.3 修订**: **不再合并**, 改主次分层 (meaning 主 + object 次, ADR-0014)
  - 理由: meaning_anchors 抽象 (天光/树影/慢下来) 是相册"灵魂", object_anchors 具体 (扶梯/楼) 是"物体", 重要性显然不同, 合并丢分层信号
  - 实现: 跟 ADR-0013 theme 同算法骨架 (`_two_tier_cluster`), 仅字段抽取器换
  - 注: 路径 A anchor 聚合是否同步分层待 P1 决策

- [x] **8f · gps_radius_m 计算** — **2026-05-13 已解决 (ADR-0005)**
  - **选定**: 凸包 + 衰减 buffer 取代单一半径
  - 实现: hull = `convex_hull(cluster_points)`; `buffer = base / (1 + alpha × ln(n))`
  - 后果: 形状由 hull 描述, 置信度由 buffer 描述, 越用越准但永不归零

- [x] **8g · is_high_frequency_anchor 判定** — **2026-05-13 重新决策 (ADR-0006 取代 ADR-0005 老版本)**
  - **老选定 (ADR-0005)**: cluster 级 `is_high_freq` 用簇内 `is_high_frequency_place` 多数派(语义错: 只看频次)
  - **新选定 (ADR-0006)**: 字段重命名 `is_high_freq` → `is_low_quality`, 改为**实时计算** `is_low_quality_place(cluster, user, user_history, l1_data, baseline, cfg)`
  - 判定: 频率门槛 + 双 density 双低占比 (Plan A); 详见 `docs/13_low_quality_place_detection.md`
  - 实现: `src/mini_album/low_quality_place.py`

- [~] **8h · 指纹更新策略** — **部分解决 (ADR-0005)**
  - place_anchor: ③ 增量 + 每 10 张全量重跑 DBSCAN (ADR-0005)
  - theme_tags_set / dominant_theme / anchors_set 的更新策略**仍待**
  - 推荐留 v0.2 与真 LLM 接入对齐

- [ ] **8i · growth_lock_at 后是否完全冻结**
  - 锁定后, dominant_* / theme_tags_set 是否还能微调?
  - **推荐**: 完全冻结. 锁后任何新照片走兜底 / 沉淀, 不再吸入

### 完成条件 (DoD)

- [x] 9 个子问题分别决策 (8a/8b/8c/8f/8g 已落地, 8h 部分; 8d/8e/8i 仍待决)
- [x] `src/mini_album/place_anchor.py::build_place_anchor` 实现 (ADR-0005)
- [x] `src/mini_album/theme_aggregation.py::build_theme_clusters` 实现 (ADR-0008)
- [ ] `src/mini_album/event_anchor.py` (event/anchor 维度的 build/update, 待 8d/8e 决策后实现)
- [x] `tests/fixtures/albums/lakeside_album.json` 含 place_anchor (DBCH) + theme_clusters (语义簇 + mock embedder 真实 centroid)
- [x] `docs/10_mini_album_schema.md` 总览 + `docs/14_theme_aggregation.md` 专项 完整规范
- [x] 单测覆盖 8a-8c/8f/8g 决策路径; 8d/8e/8h/8i 待
- [x] 已写 ADR-0005 / ADR-0006 / ADR-0008; 8d/8e/8h/8i 决策时再追加

### 关联

**文档**:
- `docs/04_truth_table_growth.md` §指纹三件套 (使用方, theme/location 已 cross-link, event/anchor 仍占位)
- `docs/10_mini_album_schema.md` (place_anchor + theme_clusters 已落, event/anchor 待)
- `docs/14_theme_aggregation.md` (theme 完整规范, ADR-0008)
- `SCHEMA_REFERENCE.md` §3 Mini Album (字段定义)

**代码**:
- `src/contracts/growth.py::MiniAlbumFingerprint` (字段定义, ADR-0008 后 删 theme_tags_set/dominant_theme, 加 theme_clusters)
- `src/contracts/theme.py::SemanticCluster` (ADR-0008)
- `src/mini_album/place_anchor.py::build_place_anchor` (ADR-0005)
- `src/mini_album/theme_aggregation.py::build_theme_clusters` (ADR-0008)

**关联 OQ**: 解决 OQ-008 是 OQ-009e (路径 A 1v1 升级) 的前置 — theme 已通过 ADR-0008 解决 (语义簇加权匹配本质就是 1-vs-aggregated 改良); event/anchor 待

### 状态变更

- 2026-05-13: 创建, 待决策, Ace 接手处理

---

## OQ-009: 多维度匹配分档 (Multi-cross 算法严格度)

**状态**: 待决策
**优先级**: **P0** (影响所有路径命中率)
**发现时间**: 2026-05-13
**发现场景**: Ace 审计 path B/C/A 的多维度比对算法
**当前 hack**: 全部维度用严格交集 / 全员一致 multi-cross, 1 张离群照片 = score 0

**问题**:
  v0.1 多维度匹配 (theme/event/people/anchor) 使用了"**严格交集 / 全员一致**"的 multi-cross:
  - **theme / anchor**: `jaccard_multi` 取严格交集 / 并集 — 1 张离群照片把 score 拉到 0
  - **event / people**: 要求全部照片一致, 否则严重降分

  例: 4 张照片 tags = `[a,b,c]` × 3 + `[d,e,f]` × 1 → 严格交集 = `∅` → score = 0 → band = none
  人直觉: 前 3 张明显一组, 第 4 张是噪声, 不该让其毁掉整体信号

  此外 **路径 A 1 vs 聚合指纹** 把"新照片与某张老照片完全一致"的强信号稀释了 (J(new, union) 因 union 变大而降低)

### 子问题清单

- [x] **9a · theme jaccard_multi 严格交集 → ?** — **2026-05-18 已关闭 (ADR-0013)**
  - **选定**: 不是 v1.3.2 双向最大池化, 而是 **双层字段 cluster + 升降档** (ADR-0013 v0.3)
  - 实现: `src/features/_two_tier_cluster.py` + `src/features/theme.py::build_theme_feature` 重写
  - 主字段 theme_tags + 次字段 main_subjects, 复用 ADR-0008 MockEmbedder + cluster_tags
  - 引发: [OQ-024](#oq-024-adr-0013-接受边界的真实数据验证)

- [x] **9b · event 严格全员一致 → ?** — **2026-05-18 已关闭 (ADR-0012)**
  - **选定**: 不是 v0.1 推荐的"多数派 ②", 而是 **event primary_share + activity 二次门槛** (Y/A/2/3, ADR-0012)
  - 实现: `src/features/event.py::build_event_feature` 重写
  - 算法: E.1 (event=1.0 + activity ≥ 2/3) strong / E.2-E.6 medium-weak / E.7 兜底 weak / E.8 none
  - 后果: 老 score=0.2 大量升 medium (B 系列命中率↑); strong 严格化 (1 张离群不再 strong)
  - 引发: [OQ-023](#oq-023-adr-0012-接受边界的真实数据验证) 真实数据验证

- [ ] **9c · people 严格一致 → ?**
  - 同 9b
  - **推荐**: ② 多数派

- [x] **9d · anchor jaccard_multi 严格交集 → ?** — **2026-05-18 已关闭 (ADR-0014)**
  - **选定**: 双层字段 cluster + 升降档 (主 meaning + 次 object), 复用 ADR-0013 工具
  - 实现: `src/features/anchor.py::build_anchor_feature`
  - 引发: [OQ-025](#oq-025-adr-0014-接受边界的真实数据验证)

- [ ] **9e · 路径 A: 1 vs 聚合指纹 → ?**
  - ① 不改 (保持当前 1 vs union)
  - ② 1 vs each old photo, 取 max(`J(new, old_i)`)
  - ③ 1 vs each old photo, 取 mean
  - **推荐**: ② max (信号最强), **但依赖 OQ-008 落实**(需要存档每张老照片 L1 才能逐张比)
  - **依赖**: OQ-008

- [ ] **9f · 各路径同名维度算法是否要统一**
  - 例: theme 在 B 是 `0.5×jaccard(tags) + 0.4×jaccard(subjects) + 0.1×scene_consistency`, 在 A 仅 `jaccard(tags, set)`
  - **推荐**: v1.3.2 接入 embedding 池化后再讨论 (届时 B 和 A 都用同算法, 自然统一)

- [ ] **9g · 各路径分档阈值是否独立**
  - 当前所有路径共享 `dimension_bands.{location/theme/event/anchor}` 同一组数值
  - 但 path A 的 score 算法**比 path B 简单**, 用同样阈值导致 G-B1/G-B3 几乎死规则
  - ① 不拆 (留 v1.3.2 重写时全校准)
  - ② 加 `path_a_bands` / `path_c_bands` 子段
  - **推荐**: ① 不拆 (v1.3.2 ADR-0004 会全重做)

### 完成条件 (DoD)

- [ ] 7 个子问题全部决策
- [ ] 选定要做的子问题 (推荐至少 9b + 9c), 实现 + 单测
- [ ] 不做的子问题, 在 `decisions/0004-feature-assembler-revision.md` 里**显式列出**"v1.3.2 覆盖" vs "OQ-009 留待"
- [ ] golden 同步刷新 (如改动 event/people 算法)

### 关联

**文档**:
- `docs/07_dimension_thresholds.md` (阈值)
- `docs/03_truth_table_main.md` (路径 B 真值表消费 bands)
- `docs/04_truth_table_growth.md` (路径 A 真值表消费 bands)
- `decisions/0004-feature-assembler-revision.md` (部分覆盖 9a/9d/9g, 不覆盖 9b/9c/9e/9f)

**代码**:
- `src/features/theme.py::build_theme_feature` (9a, ADR-0013 已关闭)
- `src/features/event.py::build_event_feature` (9b, ADR-0012 已关闭)
- `src/features/people.py::compute_people_score` (9c, 仍 v0.1)
- `src/features/anchor.py::build_anchor_feature` (9d, ADR-0014 已关闭)
- `src/features/growth_features.py` (9e, 路径 A 待决)

**关联 OQ**: 9e 依赖 OQ-008 (照片级数据存档)

### 状态变更

- 2026-05-13: 创建, 待决策, 排在 OQ-008 之后处理

---

## OQ-010: user_home_city 推断模块实现

**状态**: **§10a/§10b 已关闭 (ADR-0016, 2026-05-18)** — 高德 reverse geocoding API 直出 country/province/city/district 4 级; admin=None 时兜底"市内"/"国外". §10c (搬家检测) + §10d (多 home_city) 仍待 P1.
**优先级**: **P0** (DBCH context 判定前置依赖)
**发现时间**: 2026-05-13
**发现场景**: 实施 ADR-0005 时
**当前 hack**: `src/mini_album/user_home_city.py::infer_user_home_city` 从 `config/place_anchor.yaml::demo_home_city_stub` 硬编码读取 user_demo → (30.26, 120.13, 30km)

**问题**: DBCH 需 user 常驻城市判 photo context. 真实推断需查 30 天 GPS 频次最高市级行政区.

### 子问题清单

- [ ] **10a · 聚类粒度** (city/district/province?) — 推荐 city
- [ ] **10b · 数据不足回退** — 推荐 home_city 保守 (同 OQ-005)
- [ ] **10c · 用户搬家检测** — 推荐滚动 30 天窗口自然衰减
- [ ] **10d · 多 home_city** (常住多城) — 推荐 P0 单, P1 升级支持多

### 完成条件

- [ ] 4 个子问题决策 + 真实实现 + 接 user_profile + 单测

### 关联

- `src/mini_album/user_home_city.py` (当前 stub)
- [ADR-0005](../decisions/0005-place-anchor-dbch.md) §2.2

### 状态变更

- 2026-05-13: 因 ADR-0005 落地引入, demo 用 stub

---

## OQ-011: 相册 anchor 完全为空场景

**状态**: 待澄清
**优先级**: P1
**发现时间**: 2026-05-13
**发现场景**: 从 ADR-0005 spec §十二 OQ-002 转入

**问题**: ADR-0005 §2.6 场景 C "相册完全为空" 真的会发生吗? 应防御性返回 band="none" 还是 raise?

当前实现: `match_new_photo` 返回 `MatchResult(band="none", reason="empty_anchor")` (单测 `test_empty_anchor_returns_none` 已覆盖).

### 子问题清单

- [ ] **11a · 上游约束是否保证不会发生** (无 GPS 照片本就不应进 album)
- [ ] **11b · 防御性处理**: 返回 none + 监控日志 vs raise

### 完成条件

- [ ] 确认上游约束
- [ ] 加监控日志 (若保留防御处理)

### 关联

- `src/mini_album/place_anchor.py::match_new_photo` 场景 C
- [ADR-0005](../decisions/0005-place-anchor-dbch.md)

### 状态变更

- 2026-05-13: 从 ADR-0005 spec OQ-002 转入

---

## OQ-012: DBSCAN eps 参数调优

**状态**: 临时经验值
**优先级**: P0.5 (真实数据上线前)
**发现时间**: 2026-05-13
**发现场景**: 从 ADR-0005 spec §六 OQ-001 转入

**问题**: `config/place_anchor.yaml::dbscan.eps_m` 是经验值 (home=200m / province=400m / country=800m). Spec 提出"是否应按 1.5× strong 重新校准?"

### 子问题清单

- [ ] **12a · 调优数据集**: 用什么? 推荐 P0.5 接真用户数据后取 100 本人工标注
- [ ] **12b · 调优 metric**: 误聚率 / 漏聚率 / F1?  推荐 F1
- [ ] **12c · 是否 per-user 个性化** — 推荐 P1 再说

### 完成条件

- [ ] 真实数据 grid search + 写 ADR-NNNN 记录最终 eps

### 关联

- `config/place_anchor.yaml::dbscan.eps_m`
- [ADR-0005](../decisions/0005-place-anchor-dbch.md) §6

### 状态变更

- 2026-05-13: 从 ADR-0005 spec OQ-001 转入

---

## OQ-013: L1 双 density 字段验证标准

**状态**: 待 L1 真实数据回放
**优先级**: **P0** (Plan A 可用性的前置)
**发现时间**: 2026-05-13
**发现场景**: 实施 ADR-0006 Plan A
**问题**: ADR-0006 Plan A 依赖 L1 输出的 `meaning_density` / `aesthetic_density` 真实反映照片质量. 如果 L1 模型对家/公司流水账照片也给出高 density, Plan A 失效, 需切 Plan B (OQ-016).

### 子问题清单

- [ ] **13a · 准确率门槛**: 100 张人工标 case 上, Plan A 与人工判断一致率达多少视为可用? — 推荐 ≥ 70%
- [ ] **13b · 测试样本构造**: 怎么标? 谁标? 标几张? — 推荐 100 张, Wenyi (prompt QA) 标
- [ ] **13c · 失败时降级路径**: 立刻切 Plan B 还是先关 plan_a.enabled? — 推荐先关, 等 Plan B 工程改造完成 (OQ-016) 再启用

### 完成条件 (DoD)

- [ ] 真实数据回放完成 + 准确率出报告
- [ ] 决策: 启用 Plan A / 切 Plan B

### 关联

- [ADR-0006](../decisions/0006-high-freq-low-quality-place.md) §5 回滚条件
- [docs/13](./13_low_quality_place_detection.md) §四 Plan A

### 状态变更

- 2026-05-13: 从 ADR-0006 spec §九 OQ-1 转入

---

## OQ-014: baseline 25 分位是否合理

**状态**: 临时经验值
**优先级**: P0.5 (上线观察后调)
**发现时间**: 2026-05-13
**发现场景**: ADR-0006 §2.2 Plan A
**问题**: spec 用用户个人 meaning_density / aesthetic_density 25 分位作为"低质量阈值". 但 25 分位本身是经验值, 实际可能偏紧 / 偏松.

### 子问题清单

- [ ] **14a · 网格搜索范围**: 20 / 25 / 30 分位
- [ ] **14b · 多用户敏感性**: 不同拍照习惯的用户阈值表现差异

### 关联

- `config/low_quality_place.yaml::plan_a.baseline_percentile`

### 状态变更

- 2026-05-13: 从 ADR-0006 spec §九 OQ-2 转入

---

## OQ-015: Plan A 失败的判定标准

**状态**: 待 v0.2 上线观察
**优先级**: **P0**
**发现时间**: 2026-05-13
**发现场景**: ADR-0006 §5 回滚条件
**问题**: Plan A 上线后多久 / 怎么算"失败"切 Plan B? 用 OQ-013 的准确率 + bad case 率?

### 子问题清单

- [ ] **15a · 观察期长度**: 2 周 / 1 个月 / 3 个月
- [ ] **15b · 失败判定指标**: 准确率 + bad case 率 + 用户主动投诉?

### 关联

- [ADR-0006](../decisions/0006-high-freq-low-quality-place.md) §5

### 状态变更

- 2026-05-13: 从 ADR-0006 spec §九 OQ-3 转入

---

## OQ-016: Plan B 启用时 L1 改输出 NIMA 的工程改造

**状态**: Plan A 失败后启动
**优先级**: P0.5
**发现时间**: 2026-05-13
**发现场景**: ADR-0006 Plan B (留 stub, 未实现)
**问题**: Plan B 用 NIMA (Neural Image Assessment) 评分替代 density. L1 模型需要改输出 NIMA 字段; baseline 需要"去污染"算法; POI 需要客户端 CLGeocoder + MKLocalSearch.

### 子问题清单

- [ ] **16a · L1 模型改造**: 加 NIMA 输出字段的工作量评估
- [ ] **16b · 客户端 POI 接入**: iOS / Android 实现
- [ ] **16c · 去污染算法验证**: spec §五 "防 baseline 污染" 是否有效

### 关联

- `archive/specs/high_frequency_Place_Detection_Spec.md` §五 (Plan B 完整描述)
- `src/mini_album/low_quality_place.py::is_low_quality_plan_b` (stub)

### 状态变更

- 2026-05-13: 从 ADR-0006 spec §九 OQ-4 转入

---

## OQ-017: POI 城市判定接入后 location 档位回切计划

**状态**: **已关闭 (ADR-0016, 2026-05-18)** — 高德 reverse geocoding 接入 + 4 档升级 (市内/省内/国内/国外, strong=500/1000/1500/2000m) 完成回切. ADR-0007 标 superseded.
**优先级**: P0.5 (回切动作本身是 v0.2 必做项, 而非 v0.1 待决)
**发现时间**: 2026-05-14
**发现场景**: [ADR-0007](../decisions/0007-unified-location-bands.md) v0.1 测试期把 location 距离档位塌缩为单一表 (500/1000/2000m), 三 context 表保留为 yaml 注释. POI 城市判定 (CLGeocoder / 行政区聚类, OQ-010 子问题 10a) 接入后需触发回切.

**问题**:
本 OQ 不是"该不该回切" — 回切是 ADR-0007 §5 明确约定的 + ADR-0005 三档原方案的承诺. 本 OQ 是**怎么回切**:
- 何时触发? POI 接入 = 立即回切, 还是先 dual-run 两套档位验证?
- 真实数据上三档表本身是否需要重新校准? 即"原 100/300/800 vs 500/1500/5000 vs 2000/5000/15000"是否还合适?
- v0.2 切换期, golden 怎么处理? (golden 期望值会跟着档位变)

### 子问题清单

- [ ] **17a · 回切触发条件**
  - ① POI 接入即切 (一行 feature flag)
  - ② POI 接入 + dual-run 1 周, 误差 < 5% 才正式切
  - **推荐**: ② dual-run (避免 stub→真实 home_city 切换带来的 silent 回归)

- [ ] **17b · 三档阈值真实校准**
  - 原三档来自 ADR-0004 经验值, 待真实 100+ 用户数据回放校准
  - 与 [OQ-012](#oq-012-dbscan-eps-参数调优) (DBSCAN eps) 联动调优
  - **推荐**: 与 OQ-012 同一批数据上 grid search

- [ ] **17c · 切换期 golden 策略**
  - golden 文件包含距离档位输出
  - 切换 PR 必然刷新所有涉及 location 的 golden
  - **推荐**: 切换 PR 强制重生 golden + 人工审 diff (避免单测自动通过掩盖回归)

- [ ] **17d · OQ-005 (home_city 缺失默认) 重新生效**
  - ADR-0007 期间 OQ-005 失效 (不读 context 阈值)
  - 回切后 OQ-005 决策 (推荐 home_city 保守) 自动恢复, 无需额外动作
  - **推荐**: 切换 PR Description 显式提示 OQ-005 重新生效

### 完成条件 (DoD)

- [ ] OQ-010 (user_home_city 真实实现) 完成
- [ ] 17a/17b/17c 决策完成 + 数据校准完成 (如选 ② 路径)
- [ ] 一行 feature flag 切换 + 全部 golden 重生
- [ ] yaml 删除 `unified_*` 段, 取消三 context 段注释
- [ ] `src/mini_album/place_anchor.py::distance_to_band` 恢复 `cfg[context]` 下钻
- [ ] ADR-0007 状态从 accepted 改为 superseded, 写 ADR-NNNN 记录回切

### 关联

**文档**:
- [ADR-0007](../decisions/0007-unified-location-bands.md) (本 OQ 的来源 + 回切计划)
- [ADR-0004](../decisions/0004-feature-assembler-revision.md) §2.1 (原三档定义)
- [ADR-0005](../decisions/0005-place-anchor-dbch.md) §2.3 (原 DBCH 三档使用)
- [docs/10](./10_mini_album_schema.md) §2.3 §2.4 (回切后恢复 per-context 表 + buffer)
- [docs/07](./07_dimension_thresholds.md) §3.2.1 (location_score 三档)

**代码**:
- `src/mini_album/place_anchor.py::distance_to_band` (回切目标)
- `src/mini_album/place_anchor.py::match_against_cluster` (buffer base 回切目标)

**关联 OQ**: 依赖 OQ-010 (user_home_city 推断); 联动 OQ-012 (DBSCAN eps); OQ-005 (home_city 缺失默认) 回切后恢复生效

### 状态变更

- 2026-05-14: ADR-0007 落地引入, 待 OQ-010 完成后处理

---

## OQ-018: Qwen 真实 embedding 接入与基准测试

**状态**: 待 v0.2 接入 (当前 mock)
**优先级**: **P0** (路径 A theme 算法上线前置)
**发现时间**: 2026-05-14
**发现场景**: [ADR-0008](../decisions/0008-theme-semantic-clustering.md) §2.5 决定 v0.1 用 MockEmbedder, 真模型 v0.2 接

**问题**: ADR-0008 的 theme 算法正确性需要真 embedding 验证语义识别质量 (湖边/水边/湖面 是否被合并). Mock 只测**逻辑正确性**, 不测**模型本身**.

### 子问题清单

- [ ] **18a · 基准测试 case 集**: 100 张? 谁标? — 推荐 100 张, Wenyi (prompt QA) 标
- [ ] **18b · 准确率门槛**: 同义词识别准确率 ≥ ? — 推荐 ≥ 60%
- [ ] **18c · 部署形态**: 本地 sentence_transformers / API / 混合 — 沿用 OQ-006 决策
- [ ] **18d · 缓存策略**: tag 级永久缓存 (字面稳定), 还是按 model_version 分 key — 沿用 OQ-007 (C 方案)
- [ ] **18e · 失败兜底**: ADR-0008 §2.5 明确 demo 不要兜底, v0.2 上线时是否需 SLA 保护? — 推荐: 上线观察 P99 后再定

### 完成条件 (DoD)

- [ ] 接 Qwen3-Embedding-0.6B 真模型 + 100 case 基准测试
- [ ] 同义词识别准确率出报告
- [ ] 决策: 启用 / 回滚 (回滚条件见 ADR-0008 §5)

### 关联

- [ADR-0008](../decisions/0008-theme-semantic-clustering.md) §2.5 + §5
- [docs/14](./14_theme_aggregation.md) §七 (Embedding 服务)
- [OQ-006](#oq-006-embedding-模型在生产环境的部署形态) (部署形态, 共享决策)
- [OQ-007](#oq-007-embedding-缓存的失效策略) (缓存策略, 共享决策)

### 状态变更

- 2026-05-14: ADR-0008 落地引入

---

## OQ-019: 语义聚类参数调优

**状态**: 临时经验值
**优先级**: P0.5 (真数据上线后调)
**发现时间**: 2026-05-14
**发现场景**: [ADR-0008](../decisions/0008-theme-semantic-clustering.md) §2 决定的 4 个参数都是经验值

**问题**: `config/theme_aggregation.yaml` 中 4 个参数都是凭直觉:

| 参数 | 当前值 | 含义 |
|---|---|---|
| `merge_similarity` | 0.75 | cosine > 该值合并为同簇 |
| `relative_threshold` | 0.4 | 频次 ≥ max × 该值 才保留 |
| `band_thresholds.strong` | 0.75 | 加权和 ≥ 该值 strong |
| `band_thresholds.medium` | 0.55 | medium |
| `band_thresholds.weak` | 0.35 | weak |

### 子问题清单

- [ ] **19a · merge_similarity 调优**
  - 太低: 不相关 tag 被强行并簇 (湖 + 桥 合并)
  - 太高: 同义 tag 不合 (湖边 / 水边 不合)
  - 推荐: 0.65 / 0.75 / 0.85 grid search

- [ ] **19b · relative_threshold 调优**
  - 太低: 长尾噪声进指纹 (1 次出现的 tag 也保留)
  - 太高: 重要次级主题被截掉 (主簇太大压制次簇)
  - 推荐: 0.3 / 0.4 / 0.5 grid search

- [ ] **19c · band_thresholds 重校**
  - 现值与 ADR-0004 §3.2.3 路径 B band 阈值 (0.85/0.70/0.55) 不同, 需观察人工标注上是否产生体感差异
  - 推荐: 真实数据上每路径独立校准

- [ ] **19d · 联动 OQ-018**
  - 真 Qwen 接入后再调参 (mock 调出来的参数不可用)

### 完成条件 (DoD)

- [ ] OQ-018 完成
- [ ] 真实数据 + 人工标注上做 grid search
- [ ] 写 ADR-NNNN 记录最终参数 + 校准过程

### 关联

- [ADR-0008](../decisions/0008-theme-semantic-clustering.md)
- `config/theme_aggregation.yaml`
- [docs/14](./14_theme_aggregation.md)

### 状态变更

- 2026-05-14: ADR-0008 落地引入

---

## OQ-020: Event 枚举与聚合调优

**状态**: 待 L1 真接入 / 真数据上线
**优先级**: P0 (枚举验证) / P0.5 (阈值调优)
**发现时间**: 2026-05-14
**发现场景**: [ADR-0009](../decisions/0009-event-aggregation.md) 落地, spec §十 6 个 OQ-EV 合并转入

**问题**: ADR-0009 把 L1 event_hint 从 6 扩到 10, 并引入三级分层聚合 (primary/secondary/tertiary). 多个参数和判定标准是经验值, 需真数据验证.

### 子问题清单

- [ ] **20a · primary_threshold 调优**: 当前 0.6, 是否调到 0.55 / 0.65? (spec OQ-EV-1)
  - 太低: 刚过半就强匹配, 混合相册被错判 primary
  - 太高: 主导事件难达成, primary 长期为 None
  - 推荐: 真数据 grid search 0.55 / 0.6 / 0.65

- [ ] **20b · secondary_threshold 调优**: 当前 0.2, 是否合理? (spec OQ-EV-2)
  - 太低: 偶发 event 进 secondary 拉高 medium 匹配率
  - 太高: 真实次主导丢失
  - 推荐: 真数据 grid search 0.15 / 0.2 / 0.25

- [ ] **20c · tertiary_min_count 调优**: 当前 1, 单次 LLM 噪点是否被错放进 weak? (spec OQ-EV-3)
  - 单次 LLM 失误 → unrelated event 进 tertiary → 后续新照片可能 weak 命中
  - 推荐: 改 2 (至少 2 次出现才进 tertiary)

- [ ] **20d · L1 unknown 占比验证** (spec OQ-EV-4): 新 prompt 上线后, unknown 比例是否 ≤ 10%?
  - 真接入后回放 100 张人工标注
  - 失败 → 改 L1 prompt few-shot 提升覆盖

- [ ] **20e · celebration 强符号优先级稳定性** (spec OQ-EV-5): 互斥优先级中 celebration 强符号 (蛋糕/婚纱) 是否稳定优先?
  - 待测: 多事件叠加场景 (生日蛋糕 + 餐桌 → 应判 celebration 不是 meal)
  - 推荐: 接 L1 后 case 测试

- [ ] **20f · daily_record 占比验证** (spec OQ-EV-6): 上线后 daily_record 比例是否降到 10-15%?
  - 上线后监控
  - 失败 → 扩枚举或重审优先级表

### 完成条件 (DoD)

- [ ] L1 真接入完成 + 100 张人工标注 case
- [ ] unknown 占比 / daily_record 占比验证
- [ ] 4 个阈值参数 grid search
- [ ] 写 ADR-NNNN 记录最终参数

### 关联

**文档**:
- [ADR-0009](../decisions/0009-event-aggregation.md)
- [docs/15_event_aggregation.md](./15_event_aggregation.md)
- `config/event_aggregation.yaml`

**代码**:
- `src/mini_album/event_aggregation.py`
- `src/contracts/l1_output.py::EventHint`

**关联 OQ**: 与 OQ-018 (Qwen embedding 接入) 共享 v0.2 真接入时间窗.

### 状态变更

- 2026-05-14: ADR-0009 落地引入, 合并 spec §十 6 个 OQ-EV

---

## OQ-021: ADR-0010 接受边界的真实数据验证

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-15
**发现场景**: [ADR-0010](../decisions/0010-path-b-location-dbch-pca-shape.md) 落地, §2.8 / §2.9 接受 3 个边界场景假设, 需 v0.2 真实数据验证

**问题**: ADR-0010 路径 B location 算法设计阶段对 3 个边界场景做了"接受 / 暂不修"的选择, 均为产品/算法判断, 未经真实数据验证:

1. **市内 chain 接受度** (ADR-0010 §2.8): DBSCAN 单链可达带来"路上点把两簇合成 K_outer=1" 默认接受为合理 (产品语义: 上午 A + 中午路上 + 下午 B 是一次出游故事). 真实数据上是否有比例可观的"假合并"被误判 medium?

2. **沿江步道 5.5km 直线散步** (ADR-0010 §2.9): L > 5 硬边界, 任何超 5km 直线都判 none. 真实场景"长江/秦淮河/钱塘江沿岸散步" 是否高频被误杀?

3. **U 形栈道 (τ > 4) 不降档** (ADR-0010 §2.9): τ > 4 表示来回穿梭, 但场景"小景点内来回走多遍" 可能 τ 极大但实际同点, 不降档是设计意图. 真实数据上"该判散却没判散"的案例占比?

### 子问题清单

- [ ] **21a · 市内 chain 误合并率**
  - v0.2 收集 100 个真实"K_outer=1 + shape=stretched" 案例, 人工标"真同次活动" vs "假合并"
  - 阈值: 假合并率 > 30% → 需补 HR-POST-LOC-01 (location.shape=stretched + time 多事件信号 [例: TimeFeature.events_per_day 单日 ≥ 2 cluster 或 max_inter_cluster_gap_h ≥ 4] → 降一档)
  - 推荐: P0.5 收集, P1 决策

- [ ] **21b · 沿江长条 ≥ 5km 高频度**
  - v0.2 真实数据上"location 维度判 none, 但 LLM/人工判该 strong/medium 的样本", 看其中"沿江/沿河长条"占比
  - 阈值: > 15% → 加 K_inner=1 + W < 0.5 + L ≤ 8 → weak/medium 逃生口
  - 联动: OQ-017 (POI 接入后 eps 弹性) 可顺带把 cross_province 档 eps 拉大覆盖

- [ ] **21c · U 形 / 来回穿梭 误判率**
  - v0.2 真实数据上"τ > 4 但实际反例 (例: 3 个不同地点来回走)" 占比
  - 阈值: > 20% → 启用 τ > 4 降档 (ADR-0010 §2.5 明示不做的部分)
  - 推荐: 沿用 ADR-0010 §2.5 不做; 真实数据反证强烈再补

- [ ] **21d · DBSCAN eps_outer = 1500m 弹性**
  - 与 OQ-017 联动: POI 城市判定接入后, 路径 B location eps_outer 是否也按 context 分级 (home_city 1km / cross_province 2km / cross_country 3km)
  - 同时影响 eps_inner / gap 阈值

### 完成条件 (DoD)

- [ ] v0.2 真实数据 100+ 案例人工标注
- [ ] 21a-c 各自统计指标出报告
- [ ] 决策: 沿用 ADR-0010 / 启用某个补丁 / 写新 ADR

### 关联

**文档**:
- [ADR-0010](../decisions/0010-path-b-location-dbch-pca-shape.md) §2.5 / §2.8 / §2.9 (接受/不修边界)
- [docs/16_path_b_location.md](./16_path_b_location.md) §七 (场景验证)

**代码**:
- `src/features/location.py` (ADR-0010 实现)
- `config/path_b_location.yaml` (阈值)

**关联 OQ**: 与 [OQ-017](#oq-017-poi-城市判定接入后-location-档位回切计划) 共享 v0.2 真实数据时间窗 — POI 接入后 path B eps 弹性与 path A 档位回切可一起评估.

### 状态变更

- 2026-05-15: ADR-0010 落地引入, 接受 3 个边界假设转入本 OQ 跟踪

---

## OQ-022: ADR-0011 接受边界的真实数据验证

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-18
**发现场景**: [ADR-0011](../decisions/0011-time-natural-day-event-clustering.md) 落地, Time_Aggregation_Spec.md v0.2 §十一 列出 10 个接受/不修边界 (a-j)

**问题**: ADR-0011 路径 B time 算法设计阶段对 10 个边界 / 临时阈值做了"接受/暂不修"或"留 OQ 跟踪"的选择, 均为产品/算法判断, 未经真实数据验证.

### 子问题清单

- [ ] **22a · eps_minutes = 120 调优**
  - 90 / 120 / 180 grid search
  - 100+ 案例人工标"是否同事件" 验证 events_per_day 准确率
  - 推荐 P0.5 真数据后调

- [ ] **22b · T1.5 extended_chain 升 strong 回滚条件**
  - v0.2 决议: events∈[3,5] gaps<4h span≤12h → strong (修问题④ 断层)
  - 回滚条件: 真实数据 T1.5 误判率 > 30% (人工 review "连续多事件" 实际不该 strong) → 回 medium
  - 关联: Time_Aggregation_Spec.md §十一 OQ-22b

- [ ] **22c · T3 cap medium 收紧验证**
  - Ace 2026-05-15 明示 K_days ≥ 3 不进 strong
  - 回滚条件: "3-7 天连续游" 漏判率 > 30% → 放宽 T3.1 到 strong (写新 ADR)
  - 关联: Time_Aggregation_Spec.md §十一 OQ-22c

- [ ] **22d · 跨夜 12h 阈值**
  - 候选 10h / 12h / 14h
  - 推荐 12h (用户合理睡眠 + 早起)
  - 真数据 case study 后调

- [ ] **22e · 0-6 点归"前一日 night"**
  - 风险: 夜班 / 凌晨工作者 体感不一致
  - 真实数据上 < 5% 用户受影响, 接受
  - 关联: Time_Aggregation_Spec.md §十一 OQ-22e

- [ ] **22f · 真值表 D 系列阈值 (time 作为放大器)**
  - time 现 4 档输出, 真值表 28 条不改, 但 D 系列 (time 升档) 仍用 time=strong 触发?
  - 依赖: 真值表层校验 docs/03
  - 推荐: ADR-0011 实施 + golden 重生后人工 review D1/D2/D3/D4 触发样本

- [ ] **22g · 凌晨归属 + overnight chain 双重逻辑冗余 (问题⑤)**
  - 场景: §2.3 "0-6 归前日" + §4.6 "12h 跨夜 chain" 两套机制处理"睡眠跨日"
  - Case 8 ([03:00, 09:00]) band 终值正确 (strong) 但 K_days 字段语义错乱
  - v0.2 暂留两套 + 标记落痕; 真实数据 dawn-cross 占比 < 2% 转方案 a 简化 (删归属)
  - 回滚: dawn-cross case 占比 > 10% 且 K_days 字段被下游误用 → 转方案 a

- [ ] **22h · 时区 / 夏令时未规整 (问题⑥)**
  - v0.2 spec 假设 `L1Output.captured_at` 已为拍摄地 local time (上游 L1 / EXIF 责任)
  - 跨时区旅行 K_days 可能 ±1, 接受为已知边界
  - 完成条件: v0.2 EXIF 真接入时验证 captured_at 字段是否带 tz; 带 tz 则规整
  - 风险: 国内用户跨时区 < 5% case, v0.1 demo 暂缓

- [ ] **22i · `max_inter_cluster_gap_h` / `max_intra_cluster_span_h` 字段拆分 (问题⑦)**
  - v0.1 spec 单字段 `max_inter_event_gap_h` 二义, v0.2 拆为两个
  - 已修, 不影响算法, 仅命名修复
  - 实施提醒: 代码层严格按拆字段实施, 避免回落二义

- [ ] **22j · T2.3 单日 events ≥ 3 一律 weak 误伤跨日游 (问题⑧)**
  - 场景: day1 早午晚 + day2 早 → T2.3 weak, 但实际可能是充实周末游
  - v0.2 暂留方案 a (跨日充实由主载体承担)
  - 回滚: 真实数据 "day1≥3 events + day2 少量" 漏判率 > 25% → 方案 b (day1+day2 都 ≥ 3 才 weak)

### 完成条件 (DoD)

- [ ] v0.2 真实数据 100+ 案例人工标注 (跟 OQ-021 共享数据集)
- [ ] 22a-j 各自统计指标出报告
- [ ] 决策: 沿用 ADR-0011 / 启用某个补丁 / 写新 ADR

### 关联

**文档**:
- [ADR-0011](../decisions/0011-time-natural-day-event-clustering.md) (本 OQ 来源 + 回滚条件)
- [docs/17_path_b_time.md](./17_path_b_time.md) (算法主规范)
- `Time_Aggregation_Spec.md` v0.2 §十一 (10 个 OQ-22a~j 原始定义, 实施完成后归档 archive/specs/)

**代码**:
- `src/features/time.py` (ADR-0011 实现)
- `config/path_b_time.yaml` (阈值)
- `src/contracts/features.py::TimeFeature` (新增字段)

**关联 OQ**:
- [OQ-003](#oq-003-time_is_fallback-的全局降权是否进入-time_score-本身) (本 ADR supersede × 0.5 全局降权)
- [OQ-021](#oq-021-adr-0010-接受边界的真实数据验证) (共享 v0.2 真实数据时间窗)

### 状态变更

- 2026-05-18: ADR-0011 落地引入, 接受 10 个边界假设 (a-j) 转入本 OQ 跟踪

---

## OQ-023: ADR-0012 接受边界的真实数据验证

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-18
**发现场景**: [ADR-0012](../decisions/0012-path-b-event-aggregation.md) 落地, Path_B_Event_Aggregation_Spec.md v0.2 §十 列出 6 个接受/不修边界 (a-f)

**问题**: ADR-0012 路径 B event 算法对 6 个边界 / 临时阈值做了"接受/暂不修" 选择, 均为产品/算法判断, 未经真实数据验证.

### 子问题清单

- [ ] **23a · band_thresholds 经验值**
  - 阈值: strong=1.0 (不可调) / medium_dominant=0.8 / medium_mixed=0.6 / weak_scattered=0.4
  - v0.2 真实数据 grid search 仅 medium/weak 阈值, strong 不动
  - 推荐 P0.5 真数据后调

- [ ] **23b · activity 二次门槛 ratio = 2/3 是否合理**
  - 当前 0.667 (Ace 2026-05-18 选定)
  - 候选: 0.6 / 2/3 / 0.75 / 0.8
  - 风险: 2/3 太松 → Case 13 [outing × 5 + walk × 4 + sightseeing × 1] 升 strong 是否合理?

- [ ] **23c · activity 兜底 max_valid_event_for_fallback**
  - 当前 N_valid ≤ 1 才启用 E.7
  - 候选: ≤ 0 (严格) / ≤ 1 / ≤ 2 (宽松)
  - 推荐 ≤ 1

- [ ] **23d · activity fallback band 上限 weak**
  - 当前永不超过 weak
  - 候选: 让 activity 100% 一致兜底也能 medium
  - 推荐保留 weak 上限

- [ ] **23e · sports 子类 (篮球/足球) 接受边界 v0.2 验证**
  - v0.2 选定方案 a (接受 sports 大类成集)
  - 风险: 真实用户上传 5 张运动照片混 (篮球/足球/网球) 单独成"运动相册" 是否符合体感?
  - v0.2 真实数据: "希望成集"占比 > 70% → 通过, > 30% "希望细分" → 触发 ADR-0012-补丁
  - 修复方向: 改 A3 / 扩 activity 枚举 / event 维度内吸收 main_subjects

- [ ] **23f · 真值表 B/D/E 系列与新 medium 大量出现的兼容性**
  - 老算法严格全员一致 0.9 strong, 否则 0.2 none
  - 新算法 4:1 / 3:2 / 80%-100% 都变 medium → B 系列 (multi-medium 组合) 命中率上升
  - 影响: mini album 数会涨, 需 golden review + 人工评估"小集质量 vs 数量"
  - 已确认 batch_3_random fixture 修改 (p002 event_hint 从 daily_record → work) 让 3 张 event 真不重合, 否则 D3 命中导致 light album

### 完成条件 (DoD)

- [ ] v0.2 真实数据 100+ 案例人工标注 (共享 OQ-021/022 数据集)
- [ ] 23a-f 各自统计指标出报告
- [ ] 决策: 沿用 ADR-0012 / 启用某个补丁 / 写新 ADR

### 关联

**文档**:
- [ADR-0012](../decisions/0012-path-b-event-aggregation.md) (本 OQ 来源 + 回滚条件)
- [docs/18_path_b_event.md](./18_path_b_event.md) (算法主规范)
- `Path_B_Event_Aggregation_Spec.md` v0.2 §十 (6 个 OQ-23a~f 原始定义, 实施完成后归档)

**代码**:
- `src/features/event.py` (ADR-0012 实现)
- `config/path_b_event.yaml` (阈值)
- `src/contracts/features.py::EventFeature` (新增字段)

**关联 OQ**:
- OQ-009 §9b (本 ADR 关闭)
- [OQ-021](#oq-021-adr-0010-接受边界的真实数据验证) (共享 v0.2 真实数据时间窗)
- [OQ-022](#oq-022-adr-0011-接受边界的真实数据验证) (共享 v0.2 真实数据时间窗)

### 状态变更

- 2026-05-18: ADR-0012 落地引入, 接受 6 个边界假设 (a-f) 转入本 OQ 跟踪

---

## OQ-024: ADR-0013 接受边界的真实数据验证

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-18
**发现场景**: [ADR-0013](../decisions/0013-path-b-theme-two-tier-cluster.md) 落地, Path_B_Theme_Aggregation_Spec.md v0.3 §十

### 子问题清单

- [ ] **24a · 双阈值真实数据校准** (主 0.5 + 次 2/3 / 1/3)
- [ ] **24b · min_hit_count = 2 vs 3** (推荐 2, 小相册友好)
- [ ] **24c · 次字段独立 cluster_threshold** (当前复用 0.75)
- [ ] **24d · MockEmbedder 局限暴露** (v0.2 OQ-018 真 Qwen 接入后解)
- [ ] **24e · 升降档幅度** (当前 1 档)

### 关联

- [ADR-0013](../decisions/0013-path-b-theme-two-tier-cluster.md)
- [docs/19_path_b_theme.md](./19_path_b_theme.md)
- `archive/specs/Path_B_Theme_Aggregation_Spec.md` v0.3

---

## OQ-025: ADR-0014 接受边界的真实数据验证

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-18
**发现场景**: [ADR-0014](../decisions/0014-path-b-anchor-two-tier-cluster.md) 落地, Path_B_Anchor_Aggregation_Spec.md v0.3 §十

### 子问题清单

- [ ] **25a · OQ-008 §8e 修订 (合并 → 分层)** v0.3 已决, 留追溯
- [ ] **25b · 阈值复用 theme 还是独立调** (anchor 中文短语可能需更松 0.65)
- [ ] **25c · object_anchors cluster_threshold** 同 OQ-024c
- [ ] **25d · MockEmbedder 中文 anchor 同义识别** 表覆盖小
- [ ] **25e · anchor 是辅证不是主载体** A 系列无 anchor=强单独成集, 但保留 strong 档

### 关联

- [ADR-0014](../decisions/0014-path-b-anchor-two-tier-cluster.md)
- [docs/20_path_b_anchor.md](./20_path_b_anchor.md)
- `archive/specs/Path_B_Anchor_Aggregation_Spec.md` v0.3

---

## OQ-026: ADR-0015 接受边界的真实数据验证

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-18
**发现场景**: [ADR-0015](../decisions/0015-path-b-emotional-single-tier-cluster.md) 落地, Path_B_Emotional_Aggregation_Spec.md v0.2 §十

### 子问题清单

- [ ] **26a · L1 prompt 改一行的真接入风险** (v0.2 LLM 接入后验证遵守"画面氛围 vs 推断情绪")
- [ ] **26b · 推断情绪黑名单 (中/英) 完整性** (扩 exhausted/frustrated/亢奋/失落 等)
- [ ] **26c · neutral cap 严格度** (当前 EM.0 preempt 直接 cap; 候选: 仅 coverage ≥ 0.6 才 cap)
- [ ] **26d · MockEmbedder 表外** (跟 OQ-024d 共享, v0.2 真 Qwen 接入后解)
- [ ] **26e · 邻近度 group 是否引入** (calm/quiet/relaxed 表外 mock 不识同义, v0.2 真模型识别)

### 关联

- [ADR-0015](../decisions/0015-path-b-emotional-single-tier-cluster.md)
- [docs/21_path_b_emotional.md](./21_path_b_emotional.md)
- `archive/specs/Path_B_Emotional_Aggregation_Spec.md` v0.2

---

## OQ-027: ADR-0016 接受边界的真实数据验证

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-18
**发现场景**: [ADR-0016](../decisions/0016-location-geocoder-4tier.md) 落地

### 子问题清单

- [ ] **27a · GPS 量化粒度** (4 位小数 ~ 10m vs 3 位 100m vs 5 位 1m), 真数据观察缓存命中率调
- [ ] **27b · 海外 fallback 接 Google Maps 时机** (Seenful 海外用户 > 5% 时启动 v0.3 国际化)
- [ ] **27c · API 失败重试策略** (当前不重试, 失败 GPS 缓存 None 防重复打 quota)
- [ ] **27d · 缓存持久化** (v0.1 进程内 dict / v0.2 Redis + TTL 切换时机)
- [ ] **27e · 用户搬家检测** (OQ-010 §10c, 30 天 GPS 频次聚类 + 滚动窗口自动检测, v0.2 落地)

### 关联

- [ADR-0016](../decisions/0016-location-geocoder-4tier.md)
- [docs/22_location_geocoder.md](./22_location_geocoder.md)
- `archive/specs/Location_Geocoder_4Tier_Spec.md` v0.1

---

## OQ-028: Pipeline Cascade Backfill 边界

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-19
**发现场景**: [ADR-0017](../decisions/0017-pipeline-cascade-backfill.md) 落地, Pipeline_Cascade_Backfill_Spec.md v0.3 §九

### 子问题清单

- [ ] **28a · ~~cascade 中已处理但未成集 photos 怎么处理~~** (v0.2 加, v0.3 作废 — 拆 N 张每张独立 cascade, 沉淀池自然承接, 顺序无所谓)

- [ ] **28b · cascade 真值表 path 选择**: 现状复用 path B 主表 28 条 (A1-F1), 真实数据后调
  - cascade 的"P + 召回 sediment"语义跟 path B 的"整批一致"不完全等价
  - 候选: 定制 cascade 真值表 (跨日 time 放宽, theme 跨日宽容)
  - v0.1 demo 复用 path B 28 条

- [ ] **28c · sediment 池 50 张是否够**: 当前 demo v0.1 截最近 50 张, PRD §3.10.10 暗示 200 张才换激进粗筛
  - 50+ 用户日均 3-5 张沉淀, 30 天 100-150 张, 截 50 可能漏关联
  - v0.2 真实数据后调到 100 张或按需

- [ ] **28d · ~~顺序敏感性产品影响~~** (v0.2 加, v0.3 作废 — 沉淀池自然承接 + Case G 验证)

- [ ] **28e · cascade 多产物频控**: 一次上传可能产出多个相册 (Case F: 3 个), PRD §3.10.7 单用户单天最多 1 次成集通知
  - cascade 多产物如何合并通知?
  - 推荐: 1 次通知合并多个相册 ("我把今天的 5 张分成了 2 个相册"), v0.2 详

- [ ] **28f · event 降权权重 0.5 是否合适** (ADR-0017 核心新增):
  - 当前 event=0.5, gps/theme=1.0
  - event_hint 10 枚举 (daily_record/outing/meal 占绝大多数), 命中"event 一致"概率高但语义弱
  - 0.5 让 event 单独命中候选永远排在任一 GPS/theme 命中之后
  - 真实数据后调到 0.3 (更激进降权) 或 0.7 (更宽松) 待观察
  - DoD: 真实数据 + 人工标注, grid search 0.3 / 0.5 / 0.7

### 完成条件 (DoD)

- [ ] v0.2 上线后 50+ 用户真实数据观察
- [ ] cascade 触发率 / 成集率 / 删除率验证 (PRD §3.10.8 指标)
- [ ] event 权重 grid search
- [ ] 写 ADR-NNNN 记录最终参数

### 关联

**文档**:
- [ADR-0017](../decisions/0017-pipeline-cascade-backfill.md)
- [docs/23_pipeline_cascade_backfill.md](./23_pipeline_cascade_backfill.md)
- [docs/05_truth_table_backfill.md](./05_truth_table_backfill.md) (含 ADR-0017 升级段)
- `config/truth_table_backfill.yaml::priority_weight`

**代码**:
- `src/policy/cascade_backfill.py::cascade_backfill_single`
- `src/candidate_builder/backfill_scan.py::rank_and_pick_top_n`
- `src/policy/backfill_engine.py::apply_backfill_caps` (不动, PRD §3.10.5 strong-only)

### 状态变更

- 2026-05-19: ADR-0017 落地引入

---

## OQ-029: Plan A/B 真实数据对比

**状态**: 待 v0.2 真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-19
**发现场景**: [ADR-0018](../decisions/0018-feature-assembler-plan-ab-switch.md) 落地, demo 阶段无法只凭 fixture 判断 ADR-0010~0015 升级的实际产品价值

**问题**: ADR-0018 加了 plan A/B 双版本开关 (L2 2.0 = ADR-0010~0015 / L2 1.0 = v1.3 §3.2 抄本), 真实数据上线前没法判断 ADR 升级带来的具体收益.

### 子问题清单

- [ ] **29a · commitment_rate 对比** (PRD §6.3 关键指标): plan A vs plan B 在 100+ 真实 case 上的成集率差异
  - 假设: plan A 成集率 ≈ plan B + 5-10% (双层语义聚类 + EM.0 cap + K_outer 散沙识别全方位提升)
  - 风险: 如果差异 < 3%, 部分 ADR 收益可质疑

- [ ] **29b · suppress_rate 对比**: 弱关联场景 plan A 是否更严格 (TH.5 none / F1)
  - 假设: plan A suppress_rate ≈ plan B + 2-5%
  - 关键 case: 5 张 [neutral×5] (L2 2.0 EM.0 cap weak vs L2 1.0 字面 0.8 strong)

- [ ] **29c · 误聚合率对比**: 用户从相册移除的比例 (delete_rate)
  - 假设: plan A 误聚合率 < plan B
  - 关键 case: 同义词主题 (湖边 / lakeside / 水边) plan A 通过 ADR-0008 同簇识别成集, plan B 字面 Jaccard 失败

- [ ] **29d · 边界场景一致性**: 同一 case 两 plan 是否给出截然不同结论?
  - Case A: 4 张西湖 + 1 张商场 (K_outer 散沙) — plan A SCATTERED, plan B max_distance 远, 输出一致
  - Case B: 5 张 [neutral] — plan A weak (EM.0), plan B strong (bug)
  - Case C: 同义词主题 - plan A 强, plan B 字面无重叠

- [ ] **29e · plan B 是否可作生产 fallback**: 真实数据下 plan A 出 bug 时是否能切 plan B 兜底?
  - 假设: plan B 算法简单, 不容易出 bug, 可作降级方案
  - 但 plan B 自带 emotional neutral bug, 真生产用需修, 或允许 plan B fallback 时单独 cap

### 完成条件 (DoD)

- [ ] v0.2 真实数据 100+ case 同时跑 plan A 和 plan B
- [ ] 29a-c 指标计算 + 对比报告
- [ ] 决策: 维持 plan A 默认 / 切 plan B / 写新 ADR 优化 plan A

### 关联

**文档**:
- [ADR-0018](../decisions/0018-feature-assembler-plan-ab-switch.md)
- [docs/24_feature_assembler_plan_ab.md](./24_feature_assembler_plan_ab.md)
- `config/feature_assembler.yaml`

**代码**:
- `src/features/plan_b/{location,time,theme,event,anchor,emotional}.py`
- `src/features/assemble.py::assemble_features` (plan 分发)
- `src/policy/bands.py::compute_bands` (阈值源切换)

**外部规范** (plan B 来源):
- `L2 Association Engine 工程实现规范 v1.3.md` §3.2 §5.3

### 状态变更

- 2026-05-19: ADR-0018 落地引入

---

## OQ-030: Persona 真实数据扩展 + 测试集 v1.0 → v2.0

**状态**: 待真实数据上线后
**优先级**: P0.5
**发现时间**: 2026-05-20
**发现场景**: [ADR-0019 v0.4](../decisions/0019-persona-based-e2e-testing.md) 落地, persona 资产池设计完毕

**问题**: ADR-0019 v0.4 设计了 3 persona (张奶奶/李叔叔/小王) × 212 张 mock 照片 × 35 scenarios. 真实用户上线后需要扩 persona 数量 + 真实标注 + review 现 scenarios 是否符合产品意图.

### 子问题清单

- [ ] **30a · 扩 persona**: 加更多用户类型 (eg. 学生 / 妈妈 / 摄影师 / 海外用户)
- [ ] **30b · 真实数据标注**: 50+ 真实用户 30 天照片库, 人工标注期望聚集结果, 跟 persona scenarios 对比
- [ ] **30c · v0.4 35 scenarios review**: 哪些是"算法接受现状", 哪些是"应改算法"? 由 Ace 人工 review (现 HTML 看板支持)
- [ ] **30d · L2.5 + cascade 覆盖扩展**: v0.4 持 L2 偏重 (34/35), L2.5 + cascade 单张测试不足. **v0.5 已补 29 个 (14 L2.5 + 15 cascade)**, 但真实数据后还需扩
- [ ] **30e · 红线测试 vs 鲁棒性测试分类**: v0.5 加 test_type 字段, 真实数据后调整红线集

### 关联

- [ADR-0019 v0.4/0.5](../decisions/0019-persona-based-e2e-testing.md)
- [docs/25](./25_persona_e2e_testing.md)
- `tests/_DASHBOARD.html` (人工审核工具)

### 状态变更

- 2026-05-20: ADR-0019 v0.4 落地引入
- 2026-05-20: v0.5 补 L2.5 + cascade scenarios 共 29 个, 加 test_type 二分类

---

## OQ-031: 真 LLM 真实行为基线 + 跟 mock 偏差对比

**状态**: 待 ADR-0020 接真 API 后跑
**优先级**: P0.5
**发现时间**: 2026-05-20
**发现场景**: [ADR-0020](../decisions/0020-real-api-integration.md) 落地, Qwen DashScope + 本地 Embedding + Amap 接入完毕

**问题**: 现 mock 桩永远取 bounds_min, 真 Qwen LLM 会在 bounds 区间内基于语义判断, 输出会偏离 mock 基线. 需要锁定**真 LLM 真实行为基线** + 持续 review.

### 子问题清单

- [ ] **31a · 真 LLM 跑 35 scenarios** (SEENFUL_LLM_MODE=real + DASHSCOPE_API_KEY): 输出锁基线 → 重生 `_VISUAL_REPORT.md` real mode
- [ ] **31b · 真 LLM vs mock diff**: 35 个 case 哪些 final_strength / decision_tier 变化? 哪些不变?
- [ ] **31c · 真 Qwen Embedding 跑**: 现 mock 同义簇靠人工 dict, 真 Qwen3-Embedding-0.6B 跑后 theme 语义簇识别哪些 case 变化?
- [ ] **31d · Amap 真接入跑 12 个 GPS**: ADR-0016 已实测, 跟 mock geocoder 对比
- [ ] **31e · 成本 review**: 真 LLM 跑全套估 < $1, 调试期 < $5; 真实 SLO 后再调 model size (turbo → plus 边界)
- [ ] **31f · evidence 质量 review**: 真 LLM 的 semantic_reason / evidence 是否符合 PRD §3.3.3 关联类型识别要求

### 关联

- [ADR-0020](../decisions/0020-real-api-integration.md)
- [docs/26](./26_real_api_integration.md)
- `tests/personas/_gen_visual_report.py` (跑 real mode 重生报告)

### 状态变更

- 2026-05-20: ADR-0020 落地引入

---

## OQ-032: ADR-0023 subject stoplist 词集完备性

**触发**: [ADR-0023](../decisions/0023-theme-subject-max-or.md) 引入 `subject_stopword_blocklist` 防泛词假阳 (`person/food/car/...` 12 个词). 但实测 FP_B1 暴露 `stuff/thing/item` 也是泛词, stoplist 没收.

**问题**: 真实 LLM 输出 main_subjects 的"泛词" 多样, 静态 stoplist 难枚举完. 需要:
- v0.2 上线后看 main_subjects top-100 词频分布, 决定加哪些
- 是否引入 IDF 替代 stoplist? 词频高于整体 P95 视作泛词

### 子问题

- [ ] **32a · top-100 词频统计**: 上线后跑 1000 张, 统计 main_subjects 频次, P95 之上视作泛词候选
- [ ] **32b · stoplist 加词**: 至少加 `stuff/thing/item/object/scene/view/place` 7 个
- [ ] **32c · IDF 替代**: 是否换成动态 IDF 算法? 静态 list 维护成本 vs 动态准确度

### 关联

- ADR-0023 §三 stoplist + §七 OQ-032 引入
- docs/28 B1 假阳 case

### 状态变更

- 2026-05-20: ADR-0023 落地引入

---

## OQ-033: ADR-0023 theme+subject 一致性 boost

**触发**: ADR-0023 MAX-OR 取最高, 但 theme=medium + subject=medium (都中等) 时, 是否应额外 boost (共识证据)? 现行不动.

### 子问题

- [ ] **33a · 真实数据看共识情况**: theme + subject 同 medium 的 case 占比? 这些 case 实际是 strong 还是 medium?
- [ ] **33b · 是否引入 +0.1 confidence boost**: 共识时 final_strength score +0.1? 影响 LLM 复核?

### 关联

- ADR-0023 §七 OQ-033 引入

### 状态变更

- 2026-05-20: ADR-0023 落地引入

---

## OQ-034: ADR-0024 Top-K K 值经验值

**触发**: [ADR-0024](../decisions/0024-theme-topk-coverage.md) 选 K=3 (经验值). 但 K 应跟 N 相关:
- N=3 时 Top-3 直接全选, K=3 没意义
- N=20 时 Top-3 可能漏 (5+ 个小主题)

### 子问题

- [ ] **34a · K 动态化**: K = max(3, N/3)? 或取累加 cov ≥ 0.5 的最少簇数
- [ ] **34b · 真实数据 N 分布**: 上线后看 batch N 分布 (90% < 10? 99% < 20?), 决定 K 是否够
- [ ] **34c · K 跟 coverage 阈值的耦合**: K 大了 coverage 容易高, 阈值是否要同步抬?

### 关联

- ADR-0024 §五 OQ-034 引入

### 状态变更

- 2026-05-21: ADR-0024 落地引入

---

## OQ-035: ADR-0024 grid 阈值 0.7 经验值

**触发**: ADR-0024 改 medium_high 阈值 0.8→0.7, 让 T1 西湖 cov=0.75 走 TH.2 medium-high 而非 TH.3 medium-low. 但 [0.7, 0.8) 区间其他 case 是否合理?

### 子问题

- [ ] **35a · cov ∈ [0.7, 0.8) 占比**: 真实数据下这区间有多少 case? 升档影响整体 medium 数量
- [ ] **35b · 阈值 0.7 vs 0.65/0.75**: grid search 看 strong/medium/weak 分布是否合理
- [ ] **35c · cov 算法变了, 老阈值是否仍合理**: ADR-0024 改 coverage 算法 (Top-K vs hit_rate), 阈值跟新算法可能不匹配

### 关联

- ADR-0024 §五 OQ-035 引入

### 状态变更

- 2026-05-21: ADR-0024 落地引入

---

## OQ-036: ADR-0025 抽象化 mapping 合理性

**触发**: [ADR-0025](../decisions/0025-theme-tags-no-geographic.md) 清洗 ~40 处地名 → 抽象化 (xihu → lake, gugong → palace, etc).

**问题**: 抽象化 mapping 是经验值. 真实数据上线后:
- 用户拍的"湖" 多种类 (西湖/千岛湖/玄武湖) 都用 `lake` 是否聚类太粗?
- "palace" 涵盖故宫/凡尔赛/迪士尼城堡是否合理?

### 子问题

- [ ] **36a · 真实数据 top-100 主题词分布**: 看用户实际拍照后 LLM 输出的非地名主题词分布
- [ ] **36b · mapping 细化**: 是否需要 lake 拆 lake/freshwater_lake/scenic_lake / palace 拆 palace/imperial_palace?
- [ ] **36c · 跨地拍同主题用户场景**: 用户拍了西湖 + 千岛湖, 都聚成 lake 是否符合"按主题成集" 直觉

### 关联

- ADR-0025 §四 OQ-036 引入

### 状态变更

- 2026-05-21: ADR-0025 落地引入

---

## OQ-037: 真 LLM 在禁地名 prompt 下是否仍 hallucinate

**触发**: ADR-0025 §2.2 加 L1 vision prompt 禁地名指令. 但真 Qwen-VL 可能仍编 "西湖" 等热门地名.

### 子问题

- [ ] **37a · v0.2 真 vision 接入后**: 跑 100 张测试图片, 看 theme_tags 含地名比例
- [ ] **37b · prompt 强度调试**: 禁令措辞 (eg. "绝不" vs "尽量不") 对编造率影响
- [ ] **37c · 后置过滤兜底**: stoplist 自动 cap 还是 strip 词后留 cluster

### 关联

- ADR-0025 §五 OQ-037 引入
- 跟 OQ-031 真 LLM 真实行为基线相关 (跨 OQ)

### 状态变更

- 2026-05-21: ADR-0025 落地引入
