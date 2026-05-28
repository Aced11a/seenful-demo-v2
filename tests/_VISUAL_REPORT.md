# Persona Scenarios Visual Report (mock mode)

- LLM mode: **mock** (env var `SEENFUL_LLM_MODE`)
- 跑了 64 个 scenarios
- 跑命令: `SEENFUL_LLM_MODE=real DASHSCOPE_API_KEY=xxx python tests/personas/_gen_visual_report.py` 切真

> 每个 case 含: 输入照片 + 7 维 bands + 真值表 + LLM 输出 + Policy 决定 + Invariants 校验

---

# L2 (整批 path B) · 34 个 scenarios

## A1_zhang_insurance_burst

**A.1 张奶奶保险式重复拍 3 张同物 30 秒内**

- Pattern: `A.1` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: 3 张同物体不应被错误升 strong, 算法应识别为保险拍而非真 burst

### 输入照片
- `z02`: orchid, white, closeup
- `z03`: orchid, white, closeup
- `z04`: orchid, white, leaf

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'strong', 'theme': 'strong', 'event': 'strong', 'people': 'none', 'anchor': 'strong', 'emotional': 'strong'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `z02`: 白兰花特写一, 这是一张普通的生活照片, 记录了当时的情景。白兰花特写一, 这是一张普通的生活照片, 记录了当时的情景。
    - `z03`: 白兰花特写二, 这是一张普通的生活照片, 记录了当时的情景。白兰花特写二, 这是一张普通的生活照片, 记录了当时的情景。
    - `z04`: 白兰花特写三 拍清, 这是一张普通的生活照片, 记录了当时的情景。白兰花特写三 拍清, 这是一张普通的生活照片, 记录了…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.785
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## A2_zhang_weekly_park_walk

**A.2 张奶奶周期性散步 跨 4 周 8 张**

- Pattern: `A.2` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: 跨多周同地同主题不应强行聚一集, 应是周期记录

### 输入照片
- `z07`: garden, morning, walk
- `z09`: garden, magnolia, blossom
- `z14`: garden, pond, koi
- `z17`: garden, pavilion, rest
- `z22`: garden, rose, fragrance
- `z26`: garden, neighbor, chat
- `z31`: garden, summer, bench
- `z36`: garden, lotus_pond, lily

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'weak', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'weak'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `z07`: 周一晨练花园, 这是一张普通的生活照片, 记录了当时的情景。周一晨练花园, 这是一张普通的生活照片, 记录了当时的情景。
    - `z09`: 玉兰开了, 这是一张普通的生活照片, 记录了当时的情景。玉兰开了, 这是一张普通的生活照片, 记录了当时的情景。
    - `z14`: 池塘锦鲤, 这是一张普通的生活照片, 记录了当时的情景。池塘锦鲤, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.600
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## A5_zhang_shopping_subzone

**A.5 张奶奶商场反复来回 6 张子区域**

- Pattern: `A.5` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: 商场内不同子区域反复来回, 应被聚成一集 (子区域内不应散沙)

### 输入照片
- `z18`: mall, 1f, supermarket
- `z19`: mall, 3f, clothes
- `z21`: mall, 3f, tea
- `z23`: mall, 1f, food_court
- `z24`: mall, 4f, bookstore
- `z27`: mall, 1f, exit

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'weak'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `z18`: 商场 1F 超市, 这是一张普通的生活照片, 记录了当时的情景。商场 1F 超市, 这是一张普通的生活照片, 记录了当时…
    - `z19`: 3F 服装店, 这是一张普通的生活照片, 记录了当时的情景。3F 服装店, 这是一张普通的生活照片, 记录了当时的情景。
    - `z21`: 3F 茶具店, 这是一张普通的生活照片, 记录了当时的情景。3F 茶具店, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.700
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## A6_zhang_plant_growth_30d

**A.6 张奶奶跟踪植物生长 30 天 8 张**

- Pattern: `A.6` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: 跟踪 1 盆牡丹 30 天日记, 应识别为持续记录 (跨长时同主题)

### 输入照片
- `z01`: peony, bud, balcony
- `z05`: peony, half_bloom, pink
- `z10`: peony, full_bloom, pink
- `z15`: peony, fading, petals
- `z20`: peony, fallen, ground
- `z25`: peony, new_leaf, recovery
- `z29`: peony, lush, leaves
- `z32`: peony, second_bud, hope

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'weak', 'theme': 'strong', 'event': 'strong', 'people': 'none', 'anchor': 'weak', 'emotional': 'weak'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `z01`: 牡丹花苞初露, 这是一张普通的生活照片, 记录了当时的情景。牡丹花苞初露, 这是一张普通的生活照片, 记录了当时的情景。
    - `z05`: 牡丹半开, 这是一张普通的生活照片, 记录了当时的情景。牡丹半开, 这是一张普通的生活照片, 记录了当时的情景。
    - `z10`: 牡丹盛开, 这是一张普通的生活照片, 记录了当时的情景。牡丹盛开, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.585
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## ANC1_li_anchor_multi_granularity

**ANC.1 李叔叔 anchor 多颗粒 3 张 (meaning 抽象 + object 具体)**

- Pattern: `ANC.1` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: meaning_anchors 4+ 个抽象 + main_subjects 4+ 个具体, ADR-0014 双层 anchor 边界

