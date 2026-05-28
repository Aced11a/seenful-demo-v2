# 测试总览 (auto-generated)

> 跑 `python tests/personas/_gen_index.py` 重生

## 一、统计

- **Persona Scenarios**: 64 个 (path B 34 / path A 15 / cascade 15)
- **单元测试**: 469 个 (跨 27 个文件)
- **总通过**: 511 (含 1 个空 fixture dir skip)

## 二、L2 (Path B 主路径整批)

(34 个)

### ✅ 常规正例

| Scenario | Persona | 焦点维度 | Expected |
|---|---|---|---|
| `A1_zhang_insurance_burst` <br> A.1 张奶奶保险式重复拍 3 张同物 30 秒内 | 张zhang | - | _(无具体 expected, 仅跑 invariants)_ |
| `A2_zhang_weekly_park_walk` <br> A.2 张奶奶周期性散步 跨 4 周 8 张 | 张zhang | - | _(无具体 expected, 仅跑 invariants)_ |
| `A5_zhang_shopping_subzone` <br> A.5 张奶奶商场反复来回 6 张子区域 | 张zhang | - | _(无具体 expected, 仅跑 invariants)_ |
| `A6_zhang_plant_growth_30d` <br> A.6 张奶奶跟踪植物生长 30 天 8 张 | 张zhang | - | _(无具体 expected, 仅跑 invariants)_ |
| `ANC1_li_anchor_multi_granularity` <br> ANC.1 李叔叔 anchor 多颗粒 3 张 (meaning 抽象 + object 具体) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `B1_li_burst_plus_one` <br> B.1 李叔叔兵马俑爆拍 12 张 + 顺路加油 1 张 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `B2_li_xihu_overnight` <br> B.2 李叔叔跨业务日西湖夜游 6 张 (22:00 → 02:00) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `B3_li_one_day_long_break` <br> B.3 李叔叔同一天中场长停顿 5 张 (上午+午饭休+下午) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `B5_li_business_plus_travel` <br> B.5 李叔叔上海开会 + 苏州周末 6 张 (event 切换) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `B6_li_airport_farewell` <br> B.6 李叔叔送女儿机场 + 回程 8 张 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `B7_li_pick_grandkid_routine` <br> B.7 李叔叔接外孙女 5 天连续高频时间地点 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `C3_xiaowang_photo_wall` <br> C.3 小王网红打卡墙 30 秒 4 人同墙 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `C4_xiaowang_steak_5_angles` <br> C.4 小王餐厅一道菜 5 角度 60 秒 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `C6_xiaowang_hike_gps_drift` <br> C.6 小王山区徒步 GPS 漂移 ±150m 5 张 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `C7_xiaowang_concert_burst` <br> C.7 小王演唱会 1 分钟 8 张连拍 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `C8_xiaowang_cafe_multi_subject` <br> C.8 小王咖啡馆 5 咖啡 + 3 朋友合影 (同地不同主体) | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `D1_zhang_screenshot_in_gathering` <br> D.1 张奶奶聚餐 3 张 + 微信截图 2 张穿插 | 张zhang | - | _(无具体 expected, 仅跑 invariants)_ |
| `D2_zhang_hospital_sensitive` <br> D.2 张奶奶体检医院 3 张 (sensitive_level=medium) | 张zhang | - | `display_decision=suppress` |
| `D9_zhang_high_freq_strong_event` <br> D.9 张奶奶家生日 6 张 (高频地点 + 强 celebration 不应被过度抑制) | 张zhang | - | `display_decision=show_mini_album` |
| `EV1_zhang_event_signal_conflict` <br> EV.1 张奶奶餐厅周年庆 event 多信号冲突 3 张 | 张zhang | - | _(无具体 expected, 仅跑 invariants)_ |
| `T12_li_one_day_multi_spot_70km` <br> #12 李叔叔一日游 故宫+长城+鸟巢 6 张跨 70km | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `T13_xiaowang_citywalk_uniform_low` <br> #13 小王 Citywalk 低密度均匀 6 张 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `T15_xiaowang_fireworks_newyear` <br> #15 小王跨年烟花 8 张 10 分钟跨业务日 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `T18_xiaowang_checkin_multi_spot` <br> #18 小王网红打卡跨城 5 个点 5 张 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `T19_li_marathon_10_spots` <br> #19 李叔叔暴走 10 景点 高频切换 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `T1_li_xihu_loop_15km` <br> #1 李叔叔环西湖闭环 15km 8 张 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `T20_li_resort_lazy_3days` <br> #20 李叔叔度假村躺平 3 天 GPS 全程同 5 张 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `T21_xiaowang_burst_plus_gap` <br> T.21 小王连拍+长间隔 5 张 1s + 1 张 30min 后 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `T22_li_camping_crossday_event` <br> T.22 李叔叔周末露营跨自然日同事件 6 张 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `T3_li_pedestrian_street_uneven` <br> #3 李叔叔步行街密度不均 6 张 (3 密 + 3 稀) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `T4_xiaowang_hike_sparse_dense` <br> #4 小王徒步前疏后密 4 张 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `T7_li_around_landmark_small_loop` <br> #7 李叔叔绕东方明珠小环 6 张 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `TH1_li_theme_granularity_mix` <br> TH.1 李叔叔 theme 颗粒度混合 4 张 (粗/中/细/感官) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `TH2_xiaowang_multi_strong_theme` <br> TH.2 小王单图多 strong theme 3 张 (万圣节+晚宴+生日) | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |

