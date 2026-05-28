# docs · 规范索引

> 这是 Seenful L2 Engine 的宪法层。代码必须服从,任何修改先改这里。
> 当前实现范围:**路径 A (动态生长) + 路径 B (L2 主) + 路径 C (兜底回扫) + 三路仲裁器**, 算法层用 v0.1 简单实现(待 v1.3.2 算法替换,见 ADR-0004)。
>
> ⚠ 流程模型: **上传张数分流** (单张走 A / 多张走 B,A 始终可叠加) + **C 真兜底** (仅在 A 和 B 都未产出相册时触发)。不是"三路并列竞争"。详见 `01_architecture.md` 和 `09_arbitration.md`。

## 文档清单 (全部已就位)

| 文档 | 内容 | 状态 |
|---|---|---|
| [01_architecture.md](./01_architecture.md) | 四层架构 + 三路 + 仲裁数据流 + orchestrator 入口 | ✅ |
| [02_data_contracts.md](./02_data_contracts.md) | 所有 Pydantic 契约 (L1/Features/Bands/Decision/Growth/Backfill/Arbitration/PlaceAnchor) + L1 文学化字段语义边界 | ✅ |
| [03_truth_table_main.md](./03_truth_table_main.md) | 主真值表 28 条 (路径 B, A1-4 + B1-9 + G1-4 + C1-4 + D1-4 + E1-2 + F1) | ✅ |
| [04_truth_table_growth.md](./04_truth_table_growth.md) | 动态生长真值表 10 条 (路径 A, G-A1-2 + G-B1-3 + G-C1-2 + G-D1 + G-E1 + G-F1) | ✅ |
| [05_truth_table_backfill.md](./05_truth_table_backfill.md) | 兜底回扫规则 (路径 C, 复用主表 + 三条 cap) | ✅ |
| [06_hard_rules.md](./06_hard_rules.md) | 全路径硬规则 + HRG-POST (A) + BACKFILL-CAP (C) + 仲裁策略 3 禁用 | ✅ |
| [07_dimension_thresholds.md](./07_dimension_thresholds.md) | 维度阈值 + 信号计算 (v1.3.2 目标方案,代码层尚是 v0.1 简化版) | ✅ |
| [09_arbitration.md](./09_arbitration.md) | 三路仲裁器 4 个 Case + 喜宝话术 | ✅ |
| [10_mini_album_schema.md](./10_mini_album_schema.md) | Mini Album 指纹合成 + place_anchor DBCH 算法 (ADR-0005) | ✅ |
| [11_observability.md](./11_observability.md) | 4 个决策日志格式 (DecisionLog / Growth / Backfill / Arbitration) | ✅ |
| [12_open_questions.md](./12_open_questions.md) | OQ-001 ~ OQ-020 | ✅ |
| [13_low_quality_place_detection.md](./13_low_quality_place_detection.md) | 高频低质量地点判定 Plan A/B (ADR-0006) | ✅ |
| [14_theme_aggregation.md](./14_theme_aggregation.md) | 路径 A theme 语义簇聚合 + 匹配 (ADR-0008) | ✅ |
| [15_event_aggregation.md](./15_event_aggregation.md) | 路径 A event 三级分层聚合 + 匹配 + L1 枚举扩展 (ADR-0009) | ✅ |
| [16_path_b_location.md](./16_path_b_location.md) | 路径 B location 分级 DBSCAN + PCA OBB + 形状校正 + transit 降档 (ADR-0010) | ✅ |
| [17_path_b_time.md](./17_path_b_time.md) | 路径 B time 自然日归属 + 时间链式切分 + T1/T2/T3 grid + 边界保护带 (ADR-0011) | ✅ |
| [18_path_b_event.md](./18_path_b_event.md) | 路径 B event primary_share + activity 二次门槛 + E.1~E.8 grid (ADR-0012) | ✅ |
| [19_path_b_theme.md](./19_path_b_theme.md) | 路径 B theme 双层字段判定 (主 theme_tags + 次 main_subjects) + 升降档 (ADR-0013) | ✅ |
| [20_path_b_anchor.md](./20_path_b_anchor.md) | 路径 B anchor 双层字段判定 (主 meaning + 次 object) + 升降档 (ADR-0014) | ✅ |
| [21_path_b_emotional.md](./21_path_b_emotional.md) | 路径 B emotional 开放字段 + 单层语义聚类 + neutral baseline (ADR-0015) | ✅ |
| [22_location_geocoder.md](./22_location_geocoder.md) | Location · 高德 Geocoder + 4 档 (市内/省内/国内/国外) (ADR-0016) | ✅ |
| [23_pipeline_cascade_backfill.md](./23_pipeline_cascade_backfill.md) | Pipeline 三路分流 (单/双/多张) + 多张 B 失败拆 N 张 cascade + 维度强度排序选 4 张 (ADR-0017) | ✅ |
| [24_feature_assembler_plan_ab.md](./24_feature_assembler_plan_ab.md) | Path B 7 维度双版本开关 (L2 2.0 默认 / L2 1.0 v1.3 抄本对比 demo, ADR-0018) | ✅ |
| [25_persona_e2e_testing.md](./25_persona_e2e_testing.md) | Persona-based E2E 测试框架 (2 persona × 40 天 + 60 scenarios + 8 条 invariants, ADR-0019) | ✅ |
| [26_real_api_integration.md](./26_real_api_integration.md) | v0.2 真接入 Qwen LLM + Embedding + Amap + Persona 记忆 mock (ADR-0020) | ✅ |
| [27_persona_mock_realism.md](./27_persona_mock_realism.md) | Persona Mock 数据真实多样性规范 (GPS 跨度参考 + event 混标 + theme 颗粒, ADR-0021) | ✅ |
| [99_glossary.md](./99_glossary.md) | 术语对照 + 仲裁术语 (case/ending) | ✅ |

