"""ADR-0019 v0.2: 18 个用户行为驱动 scenarios 生成器.

每个 scenario 戳一个**用户行为模式**, 验证算法是否捕捉产品意图.
不验证 "维度×band" 矩阵, 不验证 matched_pattern 细节.
关心: 算法在该用户行为下**输出是否符合产品意图**.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"
SCENARIO_DIR.mkdir(exist_ok=True)

SCENARIOS: list[dict] = []


def add(**spec):
    # ADR-0019 v0.5: 默认 test_type=robustness (Ace 拍板: e2e 主要测鲁棒性, 红线在单测里)
    spec.setdefault("test_type", "robustness")
    SCENARIOS.append(spec)


# ═══════════════════════════════════════════════════════════════
# 18 个用户行为驱动 scenarios (跨 3 persona)
# ═══════════════════════════════════════════════════════════════

# ─── 老人 (5 个) ─────────────────────────────────────────────

add(
    file="A1_zhang_insurance_burst",
    name="A.1 张奶奶保险式重复拍 3 张同物 30 秒内",
    persona="laoqi_zhang", behavior_pattern="A.1", test_path="L2",
    product_intent="3 张同物体不应被错误升 strong, 算法应识别为保险拍而非真 burst",
    input={"new_photos": ["z02", "z03", "z04"]},
    expected={},                                # 不强求具体, 关心 invariants
    invariants=["INV-01"],
    notes="3 张白兰花特写, 同 30 秒内. 期望: 不被识别为强信号成集",
)

add(
    file="A2_zhang_weekly_park_walk",
    name="A.2 张奶奶周期性散步 跨 4 周 8 张",
    persona="laoqi_zhang", behavior_pattern="A.2", test_path="L2",
    product_intent="跨多周同地同主题不应强行聚一集, 应是周期记录",
    input={"new_photos": ["z07", "z09", "z14", "z17", "z22", "z26", "z31", "z36"]},
    expected={},
    invariants=["INV-01"],
    notes="跨 4 周 8 张, time T3 多日 + theme 一致. 看算法是否拢成一集 vs 散沙",
)

add(
    file="A4_zhang_granddaughter_grab",
    name="A.4 张奶奶被孙女抢手机自拍 3 张突变",
    persona="laoqi_zhang", behavior_pattern="A.4", test_path="L2.5",
    product_intent="孙女自拍突变 vs 阳台花相册, 应 no_merge (主题完全无关)",
    input={"new_photo": "z11", "old_albums": ["granddaughter_album"]},
    expected={"decision_tier": "ask_user"},     # 高频地点降档 auto→ask_user (HR-POST-03)
    invariants=["INV-01"],
    notes="孙女自拍应进 granddaughter_album (people + theme 都强匹配)",
)

add(
    file="A5_zhang_shopping_subzone",
    name="A.5 张奶奶商场反复来回 6 张子区域",
    persona="laoqi_zhang", behavior_pattern="A.5", test_path="L2",
    product_intent="商场内不同子区域反复来回, 应被聚成一集 (子区域内不应散沙)",
    input={"new_photos": ["z18", "z19", "z21", "z23", "z24", "z27"]},
    expected={},
    invariants=["INV-01"],
    notes="同一商场 1F-3F-1F-4F, theme 各不同但 GPS 同. 看 location 是否能拢起来",
)

add(
    file="A6_zhang_plant_growth_30d",
    name="A.6 张奶奶跟踪植物生长 30 天 8 张",
    persona="laoqi_zhang", behavior_pattern="A.6", test_path="L2",
    product_intent="跟踪 1 盆牡丹 30 天日记, 应识别为持续记录 (跨长时同主题)",
    input={"new_photos": ["z01", "z05", "z10", "z15", "z20", "z25", "z29", "z32"]},
    expected={},
    invariants=["INV-01"],
    notes="同盆牡丹从花苞到凋零再到新生, time 跨 30+ 天 + theme 一致 + location 同 (高频). 看算法判断",
)

# ─── 中年 (6 个) ─────────────────────────────────────────────

add(
    file="B1_li_burst_plus_one",
    name="B.1 李叔叔兵马俑爆拍 12 张 + 顺路加油 1 张",
    persona="laoli_youke", behavior_pattern="B.1", test_path="L2",
    product_intent="顺路那张加油站不应被错聚到兵马俑集, 应单独沉淀",
    input={"new_photos": ["l13","l14","l15","l16","l17","l18","l19","l20","l21","l22","l23","l24","l25"]},
    expected={},
    invariants=["INV-01"],
    notes="12 张兵马俑应成集 + 1 张加油站应被识别为长尾",
)

add(
    file="B2_li_xihu_overnight",
    name="B.2 李叔叔跨业务日西湖夜游 6 张 (22:00 → 02:00)",
    persona="laoli_youke", behavior_pattern="B.2", test_path="L2",
    product_intent="跨 04:00 业务日边界不应切碎, 同一段连续夜游应聚成一集",
    input={"new_photos": ["l01", "l02", "l03", "l04", "l05", "l06"]},
    expected={},
    invariants=["INV-01"],
    notes="time 跨 4 小时, 跨 04:00 边界. 看 ADR-0011 业务日识别",
)

add(
    file="B3_li_one_day_long_break",
    name="B.3 李叔叔同一天中场长停顿 5 张 (上午+午饭休+下午)",
    persona="laoli_youke", behavior_pattern="B.3", test_path="L2",
    product_intent="2-3 小时午饭间断不应切集, 同一天 outing 应整体成集",
    input={"new_photos": ["l39", "l40", "l41", "l42", "l43"]},
    expected={},
    invariants=["INV-01"],
    notes="9:00 → 13:00 餐 → 17:00, 时间链式切分 gap=120min 边界",
)

add(
    file="B5_li_business_plus_travel",
    name="B.5 李叔叔上海开会 + 苏州周末 6 张 (event 切换)",
    persona="laoli_youke", behavior_pattern="B.5", test_path="L2",
    product_intent="工作 + 旅游 mix, 不应混成单一相册 (event 维度需要拆)",
    input={"new_photos": ["l07", "l08", "l09", "l10", "l11", "l12"]},
    expected={},
    invariants=["INV-01"],
    notes="3 张 work + 3 张 outing, event 分布异质",
)

add(
    file="B6_li_airport_farewell",
    name="B.6 李叔叔送女儿机场 + 回程 8 张",
    persona="laoli_youke", behavior_pattern="B.6", test_path="L2",
    product_intent="机场 5 + 地铁 3, 同一段送行行程应被识别 (即使分两个 location)",
    input={"new_photos": ["l26","l27","l28","l29","l30","l31","l32","l33"]},
    expected={},
    invariants=["INV-01"],
    notes="event=gathering+outing+daily_record 混合, theme 跨 airport/metro/home",
)

add(
    file="B7_li_pick_grandkid_routine",
    name="B.7 李叔叔接外孙女 5 天连续高频时间地点",
    persona="laoli_youke", behavior_pattern="B.7", test_path="L2",
    product_intent="每天同一时间同一地点接娃, 不应单独成集 (高频地点 + 例行)",
    input={"new_photos": ["l34", "l35", "l36", "l37", "l38"]},
    expected={},
    invariants=["INV-03"],
    notes="5 天每天 15:30 学校门口, 极高频. HR-POST-03 应阻断",
)

# ─── 年轻人 (5 个) ─────────────────────────────────────────────

add(
    file="C3_xiaowang_photo_wall",
    name="C.3 小王网红打卡墙 30 秒 4 人同墙",
    persona="xiaowang", behavior_pattern="C.3", test_path="L2",
    product_intent="同一面墙不同人打卡, 应识别为集体打卡而非误聚",
    input={"new_photos": ["w27", "w28", "w29", "w30"]},
    expected={},
    invariants=["INV-01"],
    notes="同 GPS + 30 秒 + theme 一致 (pink wall), people 多次切换",
)

add(
    file="C4_xiaowang_steak_5_angles",
    name="C.4 小王餐厅一道菜 5 角度 60 秒",
    persona="xiaowang", behavior_pattern="C.4", test_path="L2",
    product_intent="同一道牛排 5 角度近相同照, 不应被 K_outer 散沙误判 + 不应升 burst strong",
    input={"new_photos": ["w22", "w23", "w24", "w25", "w26"]},
    expected={},
    invariants=["INV-01"],
    notes="同 GPS 同 event 60 秒, theme 高度同质. 看算法是否聚成 / 散沙",
)

add(
    file="C6_xiaowang_hike_gps_drift",
    name="C.6 小王山区徒步 GPS 漂移 ±150m 5 张",
    persona="xiaowang", behavior_pattern="C.6", test_path="L2",
    product_intent="GPS 漂移大但 theme 一致 (hike), 不应因 GPS 散沙就放弃成集",
    input={"new_photos": ["w17", "w18", "w19", "w20", "w21"]},
    expected={},
    invariants=["INV-01"],
    notes="GPS 飘 ±150m, eps_inner=500m 边界. 看 theme/event 是否兜底",
)

add(
    file="C7_xiaowang_concert_burst",
    name="C.7 小王演唱会 1 分钟 8 张连拍",
    persona="xiaowang", behavior_pattern="C.7", test_path="L2",
    product_intent="1 分钟内 8 张演唱会, T1.5 events∈[3,5] 升 strong 触发 / activity 二次门槛是否过滤",
    input={"new_photos": ["w01", "w02", "w03", "w04", "w05", "w06", "w07", "w08"]},
    expected={},
    invariants=["INV-01"],
    notes="event=performance, 60 秒内 8 张. T1.5 → strong + activity ≥ 2/3?",
)

add(
    file="C8_xiaowang_cafe_multi_subject",
    name="C.8 小王咖啡馆 5 咖啡 + 3 朋友合影 (同地不同主体)",
    persona="xiaowang", behavior_pattern="C.8", test_path="L2",
    product_intent="同一咖啡馆但 2 个不同主体 (咖啡 vs 朋友), 多维度博弈应拆集",
    input={"new_photos": ["w09","w10","w11","w12","w13","w14","w15","w16"]},
    expected={},
    invariants=["INV-01"],
    notes="同 GPS + event=meal/gathering 混 + theme cafe/friend 主体切换",
)

# ─── 通用 (2 个) ──────────────────────────────────────────────

add(
    file="D1_zhang_screenshot_in_gathering",
    name="D.1 张奶奶聚餐 3 张 + 微信截图 2 张穿插",
    persona="laoqi_zhang", behavior_pattern="D.1", test_path="L2",
    product_intent="截图应被识别为非记忆型, 不应污染聚餐成集",
    input={"new_photos": ["z08", "z16", "z28", "z30", "z33"]},
    expected={},
    invariants=["INV-01"],
    notes="3 张聚餐 (event=meal) + 2 张 wechat/recipe 截图. 看算法是否过滤截图",
)

add(
    file="D2_zhang_hospital_sensitive",
    name="D.2 张奶奶体检医院 3 张 (sensitive_level=medium)",
    persona="laoqi_zhang", behavior_pattern="D.2", test_path="L2",
    test_type="red_line",                     # 红线 #6 基础校验
    product_intent="敏感照片 sensitive_level≥medium, 即使其他维度都强, 也强 suppress",
    input={"new_photos": ["z34", "z35", "z37"]},
    expected={"display_decision": "suppress"},
    invariants=["INV-02"],
    notes="HR-PRE-02 敏感照片强制 suppress (红线 #6)",
)

add(
    file="D9_zhang_high_freq_strong_event",
    name="D.9 张奶奶家生日 6 张 (高频地点 + 强 celebration 不应被过度抑制)",
    persona="laoqi_zhang", behavior_pattern="D.9", test_path="L2",
    product_intent="家 (高频) 办生日 (强 event), HR-POST-03 不应过度抑制 → 应该成集",
    input={"new_photos": ["z38", "z39", "z40", "z41", "z42", "z43"]},
    expected={"display_decision": "show_mini_album"},
    invariants=[],
    notes="高频地点 + event=celebration strong. HR-POST-03 边界, 真生日应成集",
)

# ═══════════════════════════════════════════════════════════════
# ADR-0019 v0.3 旅游分布场景 (10 个)
# ═══════════════════════════════════════════════════════════════

add(
    file="T1_li_xihu_loop_15km",
    name="#1 李叔叔环西湖闭环 15km 8 张",
    persona="laoli_youke", behavior_pattern="T.1", test_path="L2",
    product_intent="环湖闭环: 首尾近 200m 但中间 15km 跨度, DBSCAN 不应把环切成多个簇",
    input={"new_photos": ["l51", "l52", "l53", "l54", "l55", "l56", "l57", "l58"]},
    expected={},
    invariants=["INV-01"],
    notes="闭环识别: 起点终点 GPS 接近, 但中间 15km, time 3-4 小时连续",
)

add(
    file="T3_li_pedestrian_street_uneven",
    name="#3 李叔叔步行街密度不均 6 张 (3 密 + 3 稀)",
    persona="laoli_youke", behavior_pattern="T.3", test_path="L2",
    product_intent="步行街内密度不均: 网红店 3 张密集 (3 分钟) + 普通段 3 张稀疏, DBSCAN eps 难适配",
    input={"new_photos": ["l59", "l60", "l61", "l62", "l63", "l64"]},
    expected={},
    invariants=["INV-01"],
    notes="高楼漂移 + 密度不均",
)

add(
    file="T7_li_around_landmark_small_loop",
    name="#7 李叔叔绕东方明珠小环 6 张",
    persona="laoli_youke", behavior_pattern="T.7", test_path="L2",
    product_intent="绕主体小环: GPS 形成小范围闭环, 主体一致 (theme strong) 应压过 location 小波动",
    input={"new_photos": ["l65", "l66", "l67", "l68", "l69", "l70"]},
    expected={},
    invariants=["INV-01"],
    notes="theme=oriental_pearl 是 strong, 即使 GPS 在 100m 范围有小环",
)

add(
    file="T12_li_one_day_multi_spot_70km",
    name="#12 李叔叔一日游 故宫+长城+鸟巢 6 张跨 70km",
    persona="laoli_youke", behavior_pattern="T.12", test_path="L2",
    product_intent="分散多点一日游: 3 个景点跨 70km, time 跨 10 小时, 应识别为同一行程或拆 3 集",
    input={"new_photos": ["l71", "l72", "l73", "l74", "l75", "l76"]},
    expected={},
    invariants=["INV-01"],
    notes="跨 70km, 点间长途移动. 嵌套容器问题, 现 demo 没实现父 POI",
)

add(
    file="T19_li_marathon_10_spots",
    name="#19 李叔叔暴走 10 景点 高频切换",
    persona="laoli_youke", behavior_pattern="T.19", test_path="L2",
    product_intent="一天 10 个景点高频切换, 不应被切成 10 个碎集, 应识别为 city tour 整体",
    input={"new_photos": ["l77", "l78", "l79", "l80", "l81", "l82", "l83", "l84", "l85", "l86"]},
    expected={},
    invariants=["INV-01"],
    notes="高频切换防过度切分, theme=city_tour 一致",
)

add(
    file="T20_li_resort_lazy_3days",
    name="#20 李叔叔度假村躺平 3 天 GPS 全程同 5 张",
    persona="laoli_youke", behavior_pattern="T.20", test_path="L2",
    product_intent="度假村 3 天 GPS 不变 + 时间稀疏, vs 高频地点核心区分: 应识别为'度假'(非高频)而非'家'(高频), HR-POST-03 不阻断",
    input={"new_photos": ["l87", "l88", "l89", "l90", "l91"]},
    expected={},
    invariants=["INV-01"],
    notes="GPS 三亚 (非用户家城市), hf=false, time T3 多日. 度假成集 vs 家不成集",
)

add(
    file="T4_xiaowang_hike_sparse_dense",
    name="#4 小王徒步前疏后密 4 张",
    persona="xiaowang", behavior_pattern="T.4", test_path="L2",
    product_intent="徒步登山前段稀疏 (2 张) + 山顶密集 (2 张), 时间密度前后差异极大, 前段不应被 sparse 踢掉",
    input={"new_photos": ["w31", "w32", "w33", "w34"]},
    expected={},
    invariants=["INV-01"],
    notes="ADR-0011 time T1 events∈[3,5] 边界, 前疏后密",
)

add(
    file="T13_xiaowang_citywalk_uniform_low",
    name="#13 小王 Citywalk 低密度均匀 6 张",
    persona="xiaowang", behavior_pattern="T.13", test_path="L2",
    product_intent="低密度均匀分布 (5km 6 张, 平均 800m/张), DBSCAN 死穴, theme=citywalk 一致兜底",
    input={"new_photos": ["w35", "w36", "w37", "w38", "w39", "w40"]},
    expected={},
    invariants=["INV-01"],
    notes="无密集簇 + theme 一致, 看算法靠 theme 还是放弃",
)

add(
    file="T15_xiaowang_fireworks_newyear",
    name="#15 小王跨年烟花 8 张 10 分钟跨业务日",
    persona="xiaowang", behavior_pattern="T.15", test_path="L2",
    product_intent="跨年烟花: 10 分钟内 8 张同主题, 跨 04:00 业务日 vs 跨自然日 (00:00) 不同语义, ADR-0011 自然日归属",
    input={"new_photos": ["w41", "w42", "w43", "w44", "w45", "w46", "w47", "w48"]},
    expected={},
    invariants=["INV-01"],
    notes="time 极密 (T1.5 events>5) + 跨 00:00 (但 < 04:00 同业务日)",
)

add(
    file="T18_xiaowang_checkin_multi_spot",
    name="#18 小王网红打卡跨城 5 个点 5 张",
    persona="xiaowang", behavior_pattern="T.18", test_path="L2",
    product_intent="跨城网红打卡 5 个点各 1 张, 跨 5km, 每点信息密度低, 应识别为 city checkin 而非分散沉淀",
    input={"new_photos": ["w49", "w50", "w51", "w52", "w53"]},
    expected={},
    invariants=["INV-01"],
    notes="每点 1 张, theme 各不同, location 跨城. 单点信息密度低 + 点间无关联",
)

# ═══════════════════════════════════════════════════════════════
# ADR-0019 v0.4 补漏 scenarios (6 个)
# ═══════════════════════════════════════════════════════════════

add(
    file="T21_xiaowang_burst_plus_gap",
    name="T.21 小王连拍+长间隔 5 张 1s + 1 张 30min 后",
    persona="xiaowang", behavior_pattern="T.21", test_path="L2",
    product_intent="ADR-0011 time T1 链式切分: 5 张连拍紧凑 + 1 张 30min 跳跃, gap > 120min 切边界",
    input={"new_photos": ["w54", "w55", "w56", "w57", "w58", "w59"]},
    expected={},
    invariants=["INV-01"],
    notes="time 维度: 看是否切成 2 集 / 同 1 集",
)

add(
    file="T22_li_camping_crossday_event",
    name="T.22 李叔叔周末露营跨自然日同事件 6 张",
    persona="laoli_youke", behavior_pattern="T.22", test_path="L2",
    product_intent="跨多个 04:00 业务日同事件 (4/26 12:00 - 4/27 18:00 连续露营), ADR-0011 T2/T3 多日识别",
    input={"new_photos": ["l92", "l93", "l94", "l95", "l96", "l97"]},
    expected={},
    invariants=["INV-01"],
    notes="跨 2 个 04:00, 连续时间, theme 一致 (camping)",
)

add(
    file="TH1_li_theme_granularity_mix",
    name="TH.1 李叔叔 theme 颗粒度混合 4 张 (粗/中/细/感官)",
    persona="laoli_youke", behavior_pattern="TH.1", test_path="L2",
    product_intent="同地点不同颗粒度 theme 标签, 字面 Jaccard ≈ 0 但 ADR-0008 语义簇应识别都是'西湖'",
    input={"new_photos": ["l98", "l99", "l100", "l101"]},
    expected={},
    invariants=["INV-01"],
    notes="测语义簇能力 vs 字面 Jaccard 死穴",
)

add(
    file="TH2_xiaowang_multi_strong_theme",
    name="TH.2 小王单图多 strong theme 3 张 (万圣节+晚宴+生日)",
    persona="xiaowang", behavior_pattern="TH.2", test_path="L2",
    product_intent="单图 theme 多元素 (≥5 标签), ADR-0013 双层判定能否处理 'theme 多焦点'",
    input={"new_photos": ["w60", "w61", "w62"]},
    expected={},
    invariants=["INV-01"],
    notes="多 strong theme 共存, 算法选哪个主导",
)

add(
    file="ANC1_li_anchor_multi_granularity",
    name="ANC.1 李叔叔 anchor 多颗粒 3 张 (meaning 抽象 + object 具体)",
    persona="laoli_youke", behavior_pattern="ANC.1", test_path="L2",
    product_intent="meaning_anchors 4+ 个抽象 + main_subjects 4+ 个具体, ADR-0014 双层 anchor 边界",
    input={"new_photos": ["l102", "l103", "l104"]},
    expected={},
    invariants=["INV-01"],
    notes="anchor 多颗粒强叠加, 看真值表 A 系 (anchor 不主导但加强)",
)

add(
    file="EV1_zhang_event_signal_conflict",
    name="EV.1 张奶奶餐厅周年庆 event 多信号冲突 3 张",
    persona="laoqi_zhang", behavior_pattern="EV.1", test_path="L2",
    product_intent="event=celebration + activity=meal + scene=restaurant 多维冲突, ADR-0012 primary_share 怎么判",
    input={"new_photos": ["z44", "z45", "z46"]},
    expected={},
    invariants=["INV-01"],
    notes="event 单值 celebration 一致, activity 和 scene 也一致但不是 celebration. 多信号冲突",
)


# ═══════════════════════════════════════════════════════════════
# ADR-0019 v0.5 · Phase 1: L2.5 单张 14 个 scenarios
# ═══════════════════════════════════════════════════════════════

# ─── 老人 3 个 ───
add(file="L25_R1_zhang_balcony_to_walk_no_merge",
    name="L2.5 #R1 张奶奶阳台花 vs 公园散步相册 → no_merge (跨场景反例)",
    persona="laoqi_zhang", behavior_pattern="L25.R1", test_path="L2.5",
    test_type="red_line",
    product_intent="阳台花 vs 公园相册 主题不同地点不同, 基础反例 no_merge",
    input={"new_photo": "z01", "old_albums": ["weekly_park_walk_album"]},
    expected={"decision_tier": "no_merge"},
    invariants=["INV-01"],
    notes="基础跨场景反例")

add(file="L25_R2_zhang_walk_to_walk_auto_merge",
    name="L2.5 #R2 张奶奶公园晨练 vs 公园相册 → auto_merge (基础正例)",
    persona="laoqi_zhang", behavior_pattern="L25.R2", test_path="L2.5",
    test_type="red_line",
    product_intent="同地点同主题, 基础正例应 auto_merge",
    input={"new_photo": "z07", "old_albums": ["weekly_park_walk_album"]},
    expected={"decision_tier": "auto_merge"},
    invariants=["INV-01"],
    notes="基础正例")

add(file="L25_zhang_distractor_screenshot_to_walk",
    name="L2.5 张奶奶截图干扰 vs 公园相册 → no_merge",
    persona="laoqi_zhang", behavior_pattern="L25.distractor", test_path="L2.5",
    test_type="robustness",
    product_intent="截图非记忆型干扰, 应 no_merge",
    input={"new_photo": "z30", "old_albums": ["weekly_park_walk_album"]},
    expected={"decision_tier": "no_merge"},
    invariants=["INV-01"],
    notes="干扰反例")

# ─── 中年 3 个 ───
add(file="L25_R3_li_xihu_new_to_xihu_auto",
    name="L2.5 #R3 李叔叔西湖新照 (粗颗粒) vs 西湖相册 → auto_merge (基础正例)",
    persona="laoli_youke", behavior_pattern="L25.R3", test_path="L2.5",
    test_type="red_line",
    product_intent="新西湖照 vs 西湖相册, 同地点同主题, 应 auto_merge (theme 颗粒度粗也能识别)",
    input={"new_photo": "l98", "old_albums": ["past_xihu_album"]},
    expected={"decision_tier": "auto_merge"},
    invariants=["INV-01"],
    notes="基础正例 + 测语义簇")

add(file="L25_R4_li_gugong_to_xihu_no_merge",
    name="L2.5 #R4 李叔叔故宫 vs 西湖相册 → no_merge (跨城反例)",
    persona="laoli_youke", behavior_pattern="L25.R4", test_path="L2.5",
    test_type="red_line",
    product_intent="跨城反例: 故宫 (北京) vs 西湖 (杭州), 即使主题都 ancient 也应 no_merge",
    input={"new_photo": "l42", "old_albums": ["past_xihu_album"]},
    expected={"decision_tier": "no_merge"},
    invariants=["INV-01"],
    notes="基础跨城反例")

add(file="L25_li_pick_grandkid_high_freq",
    name="L2.5 李叔叔接娃 vs 接娃相册 → auto/ask (高频地点)",
    persona="laoli_youke", behavior_pattern="L25.high_freq", test_path="L2.5",
    test_type="robustness",
    product_intent="高频地点 + 日常 routine, HR-POST-03 边界",
    input={"new_photo": "l35", "old_albums": ["pick_grandkid_album"]},
    expected={},
    invariants=["INV-03"],
    notes="高频地点降档 ask_user 或不降")

# ─── 年轻人 1 个 (跨 persona album 误用反例) ───
add(file="L25_xiaowang_concert_to_walk_no_merge",
    name="L2.5 小王演唱会照 vs 张奶奶公园相册 → no_merge (跨用户反例)",
    persona="xiaowang", behavior_pattern="L25.cross_user", test_path="L2.5",
    test_type="robustness",
    product_intent="演唱会照 vs 公园相册 (不同 persona), 主题完全不同, no_merge",
    input={"new_photo": "w01", "old_albums": []},
    expected={"decision_tier": "no_merge"},
    invariants=["INV-01"],
    notes="空 album 列表测试")

# ─── 通用 7 个 ───
add(file="L25_zhang_sensitive_to_any_no_merge",
    name="L2.5 张奶奶医院敏感 vs 公园相册 → no_merge (红线 #6)",
    persona="laoqi_zhang", behavior_pattern="L25.sensitive", test_path="L2.5",
    test_type="red_line",
    product_intent="敏感照片 sensitive_level=medium, 即使其他维度都强, 永远 no_merge (HRG-POST-01)",
    input={"new_photo": "z34", "old_albums": ["weekly_park_walk_album"]},
    expected={"decision_tier": "no_merge"},
    invariants=["INV-02"],
    notes="红线 #6 基础")

add(file="L25_zhang_high_freq_birthday_celebration",
    name="L2.5 张奶奶生日 (家高频) vs 孙女相册 → auto_merge (强 event 不降)",
    persona="laoqi_zhang", behavior_pattern="L25.high_freq_strong_event", test_path="L2.5",
    test_type="robustness",
    product_intent="高频地点 + 强 celebration, HR-POST-03 不过度抑制",
    input={"new_photo": "z38", "old_albums": ["granddaughter_album"]},
    expected={"decision_tier": "auto_merge"},
    invariants=["INV-03"],
    notes="高频地点边界")

add(file="L25_li_camping_to_xihu_no_merge",
    name="L2.5 李叔叔露营 vs 西湖相册 → no_merge (跨主题)",
    persona="laoli_youke", behavior_pattern="L25.cross_theme", test_path="L2.5",
    test_type="robustness",
    product_intent="露营 vs 西湖游, 跨主题应 no_merge",
    input={"new_photo": "l93", "old_albums": ["past_xihu_album"]},
    expected={"decision_tier": "no_merge"},
    invariants=["INV-01"],
    notes="跨主题反例")

add(file="L25_li_multi_anchor_to_xihu",
    name="L2.5 李叔叔多 anchor 照 vs 西湖相册 (anchor 颗粒度边界)",
    persona="laoli_youke", behavior_pattern="L25.multi_anchor", test_path="L2.5",
    test_type="robustness",
    product_intent="新照含 4 个 meaning_anchor + 5 个 object, 同地点应 auto_merge / ask_user",
    input={"new_photo": "l102", "old_albums": ["past_xihu_album"]},
    expected={},
    invariants=["INV-01"],
    notes="anchor 多颗粒边界, 同地 GPS")

add(file="L25_xiaowang_multi_theme_to_walk_no_merge",
    name="L2.5 小王单图多 strong theme (万圣节+生日) vs 张奶奶公园相册 → no_merge",
    persona="xiaowang", behavior_pattern="L25.multi_theme", test_path="L2.5",
    test_type="robustness",
    product_intent="单图多 strong theme + 跨场景, 算法主导 theme 选择",
    input={"new_photo": "w60", "old_albums": []},
    expected={"decision_tier": "no_merge"},
    invariants=["INV-01"],
    notes="多主题 + 空 album 列表")

add(file="L25_li_th_granularity_细颗粒_to_xihu",
    name="L2.5 李叔叔西湖细颗粒标签 vs 西湖相册 (语义簇兜底)",
    persona="laoli_youke", behavior_pattern="L25.th_granularity", test_path="L2.5",
    test_type="robustness",
    product_intent="细颗粒标签 [断桥, 行人, 风筝] 字面 Jaccard=0 但 ADR-0008 语义簇识别 → 应 auto_merge",
    input={"new_photo": "l99", "old_albums": ["past_xihu_album"]},
    expected={"decision_tier": "auto_merge"},
    invariants=["INV-01"],
    notes="语义簇 vs 字面 Jaccard")

add(file="L25_zhang_event_conflict_to_album",
    name="L2.5 张奶奶餐厅周年庆 (event 多信号冲突) vs 孙女相册",
    persona="laoqi_zhang", behavior_pattern="L25.event_conflict", test_path="L2.5",
    test_type="robustness",
    product_intent="event=celebration + activity=meal + scene=restaurant 多信号冲突时, primary event 主导决策",
    input={"new_photo": "z44", "old_albums": ["granddaughter_album"]},
    expected={},
    invariants=["INV-01"],
    notes="多信号冲突边界")


# ═══════════════════════════════════════════════════════════════
# ADR-0019 v0.5 · Phase 2: cascade 单张 15 个 scenarios
# ═══════════════════════════════════════════════════════════════

# ─── 老人 4 个 ───
add(file="C_R1_zhang_balcony_recall_balcony",
    name="cascade #R1 张奶奶阳台花新照 vs 沉淀池 (有阳台花) → create_new_album",
    persona="laoqi_zhang", behavior_pattern="C.R1", test_path="cascade",
    test_type="red_line",
    product_intent="cascade 基础正例: 新照跟池里 4 张同主题, 应 create_new_album",
    input={"new_photo": "z32", "sediment_pool": ["z01", "z03", "z06", "z08"]},
    expected={"decision_tier": "create_new_album"},
    invariants=["INV-01", "INV-04", "INV-05", "INV-06"],
    notes="基础正例")

add(file="C_R2_zhang_empty_pool_insufficient",
    name="cascade #R2 张奶奶单张 vs 空池 → insufficient (基础反例)",
    persona="laoqi_zhang", behavior_pattern="C.R2", test_path="cascade",
    test_type="red_line",
    product_intent="cascade 基础反例: 空池无候选 → insufficient_candidates",
    input={"new_photo": "z32", "sediment_pool": []},
    expected={"decision_tier": "insufficient_candidates"},
    invariants=["INV-04"],
    notes="基础反例")

add(file="C_zhang_screenshot_no_recall",
    name="cascade 张奶奶截图干扰 vs 沉淀池 → no_backfill",
    persona="laoqi_zhang", behavior_pattern="C.distractor", test_path="cascade",
    test_type="robustness",
    product_intent="干扰截图 vs 池, 主题完全无关, no_backfill",
    input={"new_photo": "z30", "sediment_pool": ["z01", "z03", "z06"]},
    expected={"decision_tier": "no_backfill"},
    invariants=["INV-01"],
    notes="干扰反例")

add(file="C_zhang_sensitive_no_recall",
    name="cascade 张奶奶敏感照 vs 沉淀池 → no_backfill (HR-PRE)",
    persona="laoqi_zhang", behavior_pattern="C.sensitive", test_path="cascade",
    test_type="robustness",
    product_intent="敏感照 sensitive_level=medium, HR-PRE 强制 suppress",
    input={"new_photo": "z34", "sediment_pool": ["z01", "z03", "z06"]},
    expected={"decision_tier": "insufficient_candidates"},
    invariants=["INV-02"],
    notes="敏感照 PRE 阻断")

# ─── 中年 5 个 ───
add(file="C_R3_li_xihu_recall_xihu",
    name="cascade #R3 李叔叔西湖新照 vs 沉淀池 (西湖类似) → create_new_album",
    persona="laoli_youke", behavior_pattern="C.R3", test_path="cascade",
    test_type="red_line",
    product_intent="cascade 跨颗粒度: 新中颗粒 vs 池里粗+细+感官混合, 应召回",
    input={"new_photo": "l100", "sediment_pool": ["l51", "l52", "l53", "l54"]},
    expected={"decision_tier": "create_new_album"},
    invariants=["INV-04", "INV-05", "INV-06"],
    notes="基础正例 + 跨颗粒度")

add(file="C_R4_li_gugong_cross_city_no_recall",
    name="cascade #R4 李叔叔故宫 vs 沉淀西湖池 → no_backfill (跨城反例)",
    persona="laoli_youke", behavior_pattern="C.R4", test_path="cascade",
    test_type="red_line",
    product_intent="跨城反例: 新故宫照 vs 池里西湖, 不应误召回",
    input={"new_photo": "l42", "sediment_pool": ["l51", "l52", "l53"]},
    expected={"decision_tier": "no_backfill"},
    invariants=["INV-01"],
    notes="基础跨城反例")

add(file="C_li_overnight_recall",
    name="cascade 李叔叔西湖夜游单张 vs 沉淀夜游 → 召回 (跨业务日)",
    persona="laoli_youke", behavior_pattern="C.overnight", test_path="cascade",
    test_type="robustness",
    product_intent="跨业务日单张 vs 沉淀池同主题, 应召回",
    input={"new_photo": "l05", "sediment_pool": ["l01", "l02", "l03"]},
    expected={},
    invariants=["INV-04", "INV-05"],
    notes="跨业务日召回边界")

add(file="C_li_resort_lazy_empty",
    name="cascade 李叔叔度假村单张 vs 空池 → insufficient",
    persona="laoli_youke", behavior_pattern="C.resort", test_path="cascade",
    test_type="robustness",
    product_intent="度假村单张 vs 空池 → insufficient",
    input={"new_photo": "l87", "sediment_pool": []},
    expected={"decision_tier": "insufficient_candidates"},
    invariants=["INV-04"],
    notes="度假村空池")

add(file="C_li_marathon_no_recall",
    name="cascade 李叔叔暴走单张 vs 沉淀池 (其他暴走) → 看决定",
    persona="laoli_youke", behavior_pattern="C.marathon", test_path="cascade",
    test_type="robustness",
    product_intent="暴走 1 张 vs 池里其他暴走景点, 每点信息密度低",
    input={"new_photo": "l77", "sediment_pool": ["l78", "l79", "l80"]},
    expected={},
    invariants=["INV-01"],
    notes="暴走点信息低边界")

# ─── 年轻人 3 个 ───
add(file="C_xiaowang_concert_no_recall",
    name="cascade 小王演唱会单张 vs 沉淀(无相关) → no_backfill",
    persona="xiaowang", behavior_pattern="C.concert", test_path="cascade",
    test_type="robustness",
    product_intent="演唱会单张 vs 池里无相关, no_backfill",
    input={"new_photo": "w01", "sediment_pool": ["w17", "w18", "w19"]},
    expected={"decision_tier": "no_backfill"},
    invariants=["INV-01"],
    notes="跨主题")

add(file="C_xiaowang_fireworks_no_recall",
    name="cascade 小王跨年烟花单张 vs 沉淀池(无烟花) → no_backfill",
    persona="xiaowang", behavior_pattern="C.fireworks", test_path="cascade",
    test_type="robustness",
    product_intent="烟花单张 vs 池里无相关烟花, no_backfill",
    input={"new_photo": "w44", "sediment_pool": ["w17", "w35", "w49"]},
    expected={"decision_tier": "no_backfill"},
    invariants=["INV-01"],
    notes="跨主题")

add(file="C_xiaowang_checkin_no_recall",
    name="cascade 小王网红打卡单张 vs 沉淀池(其他网红) → 看决定",
    persona="xiaowang", behavior_pattern="C.checkin", test_path="cascade",
    test_type="robustness",
    product_intent="网红打卡单张 vs 池里其他网红点, 每点 1 张, 跨城",
    input={"new_photo": "w49", "sediment_pool": ["w50", "w51", "w52", "w53"]},
    expected={},
    invariants=["INV-01"],
    notes="跨城网红打卡")

# ─── 通用 3 个 ───
add(file="C_R5_zhang_event_conflict_empty",
    name="cascade #R5 张奶奶餐厅周年 (event 冲突) vs 空池 → insufficient",
    persona="laoqi_zhang", behavior_pattern="C.R5", test_path="cascade",
    test_type="red_line",
    product_intent="event 多信号冲突 + 空池 → insufficient",
    input={"new_photo": "z44", "sediment_pool": []},
    expected={"decision_tier": "insufficient_candidates"},
    invariants=["INV-04"],
    notes="基础反例")

add(file="C_li_th_granularity_recall",
    name="cascade 李叔叔西湖感官标签 vs 沉淀池(4 颗粒度西湖) → 语义簇召回",
    persona="laoli_youke", behavior_pattern="C.th_granularity", test_path="cascade",
    test_type="robustness",
    product_intent="新照感官颗粒 vs 池里粗/中/细 + 一张感官, 字面 Jaccard 低, 语义簇兜底",
    input={"new_photo": "l101", "sediment_pool": ["l98", "l99", "l100", "l51"]},
    expected={},
    invariants=["INV-01"],
    notes="语义簇兜底测试")

add(file="C_xiaowang_multi_theme_no_recall",
    name="cascade 小王单图多 strong theme vs 沉淀池(任何) → 看决定",
    persona="xiaowang", behavior_pattern="C.multi_theme", test_path="cascade",
    test_type="robustness",
    product_intent="单图含万圣节+晚宴+生日多 theme vs 池里无相关, 算法主导 theme 选择",
    input={"new_photo": "w60", "sediment_pool": ["w35", "w49", "w50"]},
    expected={"decision_tier": "no_backfill"},
    invariants=["INV-01"],
    notes="多主题 + 跨")


# ═══════════════════════════════════════════════════════════════
# 落盘
# ═══════════════════════════════════════════════════════════════

def main():
    written = 0
    for spec in SCENARIOS:
        fn = spec.pop("file")
        path = SCENARIO_DIR / f"{fn}.yaml"
        path.write_text(
            yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        written += 1
    print(f"OK: Wrote {written} user-behavior-driven scenarios")


if __name__ == "__main__":
    main()
