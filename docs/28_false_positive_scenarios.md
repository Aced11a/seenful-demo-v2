# 28 · 假阳场景目录 (符合规则但不应成集)

> 算法路径走通了, 但产品意图反对成集的场景清单.
> 目的: 给 persona/scenario 补漏 + 给真实数据上线后调参提供基线.
> **本文档只列问题, 不提解决方案** — 解决方案要走 ADR 流程.
>
> 作者: Ace + Claude 共同梳理, 2026-05-20
> 触发: Ace "测试集还差一块没有测试: 符合规则但不应该成集"

---

## 文档约定

- 每个 case 列: **触发条件 / 算法路径 / 假阳原因 / 涉及红线 / 现有防御 / 状态**
- **状态**: 🟢 已防御 / 🟡 部分防御 / 🔴 未防御 / ⚫ 无法防御 (设计缺口)
- **红线**: 引用 CLAUDE.md 8 条产品红线编号
- **类**: A = 用户行为类 / B = 规则漏洞类 (对抗性) / C = 数据语义陷阱

---

## A 类 · 真实用户行为触发 (用户无恶意, 算法过度敏感)

### A1 · 流水账类高频地点

- **触发**: 张师傅家附近早餐店 5 张连续 7 天拍, 同 GPS (50m 半径), event=meal, theme=早餐/包子/豆浆
- **路径**: location strong (单点紧聚) + event strong (E.1 meal + activity=meal ≥ 2/3) + theme strong (TH.1 全员一致) → 主真值表 A1/A2/A3 任一直接成集
- **假阳原因**: "天天去同一家早餐店" 是**日常流水**, 不是用户想留念的"事件". 信号都强反而是反例.
- **红线**: #7 (高频地点不能仅凭 GPS 自动并入)
- **现有防御**: HR-BANDS-01 (ADR-0006 高频 + 低质量地点降一档) + HR-POST-03 (高频 + theme/event 弱时 cap medium)
- **状态**: 🟡 部分 — 老 HR-POST-03 只降"theme/event 弱"的, 这种 case 全 strong 不降; ADR-0006 双 density 真实场景要靠 user_history (demo 没接), 现行不降.

---

### A2 · 弱关联凑 daily_record

- **触发**: 3 张完全不相关的照片 (一张早餐, 一张地铁里, 一张同事桌前), 但 L1 全部判 event_hint=`daily_record` + activity 都标 walk/stand
- **路径**: event E.1 strong (primary_share=1.0 + activity≥2/3) → A3 真值表 (event=强 单独成集 type=event)
- **假阳原因**: daily_record 是 L1 的兜底枚举, 语义本就是"零碎记录, 没具体事件". 凑足 3 张就成集违反"成集 = 有事件" 直觉.
- **红线**: #5 (弱关联绝不成集)
- **现有防御**: **无**. event 算法不区分 daily_record 与其他枚举.
- **状态**: 🔴 未防御 — 本次会话 (2026-05-20) Ace 已问过, 暂未加 HR.

---

### A3 · 跨季同地点 (年度合集 vs 事件相册)

- **触发**: 同一公园春夏秋冬各拍 3 张, 共 12 张. location strong (同 GPS) + time T3 跨多日 (9 个月跨度) + theme strong "公园"
- **路径**: 主真值表 A1/A2 → 成"公园相册"
- **假阳原因**: 跨季节属"年度回顾"语义 (年度合集应是更高层的产物), 算法把它压成单事件相册.
- **红线**: 无直接违反, 但"成集语义颗粒度"错乱.
- **现有防御**: time T3 grid 没显式拒绝, 但 T3.4 (span > 12h) 可能 cap weak. 实测要看.
- **状态**: ⚫ 设计缺口 — 当前没有"长时间跨度该不该单事件" 的机制, 留 OQ.

---

### A4 · 上下班路线 / 接娃路线