## P0 未决问题 (Ace 处理中)

- **[OQ-008](./12_open_questions.md#oq-008-小集指纹合成-mini-album-fingerprint-synthesis)** · 小集指纹合成 — **部分解决** (§8a/8f/8g ADR-0005/0006, §8b/8c ADR-0008, §8d ADR-0009, **§8e ADR-0014 修订: 合并 → 分层**); §8h/8i 仍待决
- **[OQ-009](./12_open_questions.md#oq-009-多维度匹配分档-multi-cross-算法严格度)** · 多维度匹配分档 — **§9a (theme) ADR-0013 关闭** / **§9b (event) ADR-0012 关闭** / **§9d (anchor) ADR-0014 关闭** / §9g (location 阈值) ADR-0010 部分关闭; §9c (people) / §9e (path A 1 vs 聚合) / §9f (路径阈值统一) 仍待决
- **[OQ-005/010/017]** · home_city 缺失默认 + user_home_city 推断 + ADR-0007 回切 — **ADR-0016 全部关闭** (高德 reverse geocoding + 4 档判定)
- **[OQ-018](./12_open_questions.md#oq-018-qwen-真实-embedding-接入与基准测试)** · Qwen3-Embedding-0.6B 接入 — path A theme + **path B theme/anchor (ADR-0013/0014) 也依赖** (v0.2 上线前置, 当前 mock embedder)

## 后续待补 (v0.2 或更晚)

- `08_llm_prompts.md` — LLM Judge prompt 完整版 (v0.1 用 mock, anthropic 接入后写)
- ADR-0004 实现 — `src/features/{location,time,theme}.py` 重写,目前是 v0.1 简化版 (注: 路径 A 的 location 已用 ADR-0005 DBCH 替代)

## 决策记录

- `decisions/0004-feature-assembler-revision.md` — location/time/theme 算法 v1.3.1→v1.3.2 替换 (距离档位部分被 ADR-0007 v0.1 测试期 supersede)
- `decisions/0005-place-anchor-dbch.md` — place_anchor 算法 DBCH (DBSCAN + Bounded Convex Hull), 2026-05-13 落地 (距离档位 + buffer base 部分被 ADR-0007 v0.1 测试期 supersede)
- `decisions/0006-high-freq-low-quality-place.md` — 高频低质量地点判定 Plan A (双 density), 2026-05-13 落地 (修订 ADR-0005 的 is_high_freq 字段语义)
- `decisions/0007-unified-location-bands.md` — Location 距离档位 v0.1 测试期塌缩为单一表 (500/1000/2000m), 2026-05-14 落地, 临时性, OQ-017 触发回切
- `decisions/0008-theme-semantic-clustering.md` — 路径 A theme 维度: 字面 Jaccard → 语义簇聚合 + 频次加权匹配, 2026-05-14 落地, 关闭 OQ-008 §8b/§8c
- `decisions/0009-event-aggregation.md` — L1 event_hint 枚举 6→10 + 路径 A event 三级分层聚合 + 四档匹配, 2026-05-14 落地, 关闭 OQ-008 §8d
- `decisions/0010-path-b-location-dbch-pca-shape.md` — 路径 B location 分级 DBSCAN + PCA OBB + 形状校正 + transit 降档, 直出 4 档 band, 2026-05-15 落地, 部分关闭 OQ-009 §9g (路径 B location 独立阈值), supersede ADR-0004 §3.2.1, 新增 OQ-021
- `decisions/0011-time-natural-day-event-clustering.md` — 路径 B time 自然日归属 + 时间链式切分 + T1/T2/T3 grid + 边界保护带, 直出 4 档 band, 2026-05-18 落地, supersede ADR-0004 §3.2.2 + OQ-003
- `decisions/0012-path-b-event-aggregation.md` — 路径 B event primary_share + activity 二次门槛 + E.1~E.8 grid, 直出 4 档 band, 2026-05-18 落地, 关闭 OQ-009 §9b, supersede 老 compute_event_score
- `decisions/0013-path-b-theme-two-tier-cluster.md` — 路径 B theme 双层字段判定 (主 theme_tags + 次 main_subjects) + cluster hit_rate + coverage + 升降档, 直出 4 档 band, 2026-05-18 落地, 关闭 OQ-009 §9a, 复用 ADR-0008 MockEmbedder + cluster_tags
- `decisions/0014-path-b-anchor-two-tier-cluster.md` — 路径 B anchor 双层字段判定 (主 meaning + 次 object) + 同 theme 算法骨架, 直出 4 档 band, 2026-05-18 落地, 关闭 OQ-009 §9d + 修订 OQ-008 §8e (合并 → 分层)
- `decisions/0015-path-b-emotional-single-tier-cluster.md` — 路径 B emotional 开放字段 + 单层语义聚类 + neutral baseline (EM.0 preempt) + 红线落痕, 直出 4 档 band, 2026-05-18 落地, L1 prompt 改 (7 白名单 → 开放画面氛围词), 复用 ADR-0013 _two_tier_cluster (enable_secondary=False), 引发 OQ-026
- `decisions/0016-location-geocoder-4tier.md` — Location · 高德 Reverse Geocoding API 接入 (MockGeocoder + AmapGeocoder + provider 双轨) + 4 档升级 (市内/省内/国内/国外, strong=500/1000/1500/2000m), 2026-05-18 落地, **supersede ADR-0007**, 关闭 OQ-005 + OQ-010 §10a/§10b + OQ-017, 引发 OQ-027
- `decisions/0017-pipeline-cascade-backfill.md` — Pipeline 三路分流 (N=1 A→C / N=2 light_judge / N≥3 B→拆 N 张 A→C) + cascade_backfill_single + 维度强度总分排序选 top 4 (event 权重 0.5) + 多产物 ArbitrationResult (cascade_albums + growth_merges + settled_photo_ids), 2026-05-19 落地, **不动 apply_backfill_caps** (PRD §3.10.5 校准, v0.2 "删 Caps 调 run_l2_path_b" 路线作废), 引发 OQ-028
- `decisions/0018-feature-assembler-plan-ab-switch.md` — Path B Feature Assembler 双版本开关 (L2 2.0 = ADR-0010~0015 默认主 / L2 1.0 = v1.3 §3.2 抄本副 demo 对比), 2026-05-19 落地, 全局开关 `config/feature_assembler.yaml::plan`, scene_type 字段已删用 0 适配, emotional neutral bug 保留 (v1.3 原貌), 不动真值表 28 条 / HR / LLM / Path A / Path C, 引发 OQ-029
- `decisions/0019-persona-based-e2e-testing.md` — Persona-based E2E Testing Framework, **v0.5** (2026-05-20): 用户行为驱动 + 每张 unique 标签 + 3 persona (张/李/小王) × 40 天 / 19 行为模式 + 10 旅游分布 + 6 补漏 + 14 L2.5 + 15 cascade scenarios / 8 invariants / HTML 测试看板 (test_type=red_line/robustness 二分类) / Path 覆盖 L2:34 + L2.5:15 + cascade:15. 引发 OQ-030
- `decisions/0021-llm-label-realism.md` — LLM 标签真实多样性原则 (Persona Mock), 2026-05-20: GPS 跨度参考表 (0.001° ≈ 100m 不是"小漂移") + event_hint 混标分布 (公园散步 50% outing / 30% daily_record / 15% gathering 等) + theme 颗粒度多样性. 修复 A2 weekly_park_walk 8 张同 GPS / xihu_overnight 跨度过小 / pick_grandkid_routine event 全 daily_record 等. 配 docs/27
- `decisions/0022-th0-multi-parallel-clusters-medium.md` — TH.0 多并列主簇 → medium (修 ADR-0013 TH.1 漏洞), 2026-05-20: B5 (上海开会 3 + 苏州游 3) theme strong 误判, 因多并列簇覆盖 100% 也触发 TH.1. 加 TH.0 优先规则 + TH.1 加 cluster_count==1 约束. ThemeShape 加 MULTI_PARALLEL_CLUSTERS. 修订 ADR-0013
- `decisions/0023-theme-subject-max-or.md` — path B theme/subject MAX-OR + 泛词 stoplist, 2026-05-20: A6 牡丹 30 天 8 张 theme weak (词散) 但 subject strong (花/叶稳), 老 ADR-0013 主优先废了 subject 信号. 新加 Phase 4-6: subject single-layer + stoplist cap medium + MAX(theme,subject) 取最高, subject 赢加 `.subject` 后缀. 保留老 Phase 3. ThemeFeature 加 subject_band/dominant_field 字段. 修订 ADR-0013, 引发 OQ-032/033
- `decisions/0024-theme-topk-coverage.md` — path B theme Phase 1 改 Top-K coverage (替代 hit_rate 单簇阈值), 2026-05-21: C8 咖啡馆 8 张 3 主题 hit=3,2,2 老 cov=0 (hit_rate<0.5 全过滤) 新 cov=0.625. K=3 + min_hit_count=2 + grid 阈值 0.7/0.5. 仅改 theme, anchor/emotional 不动. 修订 ADR-0013 Phase 1, 引发 OQ-034/035
- `decisions/0025-theme-tags-no-geographic.md` — theme_tags 禁地名 + 地标 (维度边界澄清), 2026-05-21: 实测 persona 含 23 种地名 (xihu × 24, gugong/great_wall/bund/pearl_tower 等). 地理信息归 location 维度 (Geocoder ADR-0016), theme_tags 描述主题/氛围/活动. 加 LLM prompt 禁令 + persona 数据清洗 (~40 处抽象化) + config stoplist. 引发 OQ-036/037
- `decisions/0020-real-api-integration.md` — v0.2 真接入: Qwen LLM (DashScope qwen-turbo no-thinking, 主/生长/兜底 3 路) + Qwen Embedding 本地 (sentence-transformers + Qwen3-Embedding-0.6B 零成本) + AmapGeocoder 切真 + Persona 加 4 层记忆 mock (Event Log / Daily Digest 字段齐全, Active State / User Model 字段保留但空); 2026-05-20 落地, mock/real 双模式 (env var SEENFUL_LLM_MODE), 失败 graceful_degrade_to_mock; 新增可视化报告生成器 _gen_visual_report.py; 引发 OQ-031

## 已归档需求

一次性 spec / prompt 实施完毕后移到 `archive/specs/`,见 [archive/specs/README.md](../archive/specs/README.md)。当前归档:
- `CC_Prompt_Feature_Assembler_Revision.md` (v1.3.2 算法替换提示词, 实施落地 ADR-0004)
- `Place_Anchor_Spec_Final.md` (DBCH 算法 spec v0.5, 实施落地 ADR-0005)
- `high_frequency_Place_Detection_Spec.md` (高频低质量地点判定 spec v0.2, 实施落地 ADR-0006)
- `Cluster_Aggregation_Spec.md` (theme 语义簇聚合 spec v0.2, 实施落地 ADR-0008)
- `Event_Field_And_Aggregation_Spec.md` (event 字段扩充与小集聚合 spec v0.2, 实施落地 ADR-0009)
- `Time_Aggregation_Spec.md` (time 自然日归属 + 链式切分 spec v0.2, 实施落地 ADR-0011)
- `Path_B_Event_Aggregation_Spec.md` (path B event primary_share + activity 二次门槛 spec v0.2, 实施落地 ADR-0012)
- `Path_B_Theme_Aggregation_Spec.md` (path B theme 双层判定 spec v0.3, 实施落地 ADR-0013)
- `Path_B_Anchor_Aggregation_Spec.md` (path B anchor 双层判定 spec v0.3, 实施落地 ADR-0014)
- `Path_B_Emotional_Aggregation_Spec.md` (path B emotional 开放字段 + 单层聚类 spec v0.2, 实施落地 ADR-0015)
- `Location_Geocoder_4Tier_Spec.md` (Location · Geocoder + 4 档升级 spec v0.1, 实施落地 ADR-0016)
- `Pipeline_Cascade_Backfill_Spec.md` (Pipeline 三路分流 + cascade 维度强度排序 spec v0.3, 实施落地 ADR-0017)

## 读取顺序建议

新人接手项目时:

1. 项目根目录的 `CLAUDE.md` (项目宪法)
2. `01_architecture.md` (架构总图 + 三路 + 仲裁)
3. `02_data_contracts.md` (所有数据结构)
4. `03_truth_table_main.md` + `04_truth_table_growth.md` + `05_truth_table_backfill.md` (三路核心算法)
5. `06_hard_rules.md` + `09_arbitration.md` (红线 + 最终结局逻辑)
6. `11_observability.md` (落痕格式)
7. `12_open_questions.md` (已知歧义)