### 输入照片
- `l102`: bridge, garden, walk
- `l103`: pavilion, ancient, tree
- `l104`: water, koi, peace

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'weak', 'event': 'strong', 'people': 'none', 'anchor': 'strong', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `l102`: 多 anchor 1 (4 抽象 meaning), 这是一张普通的生活照片, 记录了当时的情景。多 anchor 1 …
    - `l103`: 多 anchor 2 (5 个混合), 这是一张普通的生活照片, 记录了当时的情景。多 anchor 2 (5 个混合)…
    - `l104`: 多 anchor 3 (object 4 个), 这是一张普通的生活照片, 记录了当时的情景。多 anchor 3 (o…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.735
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## B1_li_burst_plus_one

**B.1 李叔叔兵马俑爆拍 12 张 + 顺路加油 1 张**

- Pattern: `B.1` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 顺路那张加油站不应被错聚到兵马俑集, 应单独沉淀

### 输入照片
- `l13`: terracotta, warrior, pit
- `l14`: terracotta, warrior, closeup
- `l15`: terracotta, horse_chariot
- `l16`: terracotta, kneeling_archer
- `l17`: terracotta, general, statue
- `l18`: terracotta, museum_hall, scale
- `l19`: terracotta, fragment, restore
- `l20`: terracotta, gift_shop, souvenir
- `l21`: terracotta, courtyard, ancient
- `l22`: terracotta, color_remnant
- `l23`: terracotta, pit_overview
- `l24`: terracotta, exit, ticket
- `l25`: gas_station, snack, roadside

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'weak', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `l13`: 兵马俑一号坑震撼, 这是一张普通的生活照片, 记录了当时的情景。兵马俑一号坑震撼, 这是一张普通的生活照片, 记录了当时…
    - `l14`: 兵马俑面部特写, 这是一张普通的生活照片, 记录了当时的情景。兵马俑面部特写, 这是一张普通的生活照片, 记录了当时的情…
    - `l15`: 铜车马, 这是一张普通的生活照片, 记录了当时的情景。铜车马, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.655
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## B2_li_xihu_overnight

**B.2 李叔叔跨业务日西湖夜游 6 张 (22:00 → 02:00)**

- Pattern: `B.2` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 跨 04:00 业务日边界不应切碎, 同一段连续夜游应聚成一集

### 输入照片
- `l01`: xihu, night, lake_view
- `l02`: xihu, music_fountain, lights
- `l03`: xihu, tea_house, midnight
- `l04`: xihu, midnight, calm
- `l05`: xihu, moonlight, bridge
- `l06`: xihu, departure, dawn_haze

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `l01`: 西湖夜晚到达, 这是一张普通的生活照片, 记录了当时的情景。西湖夜晚到达, 这是一张普通的生活照片, 记录了当时的情景。
    - `l02`: 音乐喷泉, 这是一张普通的生活照片, 记录了当时的情景。音乐喷泉, 这是一张普通的生活照片, 记录了当时的情景。
    - `l03`: 西湖边茶馆夜话, 这是一张普通的生活照片, 记录了当时的情景。西湖边茶馆夜话, 这是一张普通的生活照片, 记录了当时的情…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.685
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## B3_li_one_day_long_break

**B.3 李叔叔同一天中场长停顿 5 张 (上午+午饭休+下午)**

- Pattern: `B.3` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 2-3 小时午饭间断不应切集, 同一天 outing 应整体成集

### 输入照片
- `l39`: mountain, dawn, peak
- `l40`: mountain, trail, hike
- `l41`: mountain_restaurant, lunch, soup
- `l42`: mountain, valley, afternoon
- `l43`: mountain, sunset, peak

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'strong', 'theme': 'weak', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'weak'}
- 真值表: `B2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: event
  - semantic_reason: mock:B2
  - evidence (3):
    - `l39`: 张家界清晨山顶, 这是一张普通的生活照片, 记录了当时的情景。张家界清晨山顶, 这是一张普通的生活照片, 记录了当时的情…
    - `l40`: 山间步道, 这是一张普通的生活照片, 记录了当时的情景。山间步道, 这是一张普通的生活照片, 记录了当时的情景。
    - `l41`: 山下午饭, 这是一张普通的生活照片, 记录了当时的情景。山下午饭, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **event**
- display_decision: **show_mini_album**
- composite_score: 0.580
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## B5_li_business_plus_travel

**B.5 李叔叔上海开会 + 苏州周末 6 张 (event 切换)**

- Pattern: `B.5` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 工作 + 旅游 mix, 不应混成单一相册 (event 维度需要拆)

### 输入照片
- `l07`: work, conference, badge
- `l08`: work, presentation, screen
- `l09`: work, dinner, business
- `l10`: zhuozheng, garden, ancient
- `l11`: zhuozheng, lotus, pond
- `l12`: suzhou, snack, street

### 算法行为
- 7 维 bands: {'location': 'none', 'time': 'weak', 'theme': 'weak', 'event': 'weak', 'people': 'none', 'anchor': 'weak', 'emotional': 'weak'}
- 真值表: `F1` · bounds=[none, none]
- **LLM 跳过** (F1 兜底)

### Policy Engine 最终
- final_strength: **none**
- final_type: **weak**
- display_decision: **suppress**
- composite_score: 0.095
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## B6_li_airport_farewell

**B.6 李叔叔送女儿机场 + 回程 8 张**

- Pattern: `B.6` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 机场 5 + 地铁 3, 同一段送行行程应被识别 (即使分两个 location)

### 输入照片
- `l26`: airport, departure_hall, luggage
- `l27`: airport, hug, farewell
- `l28`: airport, security_gate, wave
- `l29`: airport, window, plane
- `l30`: airport, exit, sign
- `l31`: metro, return, indoor
- `l32`: metro, window, neighborhood
- `l33`: home, empty_room, light

### 算法行为
- 7 维 bands: {'location': 'none', 'time': 'strong', 'theme': 'weak', 'event': 'weak', 'people': 'weak', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `G2` · bounds=[light, medium]
- **LLM 输出**:
  - proposed_strength: weak
  - proposed_type: temporal
  - semantic_reason: mock:G2
  - evidence (3):
    - `l26`: 浦东机场出发厅, 这是一张普通的生活照片, 记录了当时的情景。浦东机场出发厅, 这是一张普通的生活照片, 记录了当时的情…
    - `l27`: 跟女儿拥抱, 这是一张普通的生活照片, 记录了当时的情景。跟女儿拥抱, 这是一张普通的生活照片, 记录了当时的情景。
    - `l28`: 安检口挥手, 这是一张普通的生活照片, 记录了当时的情景。安检口挥手, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **weak**
- final_type: **temporal**
- display_decision: **show_inline_hint**
- composite_score: 0.420
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## B7_li_pick_grandkid_routine

**B.7 李叔叔接外孙女 5 天连续高频时间地点**

- Pattern: `B.7` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 每天同一时间同一地点接娃, 不应单独成集 (高频地点 + 例行)

### 输入照片
- `l34`: school_gate, waiting, sign
- `l35`: school_gate, grandkid, smile
- `l36`: school_gate, snack, after_school
- `l37`: school_gate, monday, routine
- `l38`: school_gate, rainy_day, umbrella

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'weak', 'theme': 'strong', 'event': 'strong', 'people': 'weak', 'anchor': 'strong', 'emotional': 'strong'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `l34`: 学校门口等, 这是一张普通的生活照片, 记录了当时的情景。学校门口等, 这是一张普通的生活照片, 记录了当时的情景。
    - `l35`: 外孙女出校门, 这是一张普通的生活照片, 记录了当时的情景。外孙女出校门, 这是一张普通的生活照片, 记录了当时的情景。
    - `l36`: 放学买零食, 这是一张普通的生活照片, 记录了当时的情景。放学买零食, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.730
- policy_overrides: 0

### ✅ Invariants 全过 (INV-03)

---

## C3_xiaowang_photo_wall

**C.3 小王网红打卡墙 30 秒 4 人同墙**

- Pattern: `C.3` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 同一面墙不同人打卡, 应识别为集体打卡而非误聚

### 输入照片
- `w27`: photo_wall, pink, pose
- `w28`: photo_wall, pink, jump
- `w29`: photo_wall, pink, victory
- `w30`: photo_wall, pink, group

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'strong', 'people': 'weak', 'anchor': 'none', 'emotional': 'strong'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w27`: 朋友 A 打卡, 这是一张普通的生活照片, 记录了当时的情景。朋友 A 打卡, 这是一张普通的生活照片, 记录了当时的情…
    - `w28`: 朋友 B 打卡, 这是一张普通的生活照片, 记录了当时的情景。朋友 B 打卡, 这是一张普通的生活照片, 记录了当时的情…
    - `w29`: 朋友 C 打卡, 这是一张普通的生活照片, 记录了当时的情景。朋友 C 打卡, 这是一张普通的生活照片, 记录了当时的情…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.795
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## C4_xiaowang_steak_5_angles

**C.4 小王餐厅一道菜 5 角度 60 秒**

- Pattern: `C.4` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 同一道牛排 5 角度近相同照, 不应被 K_outer 散沙误判 + 不应升 burst strong

### 输入照片
- `w22`: steak, top_view, plate
- `w23`: steak, side_view, fork
- `w24`: steak, closeup, texture
- `w25`: steak, half_eaten, fork
- `w26`: steak, sauce, drip

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'strong', 'people': 'none', 'anchor': 'none', 'emotional': 'strong'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w22`: 牛排俯拍, 这是一张普通的生活照片, 记录了当时的情景。牛排俯拍, 这是一张普通的生活照片, 记录了当时的情景。
    - `w23`: 牛排侧拍带叉子, 这是一张普通的生活照片, 记录了当时的情景。牛排侧拍带叉子, 这是一张普通的生活照片, 记录了当时的情…
    - `w24`: 牛排纹理特写, 这是一张普通的生活照片, 记录了当时的情景。牛排纹理特写, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.750
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## C6_xiaowang_hike_gps_drift

**C.6 小王山区徒步 GPS 漂移 ±150m 5 张**

- Pattern: `C.6` · Path: `L2` · Persona: `xiaowang`
- 产品意图: GPS 漂移大但 theme 一致 (hike), 不应因 GPS 散沙就放弃成集

### 输入照片
- `w17`: hike, trail, peak
- `w18`: hike, waterfall, mist
- `w19`: hike, rest, viewpoint
- `w20`: hike, summit, victory
- `w21`: hike, picnic, sandwich

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'weak'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w17`: 山路起点, 这是一张普通的生活照片, 记录了当时的情景。山路起点, 这是一张普通的生活照片, 记录了当时的情景。
    - `w18`: 半山瀑布 GPS 飘 200m, 这是一张普通的生活照片, 记录了当时的情景。半山瀑布 GPS 飘 200m, 这是一张…
    - `w19`: 观景台 GPS 飘 150m, 这是一张普通的生活照片, 记录了当时的情景。观景台 GPS 飘 150m, 这是一张普通…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.700
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## C7_xiaowang_concert_burst

