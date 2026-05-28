# TEST_PLAN · 76(实际 77)场景 → API 台子覆盖映射

> 状态: **v0.2 · §6 边界判定 Ace 已确认(2026-05-28)· 可跑 50 条**
> 配套: `SPEC.md`(台子设计)、`CLAUDE.md`(子项目宪法)。本文件只管"哪些场景本轮跑、哪些延后、为什么"。
> 数据源: `../tests/personas/scenarios/*.yaml`(共 77 个,只读)。

---

## 0. 为什么需要分类

新台子缺两类信号(当前微信小程序环境拿不到,见 `SPEC.md` §5 D):

- **GPS / `exif_location` / 高频地点** → location 维度无信号
- **`captured_at`** 删除 → **time 维度也无信号**(自然日归属、链式切分、gap 切集、连拍升档全失效)

因此判定的核心问题:**把 GPS + time 都拿掉后,这个场景的"正确答案"还成立、还可验吗?**

---

## 1. 判定图例

| 标记 | 含义 | 处理 |
|---|---|---|
| ✅ RUNNABLE | 期望结果靠语义字段(theme/subject/event_hint/emotional/sensitive/people/质量)即可达成+验证 | 本轮跑,正常比对 |
| 🟡 PARTIAL | 成集/合并动作能靠语义跑通,但场景**专门压的那个边界**靠 GPS/time → 该断言延后 | 跑成集动作,**放宽/跳过**边界断言;边界进待办栏 |
| ⛔ DEFERRED | 期望结果**根本上靠 GPS 邻近 / time 间隔**才成立 | 本轮**不发请求**,标 `deferred`,进 §4 待办栏 |

原因标签:`(loc)` GPS/位置 · `(time)` 时间/间隔 · `(hfp)` 高频地点。

---

## 2. 覆盖总览

| persona | ✅ 可跑 | 🟡 部分 | ⛔ 延后 | 小计 |
|---|---|---|---|---|
| zhang (laoqi_zhang) | 20 | 1 | 11 | 32 |
| li (laoli_youke) | 12 | 3 | 13 | 28 |
| xiaowang | 10 | 4 | 3 | 17 |
| **合计** | **42** | **8** | **27** | **77** |

> 本轮**真正打到后端 = 42 ✅ + 8 🟡 = 50 条**;27 ⛔ 进 location/time 待办栏(§4),将来拿到地理/时间信息再补。

---

## 3. 逐场景判定(按 persona)

### 3.1 ZHANG (laoqi_zhang) · 32