- **触发**: 用户每天 7:30 - 8:00 拍 1 张地铁 / 路边, 累积 1 个月 30 张. 同 GPS chain (linear shape) + event=daily_record/work + time 链式切分多日.
- **路径**: location strong (linear chain) + event strong / theme strong → 多维 strong
- **假阳原因**: 同 A1 流水账逻辑, 但形态从"点"变成"线"
- **红线**: #7
- **现有防御**: ADR-0010 LocationFeature 形状校正 (linear → A1.5/A1.7 单独 path), 但仍 strong/medium 成集
- **状态**: 🟡 部分 — 形状识别有, 但没拒绝成集. ADR-0011 多日 K_days 也只是 medium-low.

---

### A5 · 多次同餐厅就餐

- **触发**: 朋友常聚的某餐厅, 一年内去 5 次各拍 3 张, 共 15 张. location strong + event=meal strong + theme 散 (不同菜)
- **路径**: 跨日成 path B 全员, 走 B 系列 multi-medium → strong
- **假阳原因**: 5 次独立聚会**不应该**合并成 1 本"餐厅相册", 每次应是独立小集 (后期可"年度合集"再聚).
- **红线**: 弱违反"事件单一性", 没直接红线
- **现有防御**: ADR-0011 time 切分 (gap > 120min 切) 应该拆开, 但 path B 是 batch 模式不分时段
- **状态**: 🟡 — 真实接入 N≥3 时 dispatch 给 path B 整批跑, time 多日只是 T3 cap medium, 不强制拆.

---

### A6 · 同 GPS 完全不同场景 (咖啡馆复合)

- **触发**: 用户在咖啡馆待 4 小时, 拍工作 2 张 + 朋友合影 2 张 + 餐 1 张. 同 GPS + 同时间窗 + event 散
- **路径**: location strong + time T1.5/T1.6 (events≤5) → 走 B 系列, theme 散 weak, event 散 weak → 真值表 D 系列 (location 单 strong) 可能 medium
- **假阳原因**: 时空叠加但**语义混杂**, 应该按 event/theme 拆成多本小集
- **红线**: 无直接违反, "事件单一性" 问题
- **现有防御**: ADR-0022 TH.0 (多并列主簇) 对 theme; event 暂无对称规则
- **状态**: 🟡 — ADR-0022 修了 theme 多并列, event 多并列还没 (eg. meal + work + gathering 各占 1/3)

---

### A7 · 截图穿插

- **触发**: 4 张真实拍摄 + 1 张应用截图 (聊天记录 / 网页 / TikTok 帧) 一起上传
- **路径**: 截图通过 HR-PRE (sensitive_level=none), 进 batch, 拉动 theme/event 偏向 "屏幕内容"
- **假阳原因**: 截图本质不是"用户在场"的拍摄, 应独立沉淀
- **红线**: 弱违反 #8 (L1 落库即权威, 但 L1 没标 image_type)
- **现有防御**: 无. L1Output **缺 image_type / source 字段**.
- **状态**: 🔴 未防御 — 字段层缺失.

---

### A8 · 路径 A 老相册"续命漂移"

- **触发**: 用户老相册 = 第一次去某公园 5 张. 后续半年陆续单图上传公园, 每次都 path A 命中 auto_merge / ask_user, 老相册一直 is_growing=true 续到 30 张
- **路径**: 30 天 growth_lock_at 每次都被刷新, 永远不锁
- **假阳原因**: 相册"语义边界扩散" — 老"某次出游" 变成"半年来去公园的总集", 失去事件单一性
- **红线**: #4 (同图唯一归属) 弱关联
- **现有防御**: HRG-PRE-03 (growth_lock_at <= now 跳过), 但 lock_at 怎么计算的? 是首次成集 + 30 天固定, 还是每次 merge 延长? 需要确认.
- **状态**: 🟡 — 取决于 lock_at 实现. demo 阶段 path A 单测覆盖 "锁后不进", 没覆盖"持续 merge 漂移".

---