**C.7 小王演唱会 1 分钟 8 张连拍**

- Pattern: `C.7` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 1 分钟内 8 张演唱会, T1.5 events∈[3,5] 升 strong 触发 / activity 二次门槛是否过滤

### 输入照片
- `w01`: concert, stage, lights
- `w02`: concert, stage, singer
- `w03`: concert, stage, blur
- `w04`: concert, audience, hands
- `w05`: concert, stage, song
- `w06`: concert, dance, choreography
- `w07`: concert, stage, fireworks
- `w08`: concert, audience, blur_motion

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'strong', 'people': 'medium', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w01`: 演唱会开场, 这是一张普通的生活照片, 记录了当时的情景。演唱会开场, 这是一张普通的生活照片, 记录了当时的情景。
    - `w02`: 主唱出场, 这是一张普通的生活照片, 记录了当时的情景。主唱出场, 这是一张普通的生活照片, 记录了当时的情景。
    - `w03`: 灯光模糊, 这是一张普通的生活照片, 记录了当时的情景。灯光模糊, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.858
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## C8_xiaowang_cafe_multi_subject

**C.8 小王咖啡馆 5 咖啡 + 3 朋友合影 (同地不同主体)**

- Pattern: `C.8` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 同一咖啡馆但 2 个不同主体 (咖啡 vs 朋友), 多维度博弈应拆集

### 输入照片
- `w09`: cafe, latte_art, foam
- `w10`: cafe, espresso, dark
- `w11`: cafe, dessert, tiramisu
- `w12`: cafe, friend, smile
- `w13`: cafe, friend, conversation
- `w14`: cafe, hand, book
- `w15`: cafe, cup_detail, light
- `w16`: cafe, latte_refill, second

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'weak', 'people': 'weak', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w09`: 拿铁拉花, 这是一张普通的生活照片, 记录了当时的情景。拿铁拉花, 这是一张普通的生活照片, 记录了当时的情景。
    - `w10`: 浓缩, 这是一张普通的生活照片, 记录了当时的情景。浓缩, 这是一张普通的生活照片, 记录了当时的情景。
    - `w11`: 提拉米苏, 这是一张普通的生活照片, 记录了当时的情景。提拉米苏, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.730
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## D1_zhang_screenshot_in_gathering

**D.1 张奶奶聚餐 3 张 + 微信截图 2 张穿插**

- Pattern: `D.1` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: 截图应被识别为非记忆型, 不应污染聚餐成集

### 输入照片
- `z08`: meal, restaurant, friend
- `z16`: meal, dish, cuisine
- `z28`: meal, group_photo, friends
- `z30`: screenshot, wechat, text
- `z33`: screenshot, recipe, app