| 场景 | path | 主导维度 | 判定 | 原因/备注 |
|---|---|---|---|---|
| D2_hospital_sensitive | L2 | sensitive | ✅ | sensitive_level 强制 suppress,红线 #6,无需 GPS/time |
| FP_A1_breakfast_daily | L2 | theme/food | ✅ | 早餐成集靠 food 主题;HFP 防御那一面本轮不触发 |
| FP_A6_cafe_multi_subject | L2 | theme/subject/event | ✅ | 咖啡馆多主体靠语义,TH.0 边界 |
| FP_B1_stoplist_loophole | L2 | subject 泛词 | ✅ | stoplist 漏洞纯 subject/tag 问题 |
| FP_B3_event_activity_walk | L2 | event/activity | ✅ | E.1 严格门槛靠 event_hint + activity 语义 |
| A6_plant_growth_30d | L2 | theme/subject | ✅ | 植物生长靠 theme;"30 天持续"的 time 面不触发 |
| CB_05_balcony_recall | cascade | theme | ✅ | balcony_flower 主题召回 |
| CB_06_empty_pool | cascade | 空池 | ✅ | 空池 → insufficient,与 GPS/time 无关 |
| CB_09_event_conflict_empty | cascade | event/空池 | ✅ | 空池 → insufficient |
| CB_14_screenshot_no_recall | cascade | theme/质量 | ✅ | 截图干扰项靠主题无关/质量 |
| CB_15_sensitive_no_recall | cascade | sensitive | ✅ | 敏感 PRE 阻断 |
| D1_screenshot_in_gathering | L2 | theme/质量 | ✅ | 截图过滤(**可能暴露 D1 缺 image_type 字段**) |
| EV1_event_signal_conflict | L2 | event/activity | ✅ | celebration vs meal,ADR-0012 纯语义 |
| L25_R1_balcony_to_walk_no_merge | L2.5 | theme 不匹配 | ✅ | 主题不匹配 → no_merge |
| L25_R2_walk_to_walk_auto_merge | L2.5 | theme | ✅ | 主题匹配 → auto_merge |
| L25_sensitive_to_any_no_merge | L2.5 | sensitive | ✅ | 红线 #6 |
| L25_distractor_screenshot_to_walk | L2.5 | theme/质量 | ✅ | 干扰项过滤 |
| A4_granddaughter_grab | L2.5 | people/theme | ✅ | 孙女自拍靠 people_presence + 主题 |
| L25_event_conflict_to_album | L2.5 | event | ✅ | celebration primary 主导 |
| FP_B2_th0_reverse(li) | L2 | theme | ✅ | (persona=li,归 li 计数) |
| L25_high_freq_birthday_celebration | L2.5 | event/hfp | 🟡 | event 可促成 auto_merge,但**"event 压过 HFP"**那条(HR-POST-03)无 hfp 信号验不了 |
| D9_high_freq_strong_event | L2 | event/hfp | ⛔ (hfp) | 整个场景是 HFP + 强 event 边界,无 hfp 信号 |
| FP_A2_daily_record_pretend | L2 | event/loc | ⛔ (loc) | 拒绝靠跨城,无 GPS 看不到跨城(**真 bug FP.A2**) |
| FP_A3_cross_season_park | L2 | time | ⛔ (time) | 跨 4 周超长时间,T3 cap 靠 time |
| FP_A5_repeat_hotpot | L2 | time | ⛔ (time) | 5 次跨 4 月,拒绝假合并靠 time 跨度 |
| FP_B4_outing_walk_cheat | L2 | loc | ⛔ (loc) | 跨 5 城,拒绝靠 location |
| FP_B5_burst_3_events | L2 | time | ⛔ (time) | 连拍升档纯 time |
| FP_B7_location_buffer_edge | L2 | loc | ⛔ (loc) | 9.9km 多簇缓冲边界纯 location |
| FP_B11_hfp_mismarked | L2 | loc/hfp | ⛔ (loc) | HFP 漏标防御纯位置 |
| A1_insurance_burst | L2 | time/loc | ⛔ (time) | 连拍 30s 不应升 strong,靠 time 密度 |
| A2_weekly_park_walk | L2 | time/loc | ⛔ (time) | 跨 4 周周期记录 |
| A5_shopping_subzone | L2 | loc | ⛔ (loc) | 商场子区域反复纯 location |

### 3.2 LI (laoli_youke) · 28

| 场景 | path | 主导维度 | 判定 | 原因/备注 |
|---|---|---|---|---|
| TH1_theme_granularity_mix | L2 | theme | ✅ | 颗粒度混合语义簇 |
| B5_business_plus_travel | L2 | event(work/outing) | ✅ | 开会 vs 旅游靠 event_hint 拆;跨城是次要 |
| CB_01_shanghai_oneday_recall | cascade | theme(city_tour) | ✅ | 暴走路线靠 city_tour 主题召回 |
| CB_03_resort_lazy_empty | cascade | 空池 | ✅ | 空池 → insufficient |
| CB_04_th_granularity_recall | cascade | theme | ✅ | 语义簇召回 |
| CB_07_xihu_recall | cascade | theme(lake) | ✅ | xihu 已按 ADR-0025 转 lake 主题 |
| FP_B2_th0_reverse | L2 | theme | ✅ | 故意混 2 主题,TH.0 medium |
| ANC1_anchor_multi_granularity | L2 | anchor/subject | ✅ | meaning_anchors + object_anchors 双层 |
| L25_camping_to_xihu_no_merge | L2.5 | theme 不匹配 | ✅ | camping vs lake 主题不匹配 |
| L25_R3_xihu_new_to_xihu_auto | L2.5 | theme(lake) | ✅ | 主题匹配 auto_merge |
| L25_th_granularity_细颗粒_to_xihu | L2.5 | theme | ✅ | 细颗粒语义簇 |
| L25_multi_anchor_to_xihu | L2.5 | anchor | ✅ | 多锚点匹配(同地点为次要) |
| T22_camping_crossday_event | L2 | event/time | 🟡 | camping 主题/event 可成集,**跨业务日**(cross 04:00)靠 time → 该面延后 |
| CB_02_overnight_xihu_recall | cascade | theme(lake)/time | 🟡 | lake 主题可召回,**跨 04:00 夜游**靠 time → 该面延后 |
| T7_around_landmark_small_loop | L2 | subject/loc | 🟡 | 东方明珠作 subject/salient_object 撑主题成集;**地标→location 邻近小环路**那一面延后(Ace 定 2026-05-28) |
| T1_xihu_loop_15km | L2 | loc/time | ⛔ (loc+time) | 环湖闭环 15km + 连续时长 |
| T3_pedestrian_street_uneven | L2 | loc | ⛔ (loc) | 密度不均 + 高楼漂移 |
| T12_one_day_multi_spot_70km | L2 | loc/time | ⛔ (loc+time) | 一日多点 70km |
| T19_marathon_10_spots | L2 | loc/time | ⛔ (loc+time) | 10 景点高频切换 |
| T20_resort_lazy_3days | L2 | loc/time | ⛔ (loc+time) | 度假村 3 天同 GPS,非高频识别 |
| B1_burst_plus_one | L2 | loc | ⛔ (loc) | 爆拍 + 加油站长尾,outlier 拒绝靠位置(**真 bug B1**) |
| B2_xihu_overnight | L2 | time | ⛔ (time) | 跨 04:00 业务日 |
| B3_one_day_long_break | L2 | time | ⛔ (time) | 午休 2-3h gap 不切集 |
| B6_airport_farewell | L2 | loc | ⛔ (loc) | 同行程不同 location 的跨点聚合 |
| B7_pick_grandkid_routine | L2 | loc/hfp/time | ⛔ (loc) | 每天同时同地高频例行 |
| CB_08_gugong_cross_city_no_backfill | cascade | loc | ⛔ (loc) | 跨城拒绝靠 location(**真 bug CB.08**) |
| L25_R4_gugong_to_xihu_no_merge | L2.5 | loc | ⛔ (loc) | 同 ancient 主题,拒绝靠跨城(**真 bug L25.R4**) |
| L25_pick_grandkid_high_freq | L2.5 | loc/hfp | ⛔ (loc) | 接娃高频例行 |