## B 类 · 钻规则漏洞 (对抗性, 用户可能恶意/无意触发)

### B1 · 泛词 main_subjects 假阳 (subject stoplist 不完备)

- **触发**: 5 张完全不同场景的照片, L1 都给 main_subjects 包含 [thing, stuff, item] — stoplist **没收**这些近义词
- **路径**: 老 ADR-0023 Phase 4 subject single-layer → cov=1.0 → TH.1 strong, stoplist 未命中, MAX 取 strong
- **假阳原因**: stoplist 是字面匹配, 覆盖不全. 真实 L1 输出会用各种近义泛词
- **红线**: #5
- **现有防御**: ADR-0023 加了 stoplist (person/car/food/table/...), 但仅 12 个词
- **状态**: 🟡 — 已有机制, 词集需迭代. OQ-032

---

### B2 · TH.0 反向利用 (多并列簇凑 medium)

- **触发**: 用户故意混拍 2 个完全不同主题各 3 张 (eg. 上海开会 + 苏州游览), 让 theme 走 TH.0 medium 而非 weak
- **路径**: ADR-0022 TH.0 medium → 真值表 B 系列 (multi-medium 组合) 可能命中
- **假阳原因**: TH.0 把"完全无关 2 簇" 当 medium 看, 给了走 B 系列组合成集的门票
- **红线**: 设计 trade-off — TH.0 是为修 B5 单簇假 strong 加的, 但 medium 仍可能进真值表
- **现有防御**: B 系列要 medium ≥ 2 维, 单 theme medium 不够
- **状态**: 🟡 — 暂时 OK, 但若 event 也 TH.0 = medium, location 也 medium, 就过门槛了

---

### B3 · event activity 同 walk 凑 strong

- **触发**: 5 张完全不同 event (1 meal + 1 outing + 1 work + 1 gathering + 1 daily_record), 但 activity 都标 walk
- **路径**: E.1 要求 event_primary_share=1.0 + activity≥2/3. 此 case event_primary_share=0.2 < 1.0, 走 E.6 weak
- **假阳原因**: 看似能钻, 实际 E.1 要求 event 也一致, 钻不通
- **红线**: —
- **现有防御**: E.1 双重门槛设计良好
- **状态**: 🟢 已防御

---

### B4 · activity 全 walk + event 全 outing (合理的钻)

- **触发**: 5 张地理散乱但都标 event=outing + activity=walk
- **路径**: E.1 strong (event=1.0 + activity≥2/3) → A3 成集 type=event
- **假阳原因**: outing 跨度极大 (1 次散步 vs 1 次远足 vs 1 次出国), 全员 outing 不代表"同一次出游"
- **红线**: #5 弱关联
- **现有防御**: 无 — event 算法不验"事件单一性"
- **状态**: 🔴 未防御 — outing 类似 daily_record, 颗粒度太粗.

---

### B5 · time T1.5 凑 strong (events 3 紧邻)

- **触发**: 用户连拍 3 张, 各间隔 30 min → events=3 紧邻 (gap < 120min)
- **路径**: T1.5 升 strong (ADR-0011 修问题④断层)
- **假阳原因**: 3 张连拍可能只是同一场合不同角度, 真值表把它当"3 个事件" 升 strong 增强了误聚合
- **红线**: 弱违反"事件单一性"
- **现有防御**: T1.5 + 其他维度配合才进 A 系列, 单 time strong 不够 (但 A4 = time-strong + ... 是真值表入口)
- **状态**: 🟡 — 设计选择, 真实数据后看是否假阳率太高 (OQ-022)

---

### B6 · meaning_anchors 自由编

