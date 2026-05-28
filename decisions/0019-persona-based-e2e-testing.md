# ADR-0019 · Persona-based E2E Testing Framework (v0.6 真 Qwen 接入 + HTML 可视化)

| 字段 | 值 |
|---|---|
| 状态 | accepted (v0.6 真 Qwen + 可视化 2026-05-20) |
| 决策日期 | v0.1~v0.5 2026-05-19/20 / **v0.6 2026-05-20 真 Qwen 跑 + HTML 可视化** |
| 决策人 | Ace — v0.2 拍板: **用户行为驱动**, 不从测试框架反推; persona 标签真实化每张 unique; 老相册指纹 mock (aggregate 单测已覆盖); 18 个用户行为模式 |
| 影响范围 | **删除现 60 fixture-driven scenarios + 重写 2 persona + 新增第 3 persona** + 写 19 个用户行为驱动 scenarios + photo catalog 生成器 + 新 invariants + 改 `tests/personas/test_persona_scenarios.py` + 改 `docs/25_persona_e2e_testing.md` |
| 相关文档 | `docs/25_persona_e2e_testing.md`; 外部参考 `D:/user/Downloads/喜宝记忆系统架构设计.md` + `D:/user/Downloads/四层记忆协同关系说明.md` |
| 关联 OQ | 新增 OQ-030 (真实数据上线后扩 persona / 调 annotation) |
| 关联 ADR | **不 supersede** 任何; **扩展** ADR-0017 (cascade 干扰项验证) + ADR-0018 (plan A/B 各自跑 persona) |

---

## v0.2 修订背景 (Ace 2026-05-20 反复戳出的方向校正)

v0.1 的核心错误:
1. **框架驱动**: 从"维度 × band 5+5" 出发设计 60 个 scenarios → 偏离用户行为
2. **标签高度重复**: 阳台花 12 张 theme_tags / event / anchors 几乎一模一样, 不真实
3. **微抖动当随机性**: GPS ±0.001 / time ±10min 不是真用户多样性

v0.2 校正:
1. **用户行为驱动**: 从真实用户拍照行为出发, 每个 scenario 戳一个鲁棒性痛点
2. **每张照片 unique 标签**: 123 张照片每张 theme / anchors / tone 都不同, 但同 group 内有"内在共性" 让语义簇可识别
3. **3 个 persona 覆盖 18 个用户行为模式** (老人 5 + 中年 6 + 年轻 5 + 通用 2)

---

## 1 · 18 个用户行为模式 (核心矩阵)

### A · 老人特有 (张奶奶, 5 个)

| ID | 模式 | 算法应捕捉 |
|---|---|---|
| A.1 | 保险式重复拍 (30 秒 3 张同物) | 不应错升 strong |
| A.2 | 周期性散步 (跨 4 周同地同主题) | 周期记录不强行成一集 |
| A.4 | 被孙女抢手机自拍 | 突变照不污染老相册 |
| A.5 | 商场反复来回 (子区域) | 同 GPS 子区域应聚 |
| A.6 | 跟踪植物生长 30 天 | 跨长时同主题持续记录 |

### B · 中年特有 (李叔叔, 6 个)

| ID | 模式 | 算法应捕捉 |
|---|---|---|
| B.1 | 单点爆拍 + 顺路一张 | 长尾不丢 |
| B.2 | 跨业务日一日游 (22:00-02:00) | 04:00 边界不切碎 |
| B.3 | 中场长停顿 (午饭休) | 2-3 小时不切集 |
| B.5 | 出差 + 顺便游 | event 切换识别 |
| B.6 | 送家人 + 回程 | 同一行程跨 location |
| B.7 | 接娃高频时间地点 | HR-POST-03 阻断 |

### C · 年轻人特有 (小王, 5 个)