### 3.3 XIAOWANG · 17

| 场景 | path | 主导维度 | 判定 | 原因/备注 |
|---|---|---|---|---|
| T13_citywalk_uniform_low | L2 | theme(citywalk) | ✅ | 低密度 DBSCAN 死穴靠主题救场,主题独立成集 |
| TH2_multi_strong_theme | L2 | theme | ✅ | 单图多 strong 主题 |
| C4_steak_5_angles | L2 | subject(steak) | ✅ | 同道菜 5 角度靠 subject;K_outer 误判属位置不触发 |
| C8_cafe_multi_subject | L2 | theme/subject | ✅ | 多主体 Top-K(ADR-0024) |
| CB_10_checkin_no_backfill | cascade | theme 无匹配 | ✅ | 打卡点跨主题 → insufficient |
| CB_11_concert_cross_city | cascade | theme 孤立 | ✅ | 演唱会池中无同主题 → insufficient(跨城为次要) |
| CB_12_fireworks_no_recall | cascade | theme 无匹配 | ✅ | 跨主题无召回 |
| CB_13_multi_theme_no_recall | cascade | theme | ✅ | 多主题 + 无匹配 |
| L25_concert_to_walk_no_merge | L2.5 | theme 不匹配 | ✅ | concert vs walk 不匹配 |
| L25_multi_theme_to_walk_no_merge | L2.5 | theme/空 album | ✅ | 空 album 列表 → no_merge |
| T15_fireworks_newyear | L2 | theme/time | 🟡 | fireworks 主题可成集,**跨 00:00 + 连拍**靠 time → 该面延后 |
| T18_checkin_multi_spot | L2 | theme/loc | 🟡 | city checkin 主题可成集,**5 点跨 5km**靠 location → 该面延后 |
| C3_photo_wall | L2 | theme/loc | 🟡 | pink_wall 主题/people 可成集,**同 GPS + 30s 连拍**延后 |
| C7_concert_burst | L2 | event/time | 🟡 | performance event 可成集,**T1.5 连拍升 strong**靠 time → 该面延后 |
| T4_hike_sparse_dense | L2 | time/loc | ⛔ (time+loc) | 前疏后密 + T1 事件 |
| T21_burst_plus_gap | L2 | time | ⛔ (time) | 连拍 + 30min gap |
| C6_hike_gps_drift | L2 | loc | ⛔ (loc) | GPS 漂移 ±150m 是整个场景的点 |

---

## 4. 延后栏(location / time 待办,进 HTML)

将来拿到 **GPS / 高频 / captured_at** 后必须补的断言。分两块:

### 4.1 ⛔ 全延后(27 条)——拿到信号后整条恢复