- **触发**: 5 张完全无关的照片, 用户/LLM 都塞 anchor "故乡" / "童年" / "外婆家"
- **路径**: AN.1 strong (anchor 全员一致) → 真值表 B/C 系列 (anchor 强单维不直接成集, 但加 location/theme 弱组合可能命中)
- **假阳原因**: anchor 是用户主观词, 没物理验证. 5 张说"故乡"不代表真在故乡拍
- **红线**: #8 (L1 落库即权威, 但 anchor 字段来源不可信)
- **现有防御**: ADR-0014 AnchorFeature 算 cluster 没限制 anchor 词来源
- **状态**: 🟡 — 真值表对 anchor 单独 strong 是要 LLM 复核, 不直接成集. 风险在 multi-medium 组合.

---

### B7 · location buffer 边界凑 medium

- **触发**: 5 张跨城市拍, 但最远 2 张距离 9.9 km (location buffer eps_outer = 1500m 已破, 但其他 3 张挤在中心 500m 内)
- **路径**: 主簇 K_outer=2 + 3 张紧簇 → A1.7 STRETCHED medium-high
- **假阳原因**: 同 city/省内, 但 5 张照片实际是 3 张在 A 区 + 2 张在 B 区 (相距 9 km), 应判 multi-cluster 而非 stretched
- **红线**: —
- **现有防御**: ADR-0010 PCA 形状校正 + transit 降档
- **状态**: 🟡 — 边界 case, 真实 GPS 噪声下难调

---

### B8 · N=2 假升 N=3 (上传重复绕过)

- **触发**: 用户上传 2 张, 但工程上重复一张 (photo_id 不同, EXIF 同) → 通过 HR-PRE-04 N≥3
- **路径**: N=3, 各维都 strong (实际是 1 张照片 ×2 + 第 3 张) → 成集
- **假阳原因**: photo_id 唯一不代表内容唯一. 重复内容应去重
- **红线**: #3 (2 张不成集)
- **现有防御**: L1 阶段应有去重, 但 demo 没实现 dedup
- **状态**: 🔴 未防御 — dedup 不在当前 demo 范围

---

### B9 · 跨日 EXIF 全 fallback (无时间证据)

- **触发**: 5 张全部 captured_at_source=upload_time_fallback (无 EXIF), 上传时间集中
- **路径**: HR-PRE-03 要求"全 fallback **且** 无 GPS" 才 suppress. 如果有 GPS 就不 suppress, time 走 fallback_ratio=1.0 → ADR-0011 T 路径仍出 weak
- **假阳原因**: 用户从云相册批量导入, 时间全是上传时间, 实际是不同日的照片. 算法当成同 batch.
- **红线**: —
- **现有防御**: HR-PRE-03 部分覆盖
- **状态**: 🟡 — 需 GPS 兜底, 真实数据上线后看

---

### B10 · LLM 复核钻 (主观说 strong)

- **触发**: backfill cascade BACKFILL-CAP-02 要求 LLM proposed_strength=strong. 真 Qwen LLM 在某些 prompt 下倾向乐观 → 给 strong
- **路径**: caps 全过 → create_new_album
- **假阳原因**: LLM 判断不稳定, 是软门槛
- **红线**: 无直接, 但 demo 阶段 LLM 调优期常见
- **现有防御**: temperature=0 + seed=42 确定性, 但 prompt 设计本身可能乐观偏好
- **状态**: 🟡 — 真实数据上线后必须看 LLM 判 strong 的比例 + 人工标注偏差 (OQ-031)

---

### B11 · is_high_frequency_place 误标

- **触发**: 用户家附近常去地点 (家/单位/早餐店), L1 没标 is_high_frequency_place=true (字段需要用户历史, demo mock 时漏标)
- **路径**: HR-BANDS-01 不触发 → location 不降档 → strong 直接进真值表
- **假阳原因**: 高频判定依赖用户历史, demo 阶段 mock 容易遗漏
- **红线**: #7
- **现有防御**: ADR-0006 双 density Plan A 实时计算, 但 demo 阶段 user_context=None 默认不判
- **状态**: 🔴 demo 期未防御 — v0.1 限制. 真实数据上线后接入 user_history.

---

### B12 · path A 弱命中阻断 path B strong