### 算法行为
- 7 维 bands: {'location': 'none', 'time': 'weak', 'theme': 'weak', 'event': 'medium', 'people': 'weak', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `C3` · bounds=[light, medium]
- **LLM 输出**:
  - proposed_strength: weak
  - proposed_type: event
  - semantic_reason: mock:C3
  - evidence (3):
    - `z08`: 老同学聚餐主桌, 这是一张普通的生活照片, 记录了当时的情景。老同学聚餐主桌, 这是一张普通的生活照片, 记录了当时的情…
    - `z16`: 聚餐红烧肉特写, 这是一张普通的生活照片, 记录了当时的情景。聚餐红烧肉特写, 这是一张普通的生活照片, 记录了当时的情…
    - `z28`: 聚餐合影, 这是一张普通的生活照片, 记录了当时的情景。聚餐合影, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **weak**
- final_type: **event**
- display_decision: **show_inline_hint**
- composite_score: 0.365
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## D2_zhang_hospital_sensitive

**D.2 张奶奶体检医院 3 张 (sensitive_level=medium)**

- Pattern: `D.2` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: 敏感照片 sensitive_level≥medium, 即使其他维度都强, 也强 suppress

### 输入照片
- `z34`: hospital, checkup, waiting
- `z35`: hospital, blood_test, lab
- `z37`: hospital, pharmacy, medicine

### 算法行为
- 7 维 bands: {}
- 真值表: `None` · bounds=[None, None]
- **LLM 输出**:
  - proposed_strength: None
  - proposed_type: None
  - semantic_reason: None
  - counter_evidence: None
  - is_mock: None

### Policy Engine 最终
- final_strength: **none**
- final_type: **weak**
- display_decision: **suppress**
- composite_score: 0.000
- policy_overrides: 0

### ✅ Invariants 全过 (INV-02)

---

## D9_zhang_high_freq_strong_event

**D.9 张奶奶家生日 6 张 (高频地点 + 强 celebration 不应被过度抑制)**

- Pattern: `D.9` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: 家 (高频) 办生日 (强 event), HR-POST-03 不应过度抑制 → 应该成集

### 输入照片
- `z38`: birthday, cake, candle
- `z39`: birthday, granddaughter, gift
- `z40`: birthday, family, table
- `z41`: birthday, blowing, candle
- `z42`: birthday, dinner, dish
- `z43`: birthday, hug, evening

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'medium', 'anchor': 'weak', 'emotional': 'strong'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `z38`: 生日蛋糕特写, 这是一张普通的生活照片, 记录了当时的情景。生日蛋糕特写, 这是一张普通的生活照片, 记录了当时的情景。
    - `z39`: 孙女拆礼物, 这是一张普通的生活照片, 记录了当时的情景。孙女拆礼物, 这是一张普通的生活照片, 记录了当时的情景。
    - `z40`: 全家围桌, 这是一张普通的生活照片, 记录了当时的情景。全家围桌, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.802
- policy_overrides: 0

### ✅ Invariants 全过 (all 8)

---

## EV1_zhang_event_signal_conflict

**EV.1 张奶奶餐厅周年庆 event 多信号冲突 3 张**

- Pattern: `EV.1` · Path: `L2` · Persona: `laoqi_zhang`
- 产品意图: event=celebration + activity=meal + scene=restaurant 多维冲突, ADR-0012 primary_share 怎么判

### 输入照片
- `z44`: restaurant, dinner, anniversary
- `z45`: restaurant, dishware, candle
- `z46`: restaurant, hug, joy

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'medium', 'anchor': 'strong', 'emotional': 'strong'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `z44`: 餐厅周年庆 (event=celeb activity=meal scene=restaurant 多信号冲突), 这是…
    - `z45`: 周年烛光, 这是一张普通的生活照片, 记录了当时的情景。周年烛光, 这是一张普通的生活照片, 记录了当时的情景。
    - `z46`: 餐厅拥抱, 这是一张普通的生活照片, 记录了当时的情景。餐厅拥抱, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.898
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T12_li_one_day_multi_spot_70km

**#12 李叔叔一日游 故宫+长城+鸟巢 6 张跨 70km**

- Pattern: `T.12` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 分散多点一日游: 3 个景点跨 70km, time 跨 10 小时, 应识别为同一行程或拆 3 集

### 输入照片
- `l71`: gugong, palace, morning
- `l72`: gugong, palace, hall
- `l73`: great_wall, mutianyu, badaling
- `l74`: great_wall, watchtower
- `l75`: bird_nest, night, lights
- `l76`: bird_nest, water_cube, neon

### 算法行为
- 7 维 bands: {'location': 'none', 'time': 'strong', 'theme': 'weak', 'event': 'strong', 'people': 'none', 'anchor': 'weak', 'emotional': 'strong'}
- 真值表: `A3` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: event
  - semantic_reason: mock:A3
  - evidence (3):
    - `l71`: 北京一日游早上故宫, 这是一张普通的生活照片, 记录了当时的情景。北京一日游早上故宫, 这是一张普通的生活照片, 记录了…
    - `l72`: 故宫太和殿, 这是一张普通的生活照片, 记录了当时的情景。故宫太和殿, 这是一张普通的生活照片, 记录了当时的情景。
    - `l73`: 长城八达岭 70km 跨度, 这是一张普通的生活照片, 记录了当时的情景。长城八达岭 70km 跨度, 这是一张普通的生…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **event**
- display_decision: **show_mini_album**
- composite_score: 0.570
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T13_xiaowang_citywalk_uniform_low

**#13 小王 Citywalk 低密度均匀 6 张**

- Pattern: `T.13` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 低密度均匀分布 (5km 6 张, 平均 800m/张), DBSCAN 死穴, theme=citywalk 一致兜底

### 输入照片
- `w35`: citywalk, alley, morning
- `w36`: citywalk, cafe_window, peek
- `w37`: citywalk, mural, painting
- `w38`: citywalk, park, bench
- `w39`: citywalk, bookstore, indie
- `w40`: citywalk, end, restaurant

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w35`: Citywalk 起点弄堂, 这是一张普通的生活照片, 记录了当时的情景。Citywalk 起点弄堂, 这是一张普通的生…
    - `w36`: 路过咖啡店, 这是一张普通的生活照片, 记录了当时的情景。路过咖啡店, 这是一张普通的生活照片, 记录了当时的情景。
    - `w37`: 街角涂鸦, 这是一张普通的生活照片, 记录了当时的情景。街角涂鸦, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.730
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T15_xiaowang_fireworks_newyear

**#15 小王跨年烟花 8 张 10 分钟跨业务日**

- Pattern: `T.15` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 跨年烟花: 10 分钟内 8 张同主题, 跨 04:00 业务日 vs 跨自然日 (00:00) 不同语义, ADR-0011 自然日归属

### 输入照片
- `w41`: fireworks, sky, anticipation
- `w42`: fireworks, first_burst
- `w43`: fireworks, sky, burst, red
- `w44`: fireworks, midnight, climax
- `w45`: fireworks, crowd, hug
- `w46`: fireworks, gold, sparks
- `w47`: fireworks, finale, smoke
- `w48`: fireworks, end, leaving

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'medium', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w41`: 跨年倒数 5 分钟, 这是一张普通的生活照片, 记录了当时的情景。跨年倒数 5 分钟, 这是一张普通的生活照片, 记录了…
    - `w42`: 第一波烟花, 这是一张普通的生活照片, 记录了当时的情景。第一波烟花, 这是一张普通的生活照片, 记录了当时的情景。
    - `w43`: 红色烟花, 这是一张普通的生活照片, 记录了当时的情景。红色烟花, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.828
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T18_xiaowang_checkin_multi_spot

**#18 小王网红打卡跨城 5 个点 5 张**

- Pattern: `T.18` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 跨城网红打卡 5 个点各 1 张, 跨 5km, 每点信息密度低, 应识别为 city checkin 而非分散沉淀

### 输入照片
- `w49`: checkin, mural_alley
- `w50`: checkin, cafe_window, latte
- `w51`: checkin, pink_wall, photo
- `w52`: checkin, dessert_shop, sweet
- `w53`: checkin, bridge, sunset

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'weak', 'people': 'medium', 'anchor': 'none', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w49`: 网红涂鸦弄堂, 这是一张普通的生活照片, 记录了当时的情景。网红涂鸦弄堂, 这是一张普通的生活照片, 记录了当时的情景。
    - `w50`: 网红咖啡, 这是一张普通的生活照片, 记录了当时的情景。网红咖啡, 这是一张普通的生活照片, 记录了当时的情景。
    - `w51`: 网红粉墙, 这是一张普通的生活照片, 记录了当时的情景。网红粉墙, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.752
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T19_li_marathon_10_spots

**#19 李叔叔暴走 10 景点 高频切换**

- Pattern: `T.19` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 一天 10 个景点高频切换, 不应被切成 10 个碎集, 应识别为 city tour 整体

### 输入照片
- `l77`: city_tour, bund, morning
- `l78`: city_tour, oriental_pearl_far
- `l79`: city_tour, yu_garden, ancient
- `l80`: city_tour, xintiandi, plaza
- `l81`: city_tour, tianzifang, lane
- `l82`: city_tour, jingan_temple
- `l83`: city_tour, lujiazui, modern
- `l84`: city_tour, shanghai_tower
- `l85`: city_tour, xujiahui, mall
- `l86`: city_tour, peoples_square, night

### 算法行为
- 7 维 bands: {'location': 'none', 'time': 'strong', 'theme': 'strong', 'event': 'strong', 'people': 'none', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `l77`: 外滩早上, 这是一张普通的生活照片, 记录了当时的情景。外滩早上, 这是一张普通的生活照片, 记录了当时的情景。
    - `l78`: 东方明珠远观, 这是一张普通的生活照片, 记录了当时的情景。东方明珠远观, 这是一张普通的生活照片, 记录了当时的情景。
    - `l79`: 豫园, 这是一张普通的生活照片, 记录了当时的情景。豫园, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.625
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T1_li_xihu_loop_15km

**#1 李叔叔环西湖闭环 15km 8 张**

- Pattern: `T.1` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 环湖闭环: 首尾近 200m 但中间 15km 跨度, DBSCAN 不应把环切成多个簇

### 输入照片
- `l51`: xihu, lake, morning, start
- `l52`: xihu, north_shore, bridge
- `l53`: xihu, hill, west_side
- `l54`: xihu, west_lake_island
- `l55`: xihu, south_shore, lunch
- `l56`: xihu, south_west, leifeng
- `l57`: xihu, walk_path, bench
- `l58`: xihu, return, lake

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'weak'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `l51`: 环湖起点北山街, 这是一张普通的生活照片, 记录了当时的情景。环湖起点北山街, 这是一张普通的生活照片, 记录了当时的情…
    - `l52`: 环湖北边断桥, 这是一张普通的生活照片, 记录了当时的情景。环湖北边断桥, 这是一张普通的生活照片, 记录了当时的情景。
    - `l53`: 环湖西边孤山, 这是一张普通的生活照片, 记录了当时的情景。环湖西边孤山, 这是一张普通的生活照片, 记录了当时的情景。
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.655
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T20_li_resort_lazy_3days

**#20 李叔叔度假村躺平 3 天 GPS 全程同 5 张**

- Pattern: `T.20` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 度假村 3 天 GPS 不变 + 时间稀疏, vs 高频地点核心区分: 应识别为'度假'(非高频)而非'家'(高频), HR-POST-03 不阻断

### 输入照片
- `l87`: resort, beach, ocean
- `l88`: resort, pool, sunset
- `l89`: resort, breakfast, leisure
- `l90`: resort, beach_lounger, book
- `l91`: resort, departure, last

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'medium', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `l87`: 三亚度假村早晨海滩, 这是一张普通的生活照片, 记录了当时的情景。三亚度假村早晨海滩, 这是一张普通的生活照片, 记录了…
    - `l88`: 度假村泳池日落, 这是一张普通的生活照片, 记录了当时的情景。度假村泳池日落, 这是一张普通的生活照片, 记录了当时的情…
    - `l89`: 度假村第二天早午餐, 这是一张普通的生活照片, 记录了当时的情景。度假村第二天早午餐, 这是一张普通的生活照片, 记录了…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.690
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T21_xiaowang_burst_plus_gap

**T.21 小王连拍+长间隔 5 张 1s + 1 张 30min 后**

- Pattern: `T.21` · Path: `L2` · Persona: `xiaowang`
- 产品意图: ADR-0011 time T1 链式切分: 5 张连拍紧凑 + 1 张 30min 跳跃, gap > 120min 切边界

### 输入照片
- `w54`: kid, jump, burst
- `w55`: kid, jump, mid_air
- `w56`: kid, jump, landing
- `w57`: kid, jump, smile
- `w58`: kid, jump, hug
- `w59`: park, rest, snack

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'weak', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w54`: 连拍第 1 张 (孩子起跳), 这是一张普通的生活照片, 记录了当时的情景。连拍第 1 张 (孩子起跳), 这是一张普通…
    - `w55`: 连拍第 2 张 (空中), 这是一张普通的生活照片, 记录了当时的情景。连拍第 2 张 (空中), 这是一张普通的生活照…
    - `w56`: 连拍第 3 张 (落地), 这是一张普通的生活照片, 记录了当时的情景。连拍第 3 张 (落地), 这是一张普通的生活照…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.775
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T22_li_camping_crossday_event

**T.22 李叔叔周末露营跨自然日同事件 6 张**

- Pattern: `T.22` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 跨多个 04:00 业务日同事件 (4/26 12:00 - 4/27 18:00 连续露营), ADR-0011 T2/T3 多日识别

### 输入照片
- `l92`: camping, tent_setup, mountain
- `l93`: camping, campfire, dusk
- `l94`: camping, stars, night_sky
- `l95`: camping, sunrise, mist
- `l96`: camping, hike, lunch
- `l97`: camping, packup, farewell

### 算法行为
- 7 维 bands: {'location': 'medium', 'time': 'weak', 'theme': 'strong', 'event': 'medium', 'people': 'none', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A2` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: thematic
  - semantic_reason: mock:A2
  - evidence (3):
    - `l92`: 周六中午到营地搭帐篷, 这是一张普通的生活照片, 记录了当时的情景。周六中午到营地搭帐篷, 这是一张普通的生活照片, 记…
    - `l93`: 篝火黄昏, 这是一张普通的生活照片, 记录了当时的情景。篝火黄昏, 这是一张普通的生活照片, 记录了当时的情景。
    - `l94`: 营地观星 (跨第一个 04:00 前), 这是一张普通的生活照片, 记录了当时的情景。营地观星 (跨第一个 04:00 …
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **thematic**
- display_decision: **show_mini_album**
- composite_score: 0.585
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T3_li_pedestrian_street_uneven

**#3 李叔叔步行街密度不均 6 张 (3 密 + 3 稀)**

- Pattern: `T.3` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 步行街内密度不均: 网红店 3 张密集 (3 分钟) + 普通段 3 张稀疏, DBSCAN eps 难适配

### 输入照片
- `l59`: nanjing_road, neon, shop
- `l60`: nanjing_road, neon, dessert
- `l61`: nanjing_road, neon, queue
- `l62`: nanjing_road, plain, walking
- `l63`: nanjing_road, shop_window
- `l64`: nanjing_road, end, exit

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'strong', 'people': 'none', 'anchor': 'none', 'emotional': 'strong'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `l59`: 网红奶茶店门口一, 这是一张普通的生活照片, 记录了当时的情景。网红奶茶店门口一, 这是一张普通的生活照片, 记录了当时…
    - `l60`: 网红奶茶店门口二, 这是一张普通的生活照片, 记录了当时的情景。网红奶茶店门口二, 这是一张普通的生活照片, 记录了当时…
    - `l61`: 网红奶茶店门口三排队, 这是一张普通的生活照片, 记录了当时的情景。网红奶茶店门口三排队, 这是一张普通的生活照片, 记…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.750
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T4_xiaowang_hike_sparse_dense

**#4 小王徒步前疏后密 4 张**

- Pattern: `T.4` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 徒步登山前段稀疏 (2 张) + 山顶密集 (2 张), 时间密度前后差异极大, 前段不应被 sparse 踢掉

### 输入照片
- `w31`: hike, start, easy_path
- `w32`: hike, mid_way, fatigue
- `w33`: hike, summit, panorama, victory
- `w34`: hike, summit, friends, selfie

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'weak', 'anchor': 'strong', 'emotional': 'strong'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w31`: 山脚起步, 这是一张普通的生活照片, 记录了当时的情景。山脚起步, 这是一张普通的生活照片, 记录了当时的情景。
    - `w32`: 半山疲累 (前疏), 这是一张普通的生活照片, 记录了当时的情景。半山疲累 (前疏), 这是一张普通的生活照片, 记录了…
    - `w33`: 山顶第一张 (后密开始), 这是一张普通的生活照片, 记录了当时的情景。山顶第一张 (后密开始), 这是一张普通的生活照…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.845
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## T7_li_around_landmark_small_loop

**#7 李叔叔绕东方明珠小环 6 张**

- Pattern: `T.7` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 绕主体小环: GPS 形成小范围闭环, 主体一致 (theme strong) 应压过 location 小波动

### 输入照片
- `l65`: oriental_pearl, north, full
- `l66`: oriental_pearl, east, lower
- `l67`: oriental_pearl, south, river
- `l68`: oriental_pearl, west, sunset
- `l69`: oriental_pearl, group, photo
- `l70`: oriental_pearl, close, detail

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'medium', 'people': 'weak', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `l65`: 东方明珠北面, 这是一张普通的生活照片, 记录了当时的情景。东方明珠北面, 这是一张普通的生活照片, 记录了当时的情景。
    - `l66`: 东方明珠东面仰拍, 这是一张普通的生活照片, 记录了当时的情景。东方明珠东面仰拍, 这是一张普通的生活照片, 记录了当时…
    - `l67`: 东方明珠南面带江, 这是一张普通的生活照片, 记录了当时的情景。东方明珠南面带江, 这是一张普通的生活照片, 记录了当时…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.775
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## TH1_li_theme_granularity_mix

**TH.1 李叔叔 theme 颗粒度混合 4 张 (粗/中/细/感官)**

- Pattern: `TH.1` · Path: `L2` · Persona: `laoli_youke`
- 产品意图: 同地点不同颗粒度 theme 标签, 字面 Jaccard ≈ 0 但 ADR-0008 语义簇应识别都是'西湖'

### 输入照片
- `l98`: 湖水, 春日, 自然
- `l99`: 断桥, 行人, 风筝
- `l100`: 西湖, 杭州, 风景
- `l101`: 波光, 涟漪, 春风

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'weak', 'event': 'strong', 'people': 'none', 'anchor': 'weak', 'emotional': 'medium'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `l98`: 西湖 (粗颗粒标签), 这是一张普通的生活照片, 记录了当时的情景。西湖 (粗颗粒标签), 这是一张普通的生活照片, 记…
    - `l99`: 西湖 (细颗粒物象标签), 这是一张普通的生活照片, 记录了当时的情景。西湖 (细颗粒物象标签), 这是一张普通的生活照…
    - `l100`: 西湖 (中颗粒地名标签), 这是一张普通的生活照片, 记录了当时的情景。西湖 (中颗粒地名标签), 这是一张普通的生活照…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.685
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

## TH2_xiaowang_multi_strong_theme

**TH.2 小王单图多 strong theme 3 张 (万圣节+晚宴+生日)**

- Pattern: `TH.2` · Path: `L2` · Persona: `xiaowang`
- 产品意图: 单图 theme 多元素 (≥5 标签), ADR-0013 双层判定能否处理 'theme 多焦点'

### 输入照片
- `w60`: halloween, dinner, birthday, costume, cake
- `w61`: costume, pumpkin, decoration, dinner_table, cocktail
- `w62`: birthday_cake, candles, halloween_mask

### 算法行为
- 7 维 bands: {'location': 'strong', 'time': 'strong', 'theme': 'strong', 'event': 'strong', 'people': 'weak', 'anchor': 'strong', 'emotional': 'strong'}
- 真值表: `A1` · bounds=[medium, strong]
- **LLM 输出**:
  - proposed_strength: medium
  - proposed_type: location
  - semantic_reason: mock:A1
  - evidence (3):
    - `w60`: 万圣节晚宴生日三合一, 这是一张普通的生活照片, 记录了当时的情景。万圣节晚宴生日三合一, 这是一张普通的生活照片, 记…
    - `w61`: 多主题装饰 (pumpkin+表+酒), 这是一张普通的生活照片, 记录了当时的情景。多主题装饰 (pumpkin+表+…
    - `w62`: 戴万圣面具吹生日蜡烛, 这是一张普通的生活照片, 记录了当时的情景。戴万圣面具吹生日蜡烛, 这是一张普通的生活照片, 记…
  - counter_evidence: v0.1 mock 阶段, counter_evidence 占位
  - is_mock: True

### Policy Engine 最终
- final_strength: **medium**
- final_type: **location**
- display_decision: **show_mini_album**
- composite_score: 0.875
- policy_overrides: 0

### ✅ Invariants 全过 (INV-01)

---

# L2.5 (path A 生长) · 15 个 scenarios

## A4_zhang_granddaughter_grab

**A.4 张奶奶被孙女抢手机自拍 3 张突变**

- Pattern: `A.4` · Path: `L2.5` · Persona: `laoqi_zhang`
- 产品意图: 孙女自拍突变 vs 阳台花相册, 应 no_merge (主题完全无关)

### 输入照片
- `z11`: selfie, child, funny

### 算法行为
- 候选老相册: ['ma_granddaughter_album']
- per_album_evaluations: 1
  - album `ma_granddaughter_album`: pattern=`G-D1`, tier=`ask_user`
    - LLM accept=True, reason: mock:G-D1
- **最终 decision_tier**: `ask_user`
- target_album: ma_granddaughter_album

### ✅ Invariants 全过 (INV-01)

---

## L25_li_camping_to_xihu_no_merge

**L2.5 李叔叔露营 vs 西湖相册 → no_merge (跨主题)**

- Pattern: `L25.cross_theme` · Path: `L2.5` · Persona: `laoli_youke`
- 产品意图: 露营 vs 西湖游, 跨主题应 no_merge

### 输入照片
- `l93`: camping, campfire, dusk

### 算法行为
- 候选老相册: ['ma_past_xihu_album']
- per_album_evaluations: 1
  - album `ma_past_xihu_album`: pattern=`G-F1`, tier=`no_merge`
    - LLM accept=False, reason: g_f1_no_signal
- **最终 decision_tier**: `no_merge`
- target_album: None

### ✅ Invariants 全过 (INV-01)

---

## L25_li_multi_anchor_to_xihu

**L2.5 李叔叔多 anchor 照 vs 西湖相册 (anchor 颗粒度边界)**

- Pattern: `L25.multi_anchor` · Path: `L2.5` · Persona: `laoli_youke`
- 产品意图: 新照含 4 个 meaning_anchor + 5 个 object, 同地点应 auto_merge / ask_user

### 输入照片
- `l102`: bridge, garden, walk

### 算法行为
- 候选老相册: ['ma_past_xihu_album']
- per_album_evaluations: 1
  - album `ma_past_xihu_album`: pattern=`G-A1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-A1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_past_xihu_album

### ✅ Invariants 全过 (INV-01)

---

## L25_li_pick_grandkid_high_freq

**L2.5 李叔叔接娃 vs 接娃相册 → auto/ask (高频地点)**

- Pattern: `L25.high_freq` · Path: `L2.5` · Persona: `laoli_youke`
- 产品意图: 高频地点 + 日常 routine, HR-POST-03 边界

### 输入照片
- `l35`: school_gate, grandkid, smile

### 算法行为
- 候选老相册: ['ma_pick_grandkid_album']
- per_album_evaluations: 1
  - album `ma_pick_grandkid_album`: pattern=`G-B2`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-B2
- **最终 decision_tier**: `auto_merge`
- target_album: ma_pick_grandkid_album

### ✅ Invariants 全过 (INV-03)

---

## L25_li_th_granularity_细颗粒_to_xihu

**L2.5 李叔叔西湖细颗粒标签 vs 西湖相册 (语义簇兜底)**

- Pattern: `L25.th_granularity` · Path: `L2.5` · Persona: `laoli_youke`
- 产品意图: 细颗粒标签 [断桥, 行人, 风筝] 字面 Jaccard=0 但 ADR-0008 语义簇识别 → 应 auto_merge

### 输入照片
- `l99`: 断桥, 行人, 风筝

### 算法行为
- 候选老相册: ['ma_past_xihu_album']
- per_album_evaluations: 1
  - album `ma_past_xihu_album`: pattern=`G-A1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-A1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_past_xihu_album

### ✅ Invariants 全过 (INV-01)

---

## L25_R1_zhang_balcony_to_walk_no_merge

**L2.5 #R1 张奶奶阳台花 vs 公园散步相册 → no_merge (跨场景反例)**

- Pattern: `L25.R1` · Path: `L2.5` · Persona: `laoqi_zhang`
- 产品意图: 阳台花 vs 公园相册 主题不同地点不同, 基础反例 no_merge

### 输入照片
- `z01`: peony, bud, balcony

### 算法行为
- 候选老相册: ['ma_weekly_park_walk_album']
- per_album_evaluations: 1
  - album `ma_weekly_park_walk_album`: pattern=`G-C1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-C1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_weekly_park_walk_album

### ✅ Invariants 全过 (INV-01)

---

## L25_R2_zhang_walk_to_walk_auto_merge

**L2.5 #R2 张奶奶公园晨练 vs 公园相册 → auto_merge (基础正例)**

- Pattern: `L25.R2` · Path: `L2.5` · Persona: `laoqi_zhang`
- 产品意图: 同地点同主题, 基础正例应 auto_merge

### 输入照片
- `z07`: garden, morning, walk

### 算法行为
- 候选老相册: ['ma_weekly_park_walk_album']
- per_album_evaluations: 1
  - album `ma_weekly_park_walk_album`: pattern=`G-A1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-A1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_weekly_park_walk_album

### ✅ Invariants 全过 (INV-01)

---

## L25_R3_li_xihu_new_to_xihu_auto

**L2.5 #R3 李叔叔西湖新照 (粗颗粒) vs 西湖相册 → auto_merge (基础正例)**

- Pattern: `L25.R3` · Path: `L2.5` · Persona: `laoli_youke`
- 产品意图: 新西湖照 vs 西湖相册, 同地点同主题, 应 auto_merge (theme 颗粒度粗也能识别)

### 输入照片
- `l98`: 湖水, 春日, 自然

### 算法行为
- 候选老相册: ['ma_past_xihu_album']
- per_album_evaluations: 1
  - album `ma_past_xihu_album`: pattern=`G-A1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-A1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_past_xihu_album

### ✅ Invariants 全过 (INV-01)

---

## L25_R4_li_gugong_to_xihu_no_merge

**L2.5 #R4 李叔叔故宫 vs 西湖相册 → no_merge (跨城反例)**

- Pattern: `L25.R4` · Path: `L2.5` · Persona: `laoli_youke`
- 产品意图: 跨城反例: 故宫 (北京) vs 西湖 (杭州), 即使主题都 ancient 也应 no_merge

### 输入照片
- `l42`: mountain, valley, afternoon

### 算法行为
- 候选老相册: ['ma_past_xihu_album']
- per_album_evaluations: 1
  - album `ma_past_xihu_album`: pattern=`G-B2`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-B2
- **最终 decision_tier**: `auto_merge`
- target_album: ma_past_xihu_album

### ✅ Invariants 全过 (INV-01)

---

## L25_xiaowang_concert_to_walk_no_merge

**L2.5 小王演唱会照 vs 张奶奶公园相册 → no_merge (跨用户反例)**

- Pattern: `L25.cross_user` · Path: `L2.5` · Persona: `xiaowang`
- 产品意图: 演唱会照 vs 公园相册 (不同 persona), 主题完全不同, no_merge

### 输入照片
- `w01`: concert, stage, lights

### 算法行为
- 候选老相册: []
- per_album_evaluations: 0
- **最终 decision_tier**: `no_merge`
- target_album: None

### ✅ Invariants 全过 (INV-01)

---

## L25_xiaowang_multi_theme_to_walk_no_merge

**L2.5 小王单图多 strong theme (万圣节+生日) vs 张奶奶公园相册 → no_merge**

- Pattern: `L25.multi_theme` · Path: `L2.5` · Persona: `xiaowang`
- 产品意图: 单图多 strong theme + 跨场景, 算法主导 theme 选择

### 输入照片
- `w60`: halloween, dinner, birthday, costume, cake

### 算法行为
- 候选老相册: []
- per_album_evaluations: 0
- **最终 decision_tier**: `no_merge`
- target_album: None

### ✅ Invariants 全过 (INV-01)

---

## L25_zhang_distractor_screenshot_to_walk

**L2.5 张奶奶截图干扰 vs 公园相册 → no_merge**

- Pattern: `L25.distractor` · Path: `L2.5` · Persona: `laoqi_zhang`
- 产品意图: 截图非记忆型干扰, 应 no_merge

### 输入照片
- `z30`: screenshot, wechat, text

### 算法行为
- 候选老相册: ['ma_weekly_park_walk_album']
- per_album_evaluations: 1
  - album `ma_weekly_park_walk_album`: pattern=`G-C1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-C1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_weekly_park_walk_album

### ✅ Invariants 全过 (INV-01)

---

## L25_zhang_event_conflict_to_album

**L2.5 张奶奶餐厅周年庆 (event 多信号冲突) vs 孙女相册**

- Pattern: `L25.event_conflict` · Path: `L2.5` · Persona: `laoqi_zhang`
- 产品意图: event=celebration + activity=meal + scene=restaurant 多信号冲突时, primary event 主导决策

### 输入照片
- `z44`: restaurant, dinner, anniversary

### 算法行为
- 候选老相册: ['ma_granddaughter_album']
- per_album_evaluations: 1
  - album `ma_granddaughter_album`: pattern=`G-C1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-C1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_granddaughter_album

### ✅ Invariants 全过 (INV-01)

---

## L25_zhang_high_freq_birthday_celebration

**L2.5 张奶奶生日 (家高频) vs 孙女相册 → auto_merge (强 event 不降)**

- Pattern: `L25.high_freq_strong_event` · Path: `L2.5` · Persona: `laoqi_zhang`
- 产品意图: 高频地点 + 强 celebration, HR-POST-03 不过度抑制

### 输入照片
- `z38`: birthday, cake, candle

### 算法行为
- 候选老相册: ['ma_granddaughter_album']
- per_album_evaluations: 1
  - album `ma_granddaughter_album`: pattern=`G-C1`, tier=`auto_merge`
    - LLM accept=True, reason: mock:G-C1
- **最终 decision_tier**: `auto_merge`
- target_album: ma_granddaughter_album

### ✅ Invariants 全过 (INV-03)

---

## L25_zhang_sensitive_to_any_no_merge

**L2.5 张奶奶医院敏感 vs 公园相册 → no_merge (红线 #6)**

- Pattern: `L25.sensitive` · Path: `L2.5` · Persona: `laoqi_zhang`
- 产品意图: 敏感照片 sensitive_level=medium, 即使其他维度都强, 永远 no_merge (HRG-POST-01)

### 输入照片
- `z34`: hospital, checkup, waiting

### 算法行为
- 候选老相册: []
- per_album_evaluations: 0
- **最终 decision_tier**: `no_merge`
- target_album: None

### ✅ Invariants 全过 (INV-02)

---

# Cascade (path C 回滚) · 15 个 scenarios

## C_li_marathon_no_recall

**cascade 李叔叔暴走单张 vs 沉淀池 (其他暴走) → 看决定**

- Pattern: `C.marathon` · Path: `cascade` · Persona: `laoli_youke`
- 产品意图: 暴走 1 张 vs 池里其他暴走景点, 每点信息密度低

### 输入照片
- `l77`: city_tour, bund, morning

### 算法行为
- 粗筛后候选: ['l80', 'l79', 'l78']
- 维度排序选 top 4: ['l80', 'l79', 'l78']
- 真值表: `A1`
- LLM: strength=`strong`, reason: mock:A1 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', True), ('BACKFILL-CAP-01-bounds_max_strong', True), ('BACKFILL-CAP-02-llm_strength_strong', True)]
- **最终 decision_tier**: `create_new_album`

### ✅ Invariants 全过 (INV-01)

---

## C_li_overnight_recall

**cascade 李叔叔西湖夜游单张 vs 沉淀夜游 → 召回 (跨业务日)**

- Pattern: `C.overnight` · Path: `cascade` · Persona: `laoli_youke`
- 产品意图: 跨业务日单张 vs 沉淀池同主题, 应召回

### 输入照片
- `l05`: xihu, moonlight, bridge

### 算法行为
- 粗筛后候选: ['l03', 'l02', 'l01']
- 维度排序选 top 4: ['l02', 'l01', 'l03']
- 真值表: `A2`
- LLM: strength=`strong`, reason: mock:A2 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', True), ('BACKFILL-CAP-01-bounds_max_strong', True), ('BACKFILL-CAP-02-llm_strength_strong', True)]
- **最终 decision_tier**: `create_new_album`

### ✅ Invariants 全过 (INV-04, INV-05)

---

## C_li_resort_lazy_empty

**cascade 李叔叔度假村单张 vs 空池 → insufficient**

- Pattern: `C.resort` · Path: `cascade` · Persona: `laoli_youke`
- 产品意图: 度假村单张 vs 空池 → insufficient

### 输入照片
- `l87`: resort, beach, ocean

### 算法行为
- 粗筛后候选: []
- 维度排序选 top 4: []
- 真值表: `N/A`
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-04)

---

## C_li_th_granularity_recall

**cascade 李叔叔西湖感官标签 vs 沉淀池(4 颗粒度西湖) → 语义簇召回**

- Pattern: `C.th_granularity` · Path: `cascade` · Persona: `laoli_youke`
- 产品意图: 新照感官颗粒 vs 池里粗/中/细 + 一张感官, 字面 Jaccard 低, 语义簇兜底

### 输入照片
- `l101`: 波光, 涟漪, 春风

### 算法行为
- 粗筛后候选: ['l100', 'l99', 'l98', 'l51']
- 维度排序选 top 4: ['l100', 'l99', 'l98', 'l51']
- 真值表: `A1`
- LLM: strength=`strong`, reason: mock:A1 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', True), ('BACKFILL-CAP-01-bounds_max_strong', True), ('BACKFILL-CAP-02-llm_strength_strong', True)]
- **最终 decision_tier**: `create_new_album`

### ✅ Invariants 全过 (INV-01)

---

## C_R1_zhang_balcony_recall_balcony

**cascade #R1 张奶奶阳台花新照 vs 沉淀池 (有阳台花) → create_new_album**

- Pattern: `C.R1` · Path: `cascade` · Persona: `laoqi_zhang`
- 产品意图: cascade 基础正例: 新照跟池里 4 张同主题, 应 create_new_album

### 输入照片
- `z32`: peony, second_bud, hope

### 算法行为
- 粗筛后候选: ['z06', 'z03']
- 维度排序选 top 4: ['z06', 'z03']
- 真值表: `A3`
- LLM: strength=`strong`, reason: mock:A3 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', True), ('BACKFILL-CAP-01-bounds_max_strong', True), ('BACKFILL-CAP-02-llm_strength_strong', True)]
- **最终 decision_tier**: `create_new_album`

### ✅ Invariants 全过 (INV-01, INV-04, INV-05, INV-06)

---

## C_R2_zhang_empty_pool_insufficient

**cascade #R2 张奶奶单张 vs 空池 → insufficient (基础反例)**

- Pattern: `C.R2` · Path: `cascade` · Persona: `laoqi_zhang`
- 产品意图: cascade 基础反例: 空池无候选 → insufficient_candidates

### 输入照片
- `z32`: peony, second_bud, hope

### 算法行为
- 粗筛后候选: []
- 维度排序选 top 4: []
- 真值表: `N/A`
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-04)

---

## C_R3_li_xihu_recall_xihu

**cascade #R3 李叔叔西湖新照 vs 沉淀池 (西湖类似) → create_new_album**

- Pattern: `C.R3` · Path: `cascade` · Persona: `laoli_youke`
- 产品意图: cascade 跨颗粒度: 新中颗粒 vs 池里粗+细+感官混合, 应召回

### 输入照片
- `l100`: 西湖, 杭州, 风景

### 算法行为
- 粗筛后候选: ['l54', 'l53', 'l52', 'l51']
- 维度排序选 top 4: ['l51', 'l54', 'l53', 'l52']
- 真值表: `A3`
- LLM: strength=`strong`, reason: mock:A3 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', True), ('BACKFILL-CAP-01-bounds_max_strong', True), ('BACKFILL-CAP-02-llm_strength_strong', True)]
- **最终 decision_tier**: `create_new_album`

### ✅ Invariants 全过 (INV-04, INV-05, INV-06)

---

## C_R4_li_gugong_cross_city_no_recall

**cascade #R4 李叔叔故宫 vs 沉淀西湖池 → no_backfill (跨城反例)**

- Pattern: `C.R4` · Path: `cascade` · Persona: `laoli_youke`
- 产品意图: 跨城反例: 新故宫照 vs 池里西湖, 不应误召回

### 输入照片
- `l42`: mountain, valley, afternoon

### 算法行为
- 粗筛后候选: ['l53', 'l52', 'l51']
- 维度排序选 top 4: ['l53', 'l52', 'l51']
- 真值表: `A1`
- LLM: strength=`strong`, reason: mock:A1 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', True), ('BACKFILL-CAP-01-bounds_max_strong', True), ('BACKFILL-CAP-02-llm_strength_strong', True)]
- **最终 decision_tier**: `create_new_album`

### ✅ Invariants 全过 (INV-01)

---

## C_R5_zhang_event_conflict_empty

**cascade #R5 张奶奶餐厅周年 (event 冲突) vs 空池 → insufficient**

- Pattern: `C.R5` · Path: `cascade` · Persona: `laoqi_zhang`
- 产品意图: event 多信号冲突 + 空池 → insufficient

### 输入照片
- `z44`: restaurant, dinner, anniversary

### 算法行为
- 粗筛后候选: []
- 维度排序选 top 4: []
- 真值表: `N/A`
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-04)

---

## C_xiaowang_checkin_no_recall

**cascade 小王网红打卡单张 vs 沉淀池(其他网红) → 看决定**

- Pattern: `C.checkin` · Path: `cascade` · Persona: `xiaowang`
- 产品意图: 网红打卡单张 vs 池里其他网红点, 每点 1 张, 跨城

### 输入照片
- `w49`: checkin, mural_alley

### 算法行为
- 粗筛后候选: ['w51']
- 维度排序选 top 4: ['w51']
- 真值表: `A2`
- LLM: strength=`strong`, reason: mock:A2 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-01)

---

## C_xiaowang_concert_no_recall

**cascade 小王演唱会单张 vs 沉淀(无相关) → no_backfill**

- Pattern: `C.concert` · Path: `cascade` · Persona: `xiaowang`
- 产品意图: 演唱会单张 vs 池里无相关, no_backfill

### 输入照片
- `w01`: concert, stage, lights

### 算法行为
- 粗筛后候选: []
- 维度排序选 top 4: []
- 真值表: `N/A`
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-01)

---

## C_xiaowang_fireworks_no_recall

**cascade 小王跨年烟花单张 vs 沉淀池(无烟花) → no_backfill**

- Pattern: `C.fireworks` · Path: `cascade` · Persona: `xiaowang`
- 产品意图: 烟花单张 vs 池里无相关烟花, no_backfill

### 输入照片
- `w44`: fireworks, midnight, climax

### 算法行为
- 粗筛后候选: []
- 维度排序选 top 4: []
- 真值表: `N/A`
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-01)

---

## C_xiaowang_multi_theme_no_recall

**cascade 小王单图多 strong theme vs 沉淀池(任何) → 看决定**

- Pattern: `C.multi_theme` · Path: `cascade` · Persona: `xiaowang`
- 产品意图: 单图含万圣节+晚宴+生日多 theme vs 池里无相关, 算法主导 theme 选择

### 输入照片
- `w60`: halloween, dinner, birthday, costume, cake

### 算法行为
- 粗筛后候选: ['w35']
- 维度排序选 top 4: ['w35']
- 真值表: `A1`
- LLM: strength=`strong`, reason: mock:A1 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-01)

---

## C_zhang_screenshot_no_recall

**cascade 张奶奶截图干扰 vs 沉淀池 → no_backfill**

- Pattern: `C.distractor` · Path: `cascade` · Persona: `laoqi_zhang`
- 产品意图: 干扰截图 vs 池, 主题完全无关, no_backfill

### 输入照片
- `z30`: screenshot, wechat, text

### 算法行为
- 粗筛后候选: ['z06', 'z03', 'z01']
- 维度排序选 top 4: ['z06', 'z03', 'z01']
- 真值表: `A3`
- LLM: strength=`strong`, reason: mock:A3 | backfill_context: 这是兜底回扫场景, 沉淀单图可能跨多天甚至数周。
- caps: [('BACKFILL-CAP-03-recall_count', True), ('BACKFILL-CAP-01-bounds_max_strong', True), ('BACKFILL-CAP-02-llm_strength_strong', True)]
- **最终 decision_tier**: `create_new_album`

### ✅ Invariants 全过 (INV-01)

---

## C_zhang_sensitive_no_recall

**cascade 张奶奶敏感照 vs 沉淀池 → no_backfill (HR-PRE)**

- Pattern: `C.sensitive` · Path: `cascade` · Persona: `laoqi_zhang`
- 产品意图: 敏感照 sensitive_level=medium, HR-PRE 强制 suppress

### 输入照片
- `z34`: hospital, checkup, waiting

### 算法行为
- 粗筛后候选: []
- 维度排序选 top 4: []
- 真值表: `N/A`
- caps: [('BACKFILL-CAP-03-recall_count', False)]
- **最终 decision_tier**: `insufficient_candidates`

### ✅ Invariants 全过 (INV-02)

---