- **location 主导(13)**: FP_A2, FP_B4, FP_B7, FP_B11, A5(zhang) · T3, B1, B6, B7, CB_08, L25_R4, L25_pick_grandkid(li) · C6(xiaowang)
- **time 主导(8)**: FP_A3, FP_A5, FP_B5, A1, A2(zhang) · B2, B3(li) · T21(xiaowang)
- **loc+time 双主导(5)**: T1, T12, T19, T20(li) · T4(xiaowang)
- **hfp 主导(1)**: D9(zhang)

> 每条在 HTML 单列:原场景 → 缺哪类信号 → 拿到后的预期(路径/决策/合并目标)。

### 4.2 🟡 部分延后(8 条)——本轮跑成集,补边界断言

| 场景 | 本轮验什么 | 拿到 GPS/time 后补什么 |
|---|---|---|
| L25_high_freq_birthday(zhang) | event 促成 auto_merge | HR-POST-03:event 压过 HFP |
| T7_around_landmark(li) | 东方明珠作 subject 撑主题成集 | 地标 location 邻近小环路那一面 |
| T22_camping_crossday(li) | camping 成集 | 跨 04:00 业务日仍归一集 |
| CB_02_overnight_xihu(li) | lake 主题召回 | 跨 04:00 夜游召回边界 |
| T15_fireworks_newyear(xiaowang) | fireworks 成集 | 跨 00:00 自然日 + T1.5 连拍 |
| T18_checkin_multi_spot(xiaowang) | checkin 主题成集 | 5 点跨 5km 多 spot 容器 |
| C3_photo_wall(xiaowang) | pink_wall 成集 | 同 GPS + 30s 连拍升档 |
| C7_concert_burst(xiaowang) | performance 成集 | T1.5 连拍升 strong |

---

## 5. 用例装配(给 Step 2)

50 条可跑的(42 ✅ + 8 🟡)落成 `cases/<path>/*.yaml`,**每场景一个自包含隔离 session**(详见 `SPEC.md` §3,非跨场景时间线):