- **触发**: N=4 上传, path A 1 张命中老相册 (medium), 但 4 张 batch path B 整体 strong. 仲裁器 Case 1 优先级让 path A 赢, path B 整体作废
- **路径**: arbitration A>B>C, Case 1: path A 命中即 winner
- **假阳原因**: 牺牲了 B 路径的 batch strong 信号. 极端情况下, 1 张老相册命中 medium 摧毁 3 张新照片的 strong 成集
- **红线**: 无直接, 设计 trade-off
- **现有防御**: ADR-0017 严格 Case 优先级 + LLM_REJECT_DOWNGRADE 兜底
- **状态**: 🟡 — 设计选择 (避免相册边界漂移), 但产品层可能反直觉

---

### B13 · cascade outlier 占比过高仍 strong (2026-05-21 暴露)

- **触发**: cascade 召回流程合并新照片 + 候选 4 张一起跑 path B. 4 张里 2 张是 outlier (eg. l42 故宫 GPS 跟 3 张池 940km 跨城), 但 1 簇里剩 2 张紧簇 (l51-l52 1.5km) → PCA L=1.47km W≈0 → A1.5 LINEAR strong
- **路径**: ADR-0010 K_outer=1 grid 不限制 cluster_size_ratio. 主簇 2 张 + 2 outlier 仍触发 A1.5 (linear K_inner=1) → location strong → 真值表 A1 → bounds_max=strong → caps 全过 → create_new_album
- **假阳原因**: 主簇占总数 50% 时不该 strong (一半是 outlier 不能代表整批). 应有 cluster_size_ratio < 0.7 时 cap medium 或 weak
- **红线**: #5 弱关联 — 跨城被算法当一次旅行
- **现有防御**: 无. ADR-0010 A1 / B / A2 / A3 都不查 cluster_size_ratio
- **状态**: 🔴 **真 bug**, 已暴露 (`CB_08_li_gugong_cross_city_no_backfill` test fail). 候选 ADR-0025 加 cluster_size_ratio guard
- **修法**: ADR-0010 A1 grid 加约束 `主簇 size / N ≥ 0.7`, 否则 cap medium

---

### B14 · transit 降档失效 (2026-05-21 暴露)

- **触发**: 一日跨多景点 70 km (eg. T12_li_one_day_multi_spot_70km), 时序相邻照片距离 10km+ 时间 1h+ → transit ~10-15 km/h (步行+地铁混合, 低于 30 km/h 阈值)
- **路径**: ADR-0010 A3 transit_demote_kmh=30, 但实际跨城用地铁/公交 transit 速度可能 < 30 → 不降档. 8 张景点 → K_outer=2/3 → B 系列 medium → final medium
- **假阳原因**: 70km 一日跨城本身不该是 medium 单事件 — 多景点零散应 inline_hint
- **红线**: 无直接, 设计阈值问题
- **现有防御**: A3 transit≥30 降档, 但门槛太高
- **状态**: 🔴 **暴露** (`T12_li_one_day_multi_spot_70km` test fail). 跟 transit 阈值经验值有关 (OQ-022)
- **修法**: 调低 A3 阈值或加新约束 (eg. 总跨度 > 50km 时 cap weak)

---

## C 类 · 数据/语义陷阱 (L1 输出本身的偏差)

### C1 · Qwen embedding 跨语言弱

- **触发**: 5 张照片 theme_tags 中英混用 [lakeside, 湖, lake, 湖泊, waterside]
- **路径**: 真 Qwen3-Embedding 跨语言相似度仅 0.49-0.62 < cluster threshold 0.75 → 散簇 weak
- **假阳原因**: 应是同一主题但 embedding 不识别, 假阴 (不是假阳但是相关漏洞)
- **红线**: —
- **现有防御**: ADR-0020 v0.7 用同语言变体校准
- **状态**: 🟡 — 已知 limitation, 待 OQ-031 真实数据评估

---

### C2 · L1 prompt 漂移 (时间不一致)