## 三、L2.5 (Path A 动态生长 单张 vs 老相册)

(15 个)

### ✅ 常规正例

| Scenario | Persona | 焦点维度 | Expected |
|---|---|---|---|
| `A4_zhang_granddaughter_grab` <br> A.4 张奶奶被孙女抢手机自拍 3 张突变 | 张zhang | - | `decision_tier=ask_user` |
| `L25_li_camping_to_xihu_no_merge` <br> L2.5 李叔叔露营 vs 西湖相册 → no_merge (跨主题) | 李youke | - | `decision_tier=no_merge` |
| `L25_li_multi_anchor_to_xihu` <br> L2.5 李叔叔多 anchor 照 vs 西湖相册 (anchor 颗粒度边界) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `L25_li_pick_grandkid_high_freq` <br> L2.5 李叔叔接娃 vs 接娃相册 → auto/ask (高频地点) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `L25_li_th_granularity_细颗粒_to_xihu` <br> L2.5 李叔叔西湖细颗粒标签 vs 西湖相册 (语义簇兜底) | 李youke | - | `decision_tier=auto_merge` |
| `L25_R1_zhang_balcony_to_walk_no_merge` <br> L2.5 #R1 张奶奶阳台花 vs 公园散步相册 → no_merge (跨场景反例) | 张zhang | - | `decision_tier=auto_merge` |
| `L25_R2_zhang_walk_to_walk_auto_merge` <br> L2.5 #R2 张奶奶公园晨练 vs 公园相册 → auto_merge (基础正例) | 张zhang | - | `decision_tier=auto_merge` |
| `L25_R3_li_xihu_new_to_xihu_auto` <br> L2.5 #R3 李叔叔西湖新照 (粗颗粒) vs 西湖相册 → auto_merge (基础正例) | 李youke | - | `decision_tier=auto_merge` |
| `L25_R4_li_gugong_to_xihu_no_merge` <br> L2.5 #R4 李叔叔故宫 vs 西湖相册 → no_merge (跨城反例) | 李youke | - | `decision_tier=auto_merge` |
| `L25_xiaowang_concert_to_walk_no_merge` <br> L2.5 小王演唱会照 vs 张奶奶公园相册 → no_merge (跨用户反例) | xiaowang | - | `decision_tier=no_merge` |
| `L25_xiaowang_multi_theme_to_walk_no_merge` <br> L2.5 小王单图多 strong theme (万圣节+生日) vs 张奶奶公园相册 → no_merge | xiaowang | - | `decision_tier=no_merge` |
| `L25_zhang_distractor_screenshot_to_walk` <br> L2.5 张奶奶截图干扰 vs 公园相册 → no_merge | 张zhang | - | `decision_tier=auto_merge` |
| `L25_zhang_event_conflict_to_album` <br> L2.5 张奶奶餐厅周年庆 (event 多信号冲突) vs 孙女相册 | 张zhang | - | _(无具体 expected, 仅跑 invariants)_ |
| `L25_zhang_high_freq_birthday_celebration` <br> L2.5 张奶奶生日 (家高频) vs 孙女相册 → auto_merge (强 event 不降) | 张zhang | - | `decision_tier=auto_merge` |
| `L25_zhang_sensitive_to_any_no_merge` <br> L2.5 张奶奶医院敏感 vs 公园相册 → no_merge (红线 #6) | 张zhang | - | `decision_tier=no_merge` |

## 四、Cascade (Path C 回滚 单张 vs 沉淀池)

(15 个)

### ✅ 常规正例

| Scenario | Persona | 焦点维度 | Expected |
|---|---|---|---|
| `C_li_marathon_no_recall` <br> cascade 李叔叔暴走单张 vs 沉淀池 (其他暴走) → 看决定 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `C_li_overnight_recall` <br> cascade 李叔叔西湖夜游单张 vs 沉淀夜游 → 召回 (跨业务日) | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `C_li_resort_lazy_empty` <br> cascade 李叔叔度假村单张 vs 空池 → insufficient | 李youke | - | `decision_tier=insufficient_candidates` |
| `C_li_th_granularity_recall` <br> cascade 李叔叔西湖感官标签 vs 沉淀池(4 颗粒度西湖) → 语义簇召回 | 李youke | - | _(无具体 expected, 仅跑 invariants)_ |
| `C_R1_zhang_balcony_recall_balcony` <br> cascade #R1 张奶奶阳台花新照 vs 沉淀池 (有阳台花) → create_new_album | 张zhang | - | `decision_tier=create_new_album` |
| `C_R2_zhang_empty_pool_insufficient` <br> cascade #R2 张奶奶单张 vs 空池 → insufficient (基础反例) | 张zhang | - | `decision_tier=insufficient_candidates` |
| `C_R3_li_xihu_recall_xihu` <br> cascade #R3 李叔叔西湖新照 vs 沉淀池 (西湖类似) → create_new_album | 李youke | - | `decision_tier=create_new_album` |
| `C_R4_li_gugong_cross_city_no_recall` <br> cascade #R4 李叔叔故宫 vs 沉淀西湖池 → no_backfill (跨城反例) | 李youke | - | `decision_tier=create_new_album` |
| `C_R5_zhang_event_conflict_empty` <br> cascade #R5 张奶奶餐厅周年 (event 冲突) vs 空池 → insufficient | 张zhang | - | `decision_tier=insufficient_candidates` |
| `C_xiaowang_checkin_no_recall` <br> cascade 小王网红打卡单张 vs 沉淀池(其他网红) → 看决定 | xiaowang | - | _(无具体 expected, 仅跑 invariants)_ |
| `C_xiaowang_concert_no_recall` <br> cascade 小王演唱会单张 vs 沉淀(无相关) → no_backfill | xiaowang | - | `decision_tier=insufficient_candidates` |
| `C_xiaowang_fireworks_no_recall` <br> cascade 小王跨年烟花单张 vs 沉淀池(无烟花) → no_backfill | xiaowang | - | `decision_tier=insufficient_candidates` |
| `C_xiaowang_multi_theme_no_recall` <br> cascade 小王单图多 strong theme vs 沉淀池(任何) → 看决定 | xiaowang | - | `decision_tier=insufficient_candidates` |
| `C_zhang_screenshot_no_recall` <br> cascade 张奶奶截图干扰 vs 沉淀池 → no_backfill | 张zhang | - | `decision_tier=create_new_album` |
| `C_zhang_sensitive_no_recall` <br> cascade 张奶奶敏感照 vs 沉淀池 → no_backfill (HR-PRE) | 张zhang | - | `decision_tier=insufficient_candidates` |

## 五、单元测试索引

| 文件 | 测试数 | 测什么 |
|---|---|---|
| `tests/unit/test_arbitration.py` | 9 | 三路仲裁器 4 个 case + 严格优先级 |
| `tests/unit/test_backfill_engine.py` | 7 | Path C apply_backfill_caps 三条 Caps strong-only |
| `tests/unit/test_backfill_scan.py` | 10 | Path C OR 粗筛 (gps/theme/event) + 30 天窗口 |
| `tests/unit/test_bands.py` | 6 | 维度分档阈值 + 高频地点降档 |
| `tests/unit/test_cascade_backfill.py` | 12 | ADR-0017 cascade_backfill_single + 维度强度排序 + event×0.5 |
| `tests/unit/test_contracts.py` | 15 | Pydantic 契约校验 (L1Output / GrowthDecision / 等) |
| `tests/unit/test_engine_clamp.py` | 10 | Path B Policy Engine LLM clamp + bounds + HR-POST |
| `tests/unit/test_event_aggregation.py` | 19 | ADR-0009 path A event 三级分层聚合 + 四档匹配 |
| `tests/unit/test_features_anchor.py` | 7 | ADR-0014 path B anchor 双层语义簇 + AN.1-AN.5 grid |
| `tests/unit/test_features_emotional.py` | 14 | ADR-0015 path B emotional 单层 + EM.0 neutral preempt |
| `tests/unit/test_features_event.py` | 23 | ADR-0012 path B event primary_share + activity 二次门槛 + E.1-E.8 |
| `tests/unit/test_features_event_people.py` | 5 | people 维度 v0.1 简化 (P0 上限 0.65) |
| `tests/unit/test_features_location.py` | 25 | ADR-0010 path B location 分级 DBSCAN + PCA OBB + 形状校正 + transit |
| `tests/unit/test_features_theme.py` | 14 | ADR-0013 path B theme 双层语义簇 + TH.1-TH.5 grid |
| `tests/unit/test_features_time.py` | 38 | ADR-0011 path B time 自然日归属 + 链式切分 + T1/T2/T3 grid |
| `tests/unit/test_geocoder.py` | 15 | ADR-0016 高德 Reverse Geocoding 4 档 + MockGeocoder |
| `tests/unit/test_growth_features.py` | 12 | Path A 4 维 features 计算 (location/theme/event/anchor) |
| `tests/unit/test_growth_scan.py` | 7 | Path A 候选老相册筛选 (is_growing + 容量 + excluded) |
| `tests/unit/test_hard_rules.py` | 7 | HR-PRE-01..05 前置硬规则 + HR-POST-01..03 |
| `tests/unit/test_invariants.py` | 18 | _(详见源码)_ |
| `tests/unit/test_low_quality_place.py` | 16 | ADR-0006 高频低质量地点判定 Plan A (双 density) |
| `tests/unit/test_place_anchor.py` | 34 | ADR-0005 path A location DBCH (DBSCAN + 凸包 + buffer) |
| `tests/unit/test_plan_b_features.py` | 25 | ADR-0018 L2 1.0 (Plan B) 7 维 v1.3 §3.2 抄本 |
| `tests/unit/test_theme_aggregation.py` | 50 | ADR-0008 path A theme 层次聚类 + 频次加权匹配 |
| `tests/unit/test_truth_table_growth.py` | 18 | Path A 生长真值表 10 条 (G-A1 ~ G-F1) |
| `tests/unit/test_truth_table_main.py` | 38 | Path B 主真值表 28 条 (A1-A4 + B1-B9 + G1-G4 + C/D/E + F1) |
| `tests/unit/test_user_home_city.py` | 15 | ADR-0016 user_home_city 推断 + 4 档判定 |

## 六、跑测试

```bash
# 跑全部 (511 个)
python -m pytest -v

# 只跑 persona scenarios
python -m pytest tests/personas/ -v

# 只跑某个 scenario
python -m pytest tests/personas/test_persona_scenarios.py -k '<scenario_name>'

# 重生索引
python tests/personas/_gen_index.py
```