| ID | 模式 | 算法应捕捉 |
|---|---|---|
| C.3 | 网红打卡墙 (5 人 30 秒) | 集体打卡识别 |
| C.4 | 餐厅一道菜 5 角度 | K_outer 不误判 |
| C.6 | GPS 漂移 ±150m | theme 兜底 |
| C.7 | 演唱会连拍 (1 分钟 8 张) | T1.5 升 strong + activity 门槛 |
| C.8 | 同地不同主体 (咖啡 vs 朋友) | 多维度博弈拆集 |

### D · 通用 (跨 persona, 3 个)

| ID | 模式 | 算法应捕捉 |
|---|---|---|
| D.1 | 聚餐 + 截图穿插 | 截图过滤不污染 |
| D.2 | 医院敏感场景 | HR-PRE-02 强 suppress (红线 #6) |
| D.9 | 高频地点 + 强 event (家生日) | HR-POST-03 边界, 不过度抑制 |

---

## 2 · 3 个 Persona 设计

| Persona | 张数 | 时间线 | 角色 |
|---|---|---|---|
| `laoqi_zhang` (张奶奶 72 岁) | **43 张** | 40 天 | 居家慢生活, 高频地点多, 周期性散步 |
| `laoli_youke` (李叔叔 58 岁) | **50 张** | 40 天 | 出差+旅游, 跨城跨日, 接外孙女 |
| `xiaowang` (小王 28 岁) | **30 张** | 14 天 | 年轻爱拍, 演唱会 / 网红 / 徒步 |
| **总** | **123 张** | | |

每张照片**unique 标签** (theme / event / tone / anchors / narrative 各自有特性), 但同 group 内有内在共性 (语义簇可识别).

参考: `tests/_PHOTO_CATALOG.md` (auto-generated 索引表, 一目了然每张在测啥)

---

## 3 · 19 个用户行为驱动 Scenarios

每个 scenario:
- 戳**一个用户行为模式**
- 验证算法是否捕捉**产品意图** (不验证 matched_pattern / score 数字细节)
- 默认跑 8 条产品红线 invariants
- 期望字段 (expected) 多数为空, 关心**红线不被违反**

具体 19 个 scenarios:
- A.1-A.6 老人 5 个 + A.4 入 ask_user (HR-POST-03)
- B.1-B.7 中年 6 个
- C.3-C.8 年轻 5 个
- D.1/D.2/D.9 通用 3 个

详见 `tests/personas/scenarios/*.yaml` 19 个文件 + `tests/_TEST_INDEX.md`

---

## 4 · 关键设计原则

### 4.1 不真改记忆
runner 只跑算法入口, 不写库 / 不更新指纹

### 4.2 老相册指纹 mock (Ace 2026-05-20 拍板)
`aggregate_*` 算法已在 `tests/unit/test_*_aggregation.py` 充分覆盖, e2e 不需要真算 — 浪费算力. persona yaml 直接填指纹 (`place_anchor_gps` / `theme_clusters` / `event_agg`).

### 4.3 Expected 字段最小化
现 19 个 scenarios 大部分 expected={}, 关心 invariants. 这是**真实算法行为揭示**模式, 不是"测试 fit 算法".

### 4.4 多路径兜底预留
test_path 字段已支持 `full_l2` 但 runner 报 NotImplementedError, 未来扩展只需加 elif.

---

## 5 · 8 条产品红线 invariants 自动校验

`src/test_utils/invariants.py` 8 条:

| ID | 红线 |
|---|---|
| INV-01 | 弱关联绝不 create_new_album (红线 #5) |
| INV-02 | sensitive_level >= medium 永远 suppress (红线 #6) |
| INV-03 | 高频地点不能仅凭 GPS 自动并入 (红线 #7) |
| INV-04 | cascade 召回 ≥ 2 张才能成集 (PRD §3.10.4) |
| INV-05 | cascade strong-only (PRD §3.10.5) |
| INV-06 | cascade 召回 ≤ 4 张 (ADR-0017) |
| INV-07 | event 权重 0.5 (ADR-0017) |
| INV-08 | plan A/B 切换 + DecisionLog 落痕 (ADR-0018) |

---

## 6 · v0.2 跟 v0.1 对比

| 项 | v0.1 (2026-05-19) | v0.2 (2026-05-20) |
|---|---|---|
| 设计哲学 | 框架驱动 (维度 × band) | 用户行为驱动 (18 模式) |
| Persona 数 | 2 | 3 (加小王年轻人) |
| 总照片数 | 140 (60+80) | 123 (43+50+30) |
| 标签设计 | 同 group 高度重复 | **每张 unique** + 同 group 内在共性 |
| Scenarios | 60 (维度 × band 排列) | **19 个** (用户行为模式) |
| Expected | calibrate 填具体 matched_pattern | 多数为空, **关心 invariants** |
| 老相册指纹 | yaml 手填 | 同 (Ace #1 拍板 mock 即可) |
| Photo Catalog | 无 | **auto-generated 索引表** (你 #2 戳的) |
| 真实数据多样性 | GPS ±0.001 微抖动 | **行为级**多样 (扫射/跨日/漂移/穿插) |

---

## 7 · 实施清单 (10 步, v0.2 修订)

1. ✅ 删现 60 fixture-driven scenarios + 老 _gen / _calibrate / _REPORT
2. ✅ 重写 `laoqi_zhang.yaml` (43 张 unique 标签)
3. ✅ 重写 `laoli_youke.yaml` (50 张 unique 标签)
4. ✅ 新建 `xiaowang.yaml` (30 张 unique 标签)
5. ✅ 写 19 个用户行为驱动 scenarios
6. ⏳ 扩展 invariants (v0.2 暂沿用 8 条, 真实数据上线后再加专项)
7. ✅ `_gen_catalog.py` Photo Catalog 生成器
8. ⏳ 跑 `_gen_index.py` 更新索引 + 跑 `_gen_visual_report.py` (待 ADR-0020 真 LLM 接入)
9. ✅ 修订 ADR-0019 v0.2 + docs/25
10. ⏳ 更新 memory + 收尾

## 8 · v0.3 新增 (2026-05-20): 10 个旅游分布场景

**参考**: `D:/user/Downloads/旅游场景照片分布_测试参考.md` (21 个旅游场景)

挑选**核心 10 个** (Ace 拍板 #1/#3/#4/#7/#12/#13/#15/#18/#19/#20):

| ID | 场景 | 加在哪 | 新 group | 张数 | 算法挑战 |
|---|---|---|---|---|---|
| T.1 | 环西湖闭环 15km | 李叔叔 | xihu_loop | 8 | 闭环识别 (首尾近中间远) |
| T.3 | 步行街密度不均 | 李叔叔 | pedestrian_street | 6 | DBSCAN eps 难适配 |
| T.4 | 徒步前疏后密 | 小王 | hike_sparse_dense | 4 | 时间密度前后差异 |
| T.7 | 绕主体小环 | 李叔叔 | around_landmark | 6 | theme 压 location 小波动 |
| T.12 | 一日多景点 70km | 李叔叔 | multi_spot_one_day | 6 | 嵌套容器问题 |
| T.13 | Citywalk 低密度均匀 | 小王 | citywalk_uniform_low | 6 | DBSCAN 死穴 |
| T.15 | 跨年烟花跨业务日 | 小王 | fireworks_newyear | 8 | 极密 + 跨日 |
| T.18 | 网红跨城打卡 | 小王 | checkin_multi_spot | 5 | 单点信息密度低 |
| T.19 | 暴走 10 景点 | 李叔叔 | marathon_sightseeing | 10 | 防过度切分 |
| T.20 | 度假村躺平 3 天 | 李叔叔 | resort_lazy_3days | 5 | vs 高频地点核心区分 |

**新增**:
- 李叔叔: +41 张 (50 → 91)
- 小王: +23 张 (30 → 53)
- 总照片: 123 → **187 张**
- Scenarios: 19 → **29 个**
- 总测试: 470 → **480 通过**

## 9 · v0.4 新增 (2026-05-20): HTML 看板 + 6 补漏 scenarios

### 9.1 补漏 scenarios (6 个, Ace 戳出的)

| ID | 模式 | 算法挑战 | 加在哪 |
|---|---|---|---|
| T.21 | 连拍 5 张 1s + 1 张 30min 后 | time T1 链式切分 gap=120min 边界 | 小王 (burst_plus_gap) |
| T.22 | 跨自然日同事件 (周末露营 4/26-4/27) | 跨 2 个 04:00, ADR-0011 T2/T3 多日识别 | 李叔叔 (weekend_camping_crossday) |
| TH.1 | theme 颗粒度混合 (粗/中/细/感官 同地点) | 字面 Jaccard ≈ 0 但 ADR-0008 语义簇应识别 | 李叔叔 (theme_granularity_mix) |
| TH.2 | 单图多 strong theme (万圣节+晚宴+生日) | ADR-0013 双层判定 + main_subjects 多 strong | 小王 (multi_strong_theme) |
| ANC.1 | anchor 多颗粒 (meaning 抽象 + object 具体 4+) | ADR-0014 双层 anchor 边界 | 李叔叔 (anchor_multi_granularity) |
| EV.1 | event 多信号冲突 (celeb+meal+restaurant) | ADR-0012 primary_share + activity 二次门槛 | 张奶奶 (event_signal_conflict) |

照片数: 187 → **212 张** (张奶奶 46 + 李叔叔 104 + 小王 62)
Scenarios: 29 → **35 个**
总测试: 480 → **486 通过**

### 9.2 HTML 看板 (核心 UX 升级)

**单文件 `tests/_DASHBOARD.html`** (22KB, 零依赖, 浏览器直开):
- 顶部统计 (总数 / match / mismatch / 已通过 / 已标记)
- 分类 toggle (A/B/C/D/T/TH/EV/ANC × 状态 × 路径)
- 搜索框 (按 name/id)
- 每个 scenario 折叠卡片:
  - 🎯 产品意图
  - 🧠 用户记忆 (4 层架构)
  - 📷 输入照片 (含 narrative/theme/anchors/gps)
  - 📊 算法 7 维 bands (**每维点击展开量化原因** — rule_fired / shape / 聚类诊断)
  - 🤖 真值表 + LLM (proposed_strength / semantic_reason / evidence / counter_evidence)
  - 🎬 最终决定
  - ⚖ 期望 vs 实际对比
  - 🛡 Invariants 校验
  - 👤 **人工审核** (Approve / Flag / Reset + 备注, localStorage 持久化)

**数据源**: `tests/_dashboard_data.json` (290KB, 跑 `_gen_dashboard_data.py` 重生)

**可扩展性**:
- 数据/UI 解耦 (后端 dump JSON 加字段, 前端不破)
- CSS variables (主题切换)
- JS 模块化 (formatXxx 函数独立, 易加新 section)
- localStorage 隔离 (review 状态不污染 JSON)

### 9.3 跑命令

```bash
# 1. 生成数据
python tests/personas/_gen_dashboard_data.py

# 2. 浏览器打开 tests/_DASHBOARD.html (双击 / 拖入)
# 或本地起服务器:
python -m http.server 8000 --directory tests
# 浏览器访问 http://localhost:8000/_DASHBOARD.html
```

---

## 8 · 跟 ADR-0020 关系

ADR-0019 v0.2 是**测试集真实化** (persona + scenarios + invariants), 跟算法逻辑无关.
ADR-0020 (待开干) 是 **真 LLM + Embedding + Amap 接入**, 接完后跑 19 scenarios 看真行为.

两个 ADR 完全独立, 但 ADR-0019 v0.2 先做完, ADR-0020 跑出来的可视化报告才有意义.

---

## 9 · 验证

- ✅ `python -m pytest tests/personas/ -v` 19 scenarios 全过
- ✅ 总测试 470 通过 (含 19 persona scenarios + 451 单测)
- ✅ `tests/_PHOTO_CATALOG.md` 自动生成 123 张照片索引
- ✅ `tests/_TEST_INDEX.md` 自动生成测试总览

---

## 10 · 关联

**ADR**:
- 不 supersede 任何 ADR
- 扩展 ADR-0017 (cascade 干扰项) + ADR-0018 (plan A/B persona)

**文档**:
- [docs/25_persona_e2e_testing.md](../docs/25_persona_e2e_testing.md) (v0.2 修订)
- `tests/_PHOTO_CATALOG.md` (auto-generated 索引)
- `tests/_TEST_INDEX.md` (auto-generated 测试总览)

**外部参考**:
- `D:/user/Downloads/喜宝记忆系统架构设计.md` (四层记忆架构)
- `D:/user/Downloads/四层记忆协同关系说明.md`

**OQ**:
- 新增 OQ-030 (真实数据 + 真 LLM 上线后 review 算法实际行为)

---

## 10 · v0.5 修订 (2026-05-20): L2.5+cascade 补齐 + test_type 二分类

### 10.1 Ace 戳出的关键问题

> "现在的情景都是上传一组照片成集. L2.5 和回滚是单张的, 并没有过多测试啊"

**真实分布暴露 (v0.4 落地后):**

| Path | v0.4 数量 | 占比 | 问题 |
|---|---|---|---|
| L2 (整批) | 34 | 97% | 充分 |
| L2.5 (单张 vs 老相册) | 1 | 3% | 严重不足 |
| cascade (单张 vs 沉淀池) | 0 | 0% | **完全缺失** |

### 10.2 v0.5 补齐 29 个 scenarios

**Phase 1 · L2.5 单张 14 个**:

| 用户群 | scenarios |
|---|---|
| 老人 (张奶奶) | 阳台花 vs 阳台相册 / 公园新照 vs 公园相册 / 干扰自拍 vs 阳台 (反例) |
| 中年 (李叔叔) | 西湖新照 vs 西湖相册 / 故宫 vs 西湖 (跨城反例) / 接娃 vs 接娃相册 |
| 年轻 (小王) | 演唱会 vs 朋友相册 / 网红墙 vs 朋友相册 / 干扰 |
| 通用 | 截图 vs 任何相册 / 敏感 vs 老相册 / 多 theme vs 相册 / 颗粒度差 vs 相册 / 多 anchor vs 相册 |

**Phase 2 · cascade 单张 15 个**:

| 用户群 | scenarios |
|---|---|
| 老人 | 阳台花 vs 沉淀池 (相似) / 阳台花 vs 沉淀池 (无关) / 截图 vs 池 / 敏感 vs 池 |
| 中年 | 西湖新照 vs 沉淀池 (西湖类似) / 跨城 vs 池 (反例) / 跨业务日 vs 池 / 度假村 vs 池 / 暴走 vs 池 |
| 年轻 | 演唱会 vs 池 / 跨年烟花 vs 池 / 网红 vs 池 |
| 通用 | 单张 vs 空池 / 多 theme vs 池 / event 多信号冲突 vs 池 |

### 10.3 test_type 二分类 (Ace 拍板)

**所有 scenarios 加 test_type 字段**:
- `red_line`: 基本功能验证, 各维度评分清晰, 简单例子应判断正确 (eg. L2 整批清晰一致 → 应成集 / L2.5 同主题同位置 → 应 auto_merge)
- `robustness`: 易错 / 干扰 / 边界 / 反例 (eg. 干扰穿插 / GPS 漂移 / 多信号冲突 / 高频地点边界)

**Ace 洞察**: "红线测试在代码里测试了很多" — ADR-0005~0018 单测层面已覆盖各维度算法红线; persona-driven e2e 主要做鲁棒性验证.

预估分布 (v0.5):
- red_line: ~20 个 (基础正例 + 简单 L2.5/cascade)
- robustness: ~44 个 (边界 / 干扰 / 反例)

### 10.4 HTML 看板加 test_type 过滤

顶部 toolbar 加 "红线 / 鲁棒性 / 全部" toggle, 卡片 header 加 test_type 标签, 统计 pill 加"红线通过率".

### 10.5 v0.4 → v0.5 数据

| 项 | v0.4 → v0.5 |
|---|---|
| Persona 数 | 3 不变 |
| 照片数 | 212 → **可能加新照片支持新 scenarios** |
| Scenarios | 35 → **64** (+ 29) |
| Path 分布 | L2:34/L2.5:1/cascade:0 → L2:34/L2.5:15/cascade:15 |
| test_type 字段 | 无 → **red_line / robustness** |
| HTML 看板 | 无 test_type 过滤 | 加 |

### 10.6 CLAUDE.md 漏点补漏 (Ace 2026-05-20 强调"最重要")

- ✅ docs/12 加 OQ-030 (v0.4 引入但 v0.5 真落字) + OQ-031 (ADR-0020 引入真落字)
- ✅ docs/00 v0.5 链接更新 (本次)
- ✅ docs/25 加 test_type / L2.5+cascade 覆盖说明
- ✅ ADR-0019 v0.5 修订段 (本节)

---

## 11 · v0.6 修订 (2026-05-20): 真 Qwen 跑 + HTML 可视化

### 11.1 真 Qwen LLM 接入跑

`config/llm_settings.yaml::provider: mock → qwen` + `DASHSCOPE_API_KEY` env + `SEENFUL_LLM_MODE=real`:
- 64 个 scenarios 中 **61 个走真 Qwen** (qwen-turbo, no-thinking, temperature=0)
- 1 个 F1 兜底跳过 LLM (按设计)
- 1 个 mock 桩 (path A 走的 GrowthJudge 已切真, 但少数边界 case 走 G-F1 跳过)
- 1 个 API failed → graceful_degrade_to_mock 兜底 (按 ADR-0020 设计)

**实际成本**: ~1 美分 (qwen-turbo 极便宜).

### 11.2 HTML 看板加可视化 3 工具 (lazy render)

每个 scenario 卡片"输入照片"段下加 3 个**默认折叠按钮**, 点击才渲染 Canvas:

| 按钮 | 工具 | 渲染内容 |
|---|---|---|
| 📊 时间轴 | Canvas | 数轴 photo 排点, gap > 120min 标红 (ADR-0011 切分边界) |
| 🗺 GPS 分布 | Canvas | lat/lng 投影散点, 标 pairwise max distance |
| 🏷 主题标签云 | DOM tags | tag 字号 ∝ 出现次数, 跨张共享黄色高亮 |

**设计原则** (Ace 强调):
- **辅助信息**, 默认折叠
- 点击才渲染 (lazy, 不影响主性能)
- 零依赖 (vanilla Canvas + DOM, 不引 Chart.js / D3)
- 可扩展: 加新 viz 工具只需 viz-toolbar 加按钮 + renderXxx 函数

### 11.3 dashboard data 真 LLM 输出抽样

`A1_zhang_insurance_burst` (保险拍 3 张):
- proposed_strength: 真 Qwen 输出
- semantic_reason: "三张照片聚焦于兰花的特写" (中文真实)
- evidence: photo_id + 真实 evidence 文本
- is_mock: **false** (确认真接入)

### 11.4 文档同步

- ✅ ADR-0019 v0.6 修订段 (本节)
- ✅ docs/25 加 v0.6 真 LLM + 可视化说明
- ✅ docs/01 已加 ADR-0020 真 API 段 (v0.5 已补)
- ✅ docs/12 OQ-031 真 LLM 行为基线 (v0.5 已加)