- **触发**: 同一用户的照片, 今天 L1 给 theme_tags=[lake], 明天 [湖面, sunset]. 跨日 batch 时词集风格不一致
- **路径**: 同语义但 embedding 不一定收得回去
- **假阳原因**: 假阴的对偶 — 同对象但簇不聚
- **红线**: —
- **现有防御**: temperature=0 + seed=42 (确定性), 但 prompt version 升级会破
- **状态**: 🟡 — prompt version 锁定 + 老照片定期重判 (未实现)

---

### C3 · GPS 传感器漂移

- **触发**: 同一地点不同时间, 手机 GPS 漂 50-150m. 5 张同公园拍 → DBSCAN eps_inner=500m 应能合, 但边缘 case 可能分簇
- **路径**: location 多簇 + linear shape → A1 系列
- **假阳原因**: 假阴, 不是假阳
- **红线**: —
- **现有防御**: ADR-0010 buffer + eps_outer 1500m 兜底
- **状态**: 🟢 大体覆盖

---

### C4 · 同义词颗粒度跨例不一

- **触发**: A 用户拍同样的湖, L1 给 [lake, dock, sunset]; B 用户拍同样的湖, L1 给 [lakeside, pier, golden_hour]. cluster 不收
- **路径**: 个体看都对, 跨用户不可比
- **假阳原因**: 跨用户对比 (eg. cohort analysis) 时假阴
- **红线**: —
- **现有防御**: demo 阶段不做跨用户分析
- **状态**: 🟢 暂时无关 — 单用户内部 OK

---

### C5 · L1 文学化字段越界

- **触发**: L1 自由文字 individual_understanding 字段中描述了情绪/缺席 ("妈妈不在身边的下午"). semantic_facts.main_subjects 也可能进 "孤独感"
- **路径**: 红线 #1/#2 违反进入算法, EmotionalShape 可能 strong
- **假阳原因**: 红线靠 prompt 工程防, 不是算法防
- **红线**: #1 #2
- **现有防御**: ADR-0015 加了 `detected_inferred_emotion_count` 落痕, 但**不阻断**
- **状态**: 🟡 — 落痕 + LLM 复核, 不强 cap. OQ-026

---

## 总结 · 优先级建议

按"假阳概率 × 红线严重性" 排序:

| 优先级 | Case | 类型 |
|---|---|---|
| **P0** (必修) | A2 daily_record 弱关联凑集 | A |
| **P0** | A7 截图穿插 (字段缺失) | A |
| **P0** | B11 is_high_frequency_place demo 期未防御 | B |
| P1 (上线前) | A1 流水账类高频 | A |
| P1 | B1 泛词 stoplist 不完备 | B |
| P1 | B4 outing/daily_record 凑 strong | B |
| P1 | C5 emotional/缺席红线靠 prompt 防 | C |
| P2 (上线后调优) | A3 跨季同地点 | A |
| P2 | A5 多次同餐厅 | A |
| P2 | A8 相册续命漂移 | A |
| P2 | B5 time T1.5 连拍 | B |
| P2 | B10 LLM 主观强 | B |
| P3 (设计层) | A6 同 GPS 不同场景 | A |
| P3 | B2 TH.0 反向利用 | B |
| P3 | B12 path A 阻断 path B | B |

---

## 用法

1. demo 阶段: P0 + P1 case **必须**补 persona/scenario, 跑 invariants 验证
2. 真实数据上线后: P2/P3 case 进 OQ, 通过 grid search + 人工标注调参
3. 此文档跟 docs/12_open_questions.md 平行, 区别是: OQ 是"待决策", 本文档是"已识别风险"

---

## 相关引用

- CLAUDE.md 8 条产品红线
- docs/06_hard_rules.md (现有防御)
- docs/12_open_questions.md (待决策项)
- docs/27_persona_mock_realism.md (LLM 标签真实性)
- decisions/0022 (TH.0 修 B5)
- decisions/0023 (subject MAX-OR + stoplist)