0. **串行 + per-id 账本 teardown**(API#3 默认 per-mockBizId 级联删,2026-05-28 实测;后端或有额外配置触发整库,runner 用 per-id 在两种模式下都正确)。
1. **L2(batch)**:`trigger` = 整批照片;无 setup。提交 → 取结果 → teardown 删本场景 id。
2. **L2.5(growth)**:`setup.seed_photos` = 原 `old_albums` 的成员照片(同一 session 内先建集);`trigger` = 单张新照。前置没建成 → `BLOCKED`(非 mismatch)。
3. **cascade**:`setup.pool_photos` = 原 `sediment_pool` 照片;`trigger` = 单张触发照。
4. ⛔ 场景仍写进 `cases/` 但标 `verdict: deferred` + `defer_reason: <loc|time|hfp>`,**不发请求**,只进 §4 待办栏。
5. ⚠ 若后端整库 wipe 开关开启,harness 跑动时不能同时手测后端(任意一方的 del 会清对方)。

> 各 L2.5 的 `seed_photos`(来自原 `old_albums` 成员)、各 cascade 的 `pool_photos`(来自原 `sediment_pool`),需读原 persona/场景逐一填,作为 **Step 2** 产出。本 plan 只定可跑性与分组。

---

## 6. 边界判定(Ace 已确认 2026-05-28)

1. **FP_A1 早餐流水账 → ✅**(已确认):靠 food 主题成集;HFP 防御那一面本轮拿不到信号,只验主题成集面。
2. **T7 东方明珠 → 🟡**(已确认,原 ⛔ 改判):东方明珠作 subject/salient_object 撑主题成集本轮跑,**地标 location 邻近小环路那一面延后**(进 §4.2)。
3. **CB_11 演唱会跨城 → ✅**(已确认):判 insufficient 靠 theme 孤立(池中无同主题),跨城为次要背景。
4. **7 条真 bug(FP_A2/B1、CB_08、L25_R1/R4 等)**:其中靠 location/time 的(FP_A2、CB_08、L25_R4、B1)本轮 ⛔ 验不了;不靠位置的(FP_B1 stoplist、L25_R1 主题不匹配、D1 截图)留 ✅,后端若仍犯会照实标 mismatch。

---

## 7. 执行方案(how —— Ace 让我定的测试方法论)

> 约束来自单库 + 严格串行(API#3 默认 per-id 级联,可能存在的整库 wipe 配置下跑动时勿手测)。核心思路:**先验台子,再验后端**——别用没校准的台子去跑 50 条,否则台子 bug 会淹没真实 mismatch。
> 另一核心原则(Ace 2026-05-28 明确):**expected = "在我们能给的信号下,产品意图应不应该成集"**,不是猜后端怎么走。后端 ≠ expected = 后端算法与产品意图的 gap,正是台子要暴露的信号,**不改 expected 去迎合后端**(CLAUDE 第4条)。

### 7.1 四阶段(每阶段过了才进下一阶段)

| 阶段 | 跑什么 | 目的 / 通过条件 |
|---|---|---|
| **P0 链路自检** | `step1_smoke`(已过)+ 补验 `wipe_db()` 无参清库可用 | 提交→轮询→wipe 三步通,鉴权/包装/码值已知 |
| **P1 三路 pilot(各 1 条)** | 每路挑 1 条最干净的 ✅:L2=`D2_hospital_sensitive`、L2.5=`L25_R3_xihu_new_to_xihu_auto`、cascade=`CB_05_balcony_recall` | **校准台子**:人工核 adapter 出的 l1Result、码值映射、verdict 判定、HTML 渲染都对。三条可解释 → 放量 |
| **P2 全量(50)** | 42✅+8🟡,按 path 分组串行 L2→L2.5→cascade | 每条独立 session(开头 wipe)。只收集,不中途改题 |
| **P3 偏差分诊** | 把非 match 结果归类(7.3) | 出偏差清单给后端 |

> 为什么 pilot 选这三条:L2 选 sensitive(决策唯一、不依赖前置、红线 #6 好判);L2.5 选 lake auto_merge(验 setup 建集 + 单张挂入全链);cascade 选 balcony 召回(验 setup 落沉淀池 + 触发回扫)。三条覆盖三种 session 形态。

### 7.2 单场景执行协议

见 `SPEC.md` §3 的 loop(wipe → setup → trigger → 轮询 → 比对)。本节不重复。

### 7.3 Verdict 分类法 + 分诊顺序

| verdict | 含义 | 处理 |
|---|---|---|
| `match` | 后端结果 == expected | 绿 |
| `acceptable` | 落在多值期望内(意图 no/auto 但结果 ask_user)| 黄绿,记备注;**绝不放宽 no→merge**(CLAUDE 第4条)|
| `mismatch` | 后端 ≠ expected 且不可接受 | 红,进偏差清单,**不改 expected** |
| `BLOCKED` | L2.5/cascade 前置没建成 | 灰,先查 setup,不算后端错 |
| `deferred` | ⛔ 场景,没发请求 | 灰,进 §4 location/time 待办 |
| `error` | 轮询超时 / HTTP 5xx / wipe 失败 | 灰,重试 1 次仍错记清单,不中断全量 |

**分诊 mismatch 前先排除**:① 码值映射缺(我的 `code_map` 没覆盖某 `displayDecisionCode`)→ 补映射重判,**不算后端 bug**;② BLOCKED 误判(前置其实没成);③ 余下才是**真 bug** → 进清单。§6.4 的已知 bug 若后端仍犯,照实标 mismatch 但清单里注明"预期内已知"。

### 7.4 输出物

- `_DASHBOARD.html`:按 path 分组 + verdict 配色;每条 **expected vs actual 并排**(route / displayDecisionCode / decisionRemark / miniAlbumId);头部统计条(各 verdict 计数);deferred 单独区列「缺哪类信号 → 拿到后预期」。
- `results/deviation_<ts>.md`:仅 `mismatch` + `error`,给后端同事的精简清单(场景 / 期望 / 实际 / 初判类别)。

### 7.5 安全 / 纪律

- 串行;wipe 清整库 → **harness 跑动时不能同时手测后端**(CLAUDE 第5条)。
- 密钥走 env(第3条);`results/` 落盘脱敏。
- 不改 expected、不替后端改规则(第4条);bug 先留可见。

---

*v0.4 · 2026-05-28(同日校准)· §5 / §7 改回 per-id 账本 teardown(API#3 实测为 per-mockBizId 级联,后端或有额外整库 wipe 配置);§7 头部明确 expected = 产品意图原则(Ace 2026-05-28 拍)*
*v0.3 · 2026-05-28 · 新增 §7 执行方案(四阶段 P0-P3 / pilot-first / verdict 分类法 + 分诊 / 输出物 / 安全),Ace 让我定测试方法论*
*v0.2 · 2026-05-28 · §6 边界判定 Ace 确认:FP_A1 ✅ / CB_11 ✅ 保持,**T7 ⛔→🟡**(东方明珠作 subject 撑主题);计数 42✅/8🟡/27⛔,可跑 50;§5 装配改「串行+开头整库 wipe」对齐 API#3 更正*
*v0.1 · 2026-05-27 · 初稿,77 场景分类 42✅/7🟡/28⛔,待 Ace 确认 §6 边界判定*
