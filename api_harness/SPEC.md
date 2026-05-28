# SPEC · Backend API E2E 测试台 (`api_harness/`)

> 状态: **草案 v0.1 · 待 Ace 确认**
> 目的: 用 mock L1 输入调后端同事的**真实 L2 逻辑**(HTTP + 落库 + 有状态),验证后端决策是否符合产品预期。
> 边界: **不动现有 `src/`**(只读参考)。本台子完全自包含在 `api_harness/` 下,有自己的 spec,不受 `docs/` 宪法约束(那套治理的是 `src/` 引擎)。

---

## 0. 一句话

```
旧:  mock 照片 → 跑我自己的 src/pipeline(静态、独立、不写库) → decision_log
新:  mock L1 + url → 调后端 HTTP API(有状态、落库、异步两段) → 后端决策结果 → 比对预期 → HTML 汇总
```

---

## 1. 后端接口(已知 + 待确认)

异步两段 + 清库,共 3 个 API。公共 header:`Content-Type: application/json` + `x-gateway-checked: 1`(非密,可硬编码)。

| # | 作用 | 端点 | 状态 |
|---|---|---|---|
| API#1 | 提交(mock L1 落库 + 触发关联) | `POST api-dev.haoduo.vip/api/v1/yxh-service/photo-meta/mockL1Finish` | ✅ schema 已拿到 |
| API#2 | 取结果 | `POST api-dev.haoduo.vip/api/v1/yxh-service/photo-meta/mockL1Result` | ✅ schema 已拿到 |
| API#3 | 删除(per-mockBizId 级联;后端或有额外配置触发整库清空) | `POST api-dev.haoduo.vip/api/v1/yxh-service/photo-meta/mockL1Result/del` | ✅ 端点确认,行为存在两种模式 |

### API#1 · mockL1Finish(已确认 2026-05-27)

**请求体**:
```jsonc
{
  "photoList": [
    { "l1Result": { /* 完整 L1 标准 JSON,见 §5;对象或字符串均可 */ },
      "photoUrl": "<非必须,可占位/省略>" }
  ]
}
```
- `photoList` 是 object[] → **一次可传多张**:L2 整批传 N 张;L2.5/cascade 传单张。
- `l1Result` = adapter 产出的完整 L1 JSON(§5);`photoUrl` 非必须 → 确认后端信任 `l1Result`,url 可占位。

**响应体**:
```jsonc
{ "mockBizId": <int64>, "photoMetaIds": [<int64>, ...], "userId": <int64> }
```
- `mockBizId`:本次提交的业务 id → 拿去 **API#2** 取结果(即 task_id)。
- `photoMetaIds`:后端给每张照片分配的 id(按 `photoList` 顺序对应)。
- `userId`:照片落库归属的用户 id。

⚠ **两条关键推论**:
1. **`photo_id` / `user_id` 不由我传,是后端分配后返回**。adapter 里的 mock photo_id 仅本地账本;真正用于链式引用(沉淀池、相册成员、召回照片)的是后端 `photoMetaIds`。runner **必须维护「本地 photo_id ↔ photoMetaId」映射**。
2. **state 怎么按 user 归拢?**(见 §9 头号 open)请求体没有 userId 入参,userId 是响应给的。那么同一 persona 的多次提交(先 L2 建集、再 L2.5 往里加)如何落到**同一 userId / 同一库**?不解决,"建集→往里加"的有状态时间线立不住。

### API#2 · mockL1Result(已确认 2026-05-27)

**请求体**:`{ "mockBizId": <int64> }`(API#1 返回的那个)。

**响应体(关键字段)**:
```jsonc
{
  "mockBizId": <int64>,
  "status": "<任务状态 → 轮询 pending/done 判据>",
  "route": "<后端实际走的路径 → 验 expected_path>",
  "displayDecision": <int>, "displayDecisionCode": "<码>", "displayDecisionDesc": "<人读>",  // 顶层决策
  "nextFlow": <int>, "nextFlowCode": "...", "nextFlowDesc": "...",
  "decisionSource": <int>, "decisionRemark": "...", "l2RecordId": <int64>, "userId": <int64>,
  "photos": [
    {
      "photoMetaId": <int64>,         // 对应 API#1 返回的某张
      "miniAlbumId": <int64>,         // ★ 落入的小集 id —— 链式验证靠它
      "decisionTier": <int>, "decisionTierCode": "...", "decisionTierDesc": "...",  // 每张决策档
      "finalResult": <int>, "finalResultCode": "...", "finalResultDesc": "...",
      "associationStrength": <int>, "associationScore": <num>, "associationType": <int>,
      "truthTablePattern": "<命中的真值表规则 → 验 matched_pattern>",
      "associationRecordId": <int64>, "candidateId": <int64>, "growthDecisionId": <int64>
    }
  ]
}
```

★ **关键:`photos[].miniAlbumId` 给到了** → L2.5/cascade 链式验证成立:
- **L2.5**:setup 种子批先成集拿到 `miniAlbumId_seed`;trigger 新照若 `miniAlbumId == miniAlbumId_seed` → 确实并进了那本集。
- **cascade**:数 trigger 后 `photos[]` 落入同一 `miniAlbumId` 的张数 → 验 recall(≥ min_recalled)。

⚠ **还缺枚举码值**:各 `*Code`/`*Desc` 是字符串(人读),但**具体码值清单**未知 —— `displayDecisionCode` 是 auto_merge/ask_user/no_merge/create…?`associationStrength` 整数怎么映 none/light/medium/strong?`status`/`route` 取值?**先靠首跑观测摸出**,或你补一份码值表(见 §9)。

### API#3 · mockL1Result/del(行为存在两种模式 · 2026-05-28 校准)

**请求体**:`{ "mockBizId": <int64> }`(字段必填,空体 400「mockBizId不能为空」)。

⚠ **行为有两种模式,目前以 per-id 为实施基础**:
- **默认观测(2026-05-28 airtight 实测)**:`del(X)` 级联删 X 的所有照片 + X 形成的小集;`del(Y)`(Y≠X) **不动 X**。即默认 = **per-mockBizId 级联删除**。
- **可能存在的整库清空**:Ace 与后端同事确认 del 可以"清除数据库",**后端或有额外配置/开关**触发整库 wipe(具体触发方式未知)。
- **runner 实施策略 = per-id 账本 teardown**:每次 submit 拿到 mockBizId 入账本,场景收尾逐个 `del(id)`。**在两种模式下都正确**(per-id 在 wipe-all 下也工作,只是多调用几次)。

**风险提示**:若后端整库 wipe 开关开着,harness 跑动时勿同时手测后端(任意一方的 del 会清掉对方的数据)。

✅ 历史:2026-05-27 首跑实测 del(X) 后 X 的 photos/小集消失,当时只有一次提交,无法区分两种模式;5-28 用"del 其他 id 不动 X"实测排除了"清全库默认开启"。

### 实测码值(2026-05-27 首跑 · 3 张食物图 L2 成集)

响应包装统一 `{ "data": { ... } }`。已观测:

| 字段 | 实测值 | 含义 |
|---|---|---|
| `status` | `PROCESSING` → `FINISHED`;删后 `NOT_FOUND` | 任务态;轮询等到非 `PROCESSING` |
| `route` | `L2` | 后端实际路径(验 expected_path) |
| `displayDecision` / `Code` / `Desc` | `1` / `show_mini_album` / `创建记忆影集` | 顶层决策 |
| `nextFlow` / `Code` / `Desc` | `1` / `l2_5` / `L2.5` | 下一步流转 |
| `decisionSource` | `5` | 决策来源 |
| `decisionRemark` | `policy_final_A2` | **真值表 pattern 在此**(`truthTablePattern` 字段本身空) |
| `photos[].finalResult` / `Code` / `Desc` | `2` / `create_mini_album` / `新建相册`(未处理时 `0`/`init`/`初始化`) | 每张最终结果 |
| `photos[].miniAlbumId` | `6`(三张同一本)| 落入的小集 id |
| `photos[].candidateId` / `associationRecordId` | int | 记录 id |
| `photos[].decisionTier*` / `associationStrength` / `truthTablePattern` | L2 下为空 | 预期 L2.5/cascade 才填,待观测 |

> 三张同主题(食物)无 GPS/time 仍成集(miniAlbumId=6)→ 印证 TEST_PLAN「theme 单维可跑」。

- **取结果**:已确认需**轮询 `pending → done`**(看 `status`,非 `PROCESSING` 即终态)→ client 带重试 + 间隔 + 超时。
- **路径判定**:已确认**后端按库状态自动判**。我**不**在请求里传 path;用响应 `route` 验"是否走了预期路径"。

---

## 2. 核心范式转变:静态独立 → 有状态有序

这是本次最大的复杂度来源。

| 维度 | 现在的 tests/ | 新 api_harness/ |
|---|---|---|
| 状态 | 无,每个 case 独立、不写库 | **落库累积**,每次上传改变库状态 |
| 路径 | yaml 里 `test_path` 显式指定跑哪条 | 后端**自动判**;`test_path` 降级为"我的预期路径" |
| 老集来源 | `persona.get_album()` 静态 fixture | 必须由**前置 L2 上传真实建出来** |
| 沉淀池来源 | `persona.get_photos(pool_ids)` 静态 | 必须由前置上传**真实落库**(单张未成集) |
| 执行 | 76 个独立调用,任意顺序 | **严格串行**,每场景一个隔离 session(setup→trigger→teardown 删本场景所有 mockBizId),组内自包含 |
| 取结果 | 同步返回 log | 异步:提交拿 task_id → 轮询取结果 |

**推论**: `test_path` 不再是"指令",而是"断言"——验证项之一是「给定当前库状态,后端是否走了我预期的那条路径」。

---

## 3. 测试流程:每场景一个隔离 session

> Ace 把隔离粒度交给我,框架定为:**L2 一批 / L2.5 先建集再测 / cascade 另起**;我据此取**每场景隔离**。API#3 默认 = **per-mockBizId 级联删**(2026-05-28 实测);可能存在的整库清空模式 pending(§1)。隔离实施 = **per-id 账本 + 收尾逐个删**(两种模式下都正确)。

开发环境单库自动累积,所以**必须严格串行**(并行会因后端如果整库 wipe 开关开着导致互相清掉),**每个场景跑成一个自包含的隔离 session**,按 path 分组(先 L2 组,再 L2.5 组,再 cascade 组):

```
for scenario in scenarios_by_group(L2, then L2.5, then cascade):
    if scenario.verdict == DEFERRED:
        scenario.result = DEFERRED(loc/time); continue   # 不发请求

    biz_ids = []                                  # 本场景账本

    # ── setup 阶段(仅 L2.5 / cascade)──
    if scenario.path == "L2.5":
        biz = API#1 提交(setup.seed_photos); biz_ids.append(biz.id)   # 老相册成员 → 应成集
        if not 轮询(biz).成集:
            scenario.result = BLOCKED(前置建集失败)
            for id in biz_ids: API#3 del(id); continue                # ← 失败归因 + 清理
    elif scenario.path == "cascade":
        biz = API#1 提交(setup.pool_photos); biz_ids.append(biz.id)   # 沉淀池落库(不自行成集)

    # ── trigger 阶段 ──
    biz = API#1 提交(trigger.photos); biz_ids.append(biz.id)
    scenario.result = 轮询 API#2(biz.mockBizId)
    比对 scenario.expected

    # ── teardown:逐个删本场景所有 mockBizId ──
    for id in biz_ids: API#3 del(id)

收尾: 出 HTML 汇总
```

**为什么每场景隔离 + 串行**:单库自动累积 → 不隔离的话后面场景看见前面残留,cascade 沉淀池被污染、L2 批次跨场景误并;每场景隔离 = 旧静态隔离语义 + 真后端。L2.5/cascade 的前置在**同一 session 内现建**,既测"建集"又测"加入/回扫",前置没建成 → 标 BLOCKED。**⚠ 后端若整库 wipe 开关开启,任意一方的 del 会清对方数据 → 跑动时勿同时手测**。

**场景 schema(草案)**:

```yaml
- id: zhang_L25_walk_to_walk
  source_scenario: L25_R2_zhang_walk_to_walk_auto_merge.yaml
  path: L2.5                       # 我预期后端走的路径(断言用,不传后端)
  verdict: runnable                # runnable | partial | deferred
  setup:                           # L2 场景留空
    seed_photos: [z_walk1, z_walk2, z_walk3]   # L2.5:建集种子(老相册成员)
    # pool_photos: [...]           # cascade:沉淀池
  trigger:
    photos: [z_walk_new]           # L2:整批 / L2.5:单张新照 / cascade:单张触发
  expected:
    decision: auto_merge           # 顶层决策(枚举见 §6)
    target: seed_album             # L2.5:并入刚 setup 建的那本集(运行时解析 album_id)
```

---

## 4. 76 场景 → 时间线的映射策略

> 逐场景的可跑性分类(✅ 可跑 / 🟡 部分 / ⛔ 延后)见 **`TEST_PLAN.md`**。本节只定策略,TEST_PLAN 定逐条落位。

按原场景的 `test_path` 分三类落位:

1. **L2 (batch / window)** → **状态构建者**。直接是时间线上的建集步骤,排在最前。它们的产物(album)被下游引用。
2. **L2.5 (growth)** → **加老集**。precondition = 某 album 已存在 → `depends_on` 指向建出该集的 L2 步骤。原 yaml 里的 `old_albums` 静态 fixture **改写成符号引用**前置步骤的 `produces_album`。
3. **cascade (backfill)** → **回扫**。precondition = 沉淀池照片已落库(单张、未成集)→ 时间线里先有"逐张上传沉淀池"的步骤,再上触发照片。
4. **FP_* (反例)** → 按其底层 path(L2/L2.5)归入对应类,期望沿用"不该成集/该 ask_user"等。

**最难的点**: 原来 album 是 yaml 里写死的 fixture id;现在必须"先真实建出来,再拿后端返回的 album_id 引用"。所以:
- expected 里的 `target_album` 用**符号名**(如 `zhang_album_lakeside`),**运行时**解析成"前置步骤实际返回的 album_id"。
- 这要求**响应体里能拿到 album_id**(见 §9 open item #3,关键)。拿不到就没法链式验证 L2.5/cascade。

**location 维度本轮延后(关键约束)**: 当前微信小程序环境拿不到 GPS/高频地点(§5 D),所以**以 location 为主导关联依据的场景本轮不真正测**——adapter 不传 GPS,后端在 location 上无信号。处理方式:
- 这类场景在 timeline 里标 `deferred: location`,**不发请求**,不计入 match/mismatch。
- 主要靠 **theme(`ai_scene_tags`)/ subject / event / emotional** 维度驱动的场景照常跑。
- 所有被延后的 location 场景,连同"将来拿到地理信息后该补什么 location 断言",由 §7 的 HTML 单独列出。

> 具体每 persona 的时间线 yaml,作为**实施第 2 步**产出(等 schema 确认后)。本 spec 只定策略。

---

## 5. 输入数据契约 (L1)

**单一事实源**: `reference/l1_standard_sample.json`(Ace 2026-05-27 提供的新 L1 标准样例)。`adapter.py` 与本节都引用它,不在多处各写一份。

`adapter.py` 把现有 persona 照片(旧 mock L1 结构)→ 新 L1 标准请求 JSON。映射规则(已与 Ace 对齐):

**A. 同名同义,直接搬**
`individual_title` / `individual_understanding`(仅占位,内容不对齐) / `meaning_anchors` / `meaning_density` / `aesthetic_density` / `semantic_facts.{main_subjects, scene_type, activity, people_presence, object_anchors, place_category, event_hint}` —— 枚举值与旧契约对得上。

**B. 替换/改写(已与 Ace 定稿 2026-05-27)**

| 旧字段 | 新字段 | 规则 |
|---|---|---|
| `theme_tags`(英文 snake_case) | `ai_scene_tags`(**中文**) | 参与后端主题维度;adapter 把英文 theme_tags **翻成中文**填入,经翻译表 `reference/theme_tag_zh_map.json`(Step 2 建,有歧义的译法问 Ace)。地名/地标按 ADR-0025 不进此字段。 |
| `semantic_facts.face_count` | 顶层 `face_count` | 提到顶层,`semantic_facts` 不再含它 |
| (新增) `salient_objects` | ← `semantic_facts.main_subjects` | 从 `main_subjects` 复制填(参与 subject 维度) |

**C. 全新字段,造合理 mock 占位**
`recognition_confidence, tqs, aqs, face_area_ratio, best_expression, eyes_open, ai_composition_tags, scene_category, color_mood, best_photo_reason, face_expression_detail, content_brief, ai_review_text, suggested_improvement, title_tone, ocr_text, generation_affordance.*`
- `safety_flags.*` 布尔用**字符串**(`"false"` / `"true"`),`sensitive_level` 用 `"none"/"low"/"medium"/"high"`(C 桶类型规则)。

**D. 旧有但新标准不传(当前微信小程序环境拿不到)**
- **`captured_at` / 时间**:删除,不传。
- **`exif_location` / GPS**、**`place_signals` / 高频地点**:不传。
- 后果:**location + time 维度本轮无法测**(见 §4 / §7 延后栏)。

**emotional_tone(留观测,填法宽松)**
- 新 L1 同时有 `color_mood`(画面色调)与 `emotional_tone`,二者在"画面氛围"语义上重叠。
- Ace 定:旧画面氛围词 / 样例情绪词**两种风格都可参考**,adapter 任填其一即可,本台子**不判其对错**。

**包装字段(不在 L1 体内,API#1 已明确)**
- adapter 产出的 L1 JSON 整体放进 `photoList[].l1Result`;每张外层只配一个 `photoUrl`(非必须,可占位)。
- `photo_id` / `user_id` **不传**:后端在响应里分配 `photoMetaIds` / `userId`(见 §1)。adapter 的本地 photo_id 仅用于场景内部引用,runner 负责映射到 `photoMetaIds`。

---

## 6. 期望与比对

- **expected 是产品意图基准,不因后端结果反改**(沿用「不改题目」纪律)。后端 ≠ 期望 = 暴露后端偏差,照实标 mismatch。
- **断言层级(旧 expected 字段 → API#2 实际字段)**:

  | 旧 expected | API#2 字段 | 断法 |
  |---|---|---|
  | `display_decision` | `displayDecisionCode`(顶层) | **必断**(码值映射待 §9 摸清) |
  | `expected_path` | `route` | 断后端是否走了预期路径 |
  | `matched_pattern` | `photos[].truthTablePattern` | 断命中的真值表规则 |
  | `decision_tier` | `photos[].decisionTierCode` | L2.5/cascade 每张决策档 |
  | `final_strength` | `photos[].associationStrength` | 关联强度(int→band 映射待 §9) |
  | `target_album` | `photos[].miniAlbumId` | **L2.5**:== setup 种子集的 miniAlbumId 才算并进去 |
  | `min/max_recalled` | 数 `photos[]` 落入同一 `miniAlbumId` 的张数 | **cascade**:≥ min_recalled |
  - 其余字段(score / 各 record id / desc)→ **raw 全量记录**,不强断。
- **多值期望 + acceptable 兜底**(沿用现有机制):
  - `decision: [ask_user, no_merge]` 任一通过;但**绝不允许把 no→merge 方向放宽**。
  - 意图是 `no_merge`/`auto_merge` 但结果 `ask_user` → 记为 **acceptable**(非 mismatch)。
- **失败归因**(每场景 session 内,关键):L2.5/cascade 的 trigger 结果不对时,先看 **setup 阶段**——
  - setup 种子批**没成集**(拿不到 miniAlbumId)→ trigger 步标 **BLOCKED(前置建集失败)**,不算 mismatch。
  - setup **成集了**但 trigger 仍判否 → 才是真 mismatch / 后端偏差。

---

## 7. 产出:HTML 汇总看板

- 按 **persona → 时间线** 展示;每步一行/一卡:`输入照片 | 期望路径 | 期望决策 | 后端实际 | match/acceptable/mismatch/BLOCKED`。
- 顶部过滤:按 persona、按 path(L2/L2.5/cascade)、按状态(mismatch/BLOCKED/deferred 高亮)。
- 失败归因显式标注上游链。
- 复用现有 `tests/_DASHBOARD.html` 的视觉风格与 3 档配色。
- **延后 location 专栏(必做)**:单独一栏列出本轮因拿不到 GPS/高频而**延后的 location 场景**,每条注明:
  - 原场景(溯源 76)、为什么需要地理信息、
  - **将来拿到地理信息后要补的 location 断言**(预期路径 / 预期决策 / 预期合并目标)。
  - 这一栏是"待办清单",不参与本轮 match 统计。

---

## 8. 目录结构 (`api_harness/`)

```
api_harness/
  SPEC.md               # 本文件
  CLAUDE.md             # 子项目宪法
  TEST_PLAN.md          # 77 场景可跑性分类
  config.py             # 读 endpoint/认证(全走环境变量,无明文)
  client.py             # 3 个 API 封装 + 轮询/重试/超时 + per-id 删除(API#3)
  adapter.py            # persona 照片 → l1Result(对 L1 新标准,§5)
  reference/
    l1_standard_sample.json   # L1 单一事实源
    theme_tag_zh_map.json     # theme_tags 英→中翻译表(Step 2 建)
  cases/                # 每场景一个 yaml(§3 schema),按 path 分组
    L2/  L2.5/  cascade/
  runner.py             # 串行:每场景 setup → trigger → 取结果 → 比对 → teardown 逐个删 mockBizId → 落 results/
  gen_dashboard.py      # results → 看板数据
  _DASHBOARD.html       # 浏览
  results/              # raw 响应 + 比对结果(gitignore)
```

---

## 9. Open Items(开跑前必须补齐)

> Ace 说 "API 的问题等下再说",以下大半待后续。✅ 已解决 / ⏳ 待补。

- ✅ **API#1 端点 + 完整请求/响应 schema**(mockL1Finish,见 §1)。`photoUrl` 非必须 → url 占位即可。
- ✅ **新 L1 字段标准** + A/B/C/D 映射定稿(见 §5,样例落 `reference/l1_standard_sample.json`)。
- ✅ **state 归拢**:开发环境单用户,数据自动落到**同一库**,**无需传 userId**。隔离**靠 per-id 账本 teardown**(不靠 userId 维度)。→ 串行 + 收尾逐个删,见 §3。
- ✅ **API#2 端点 + 请求/响应 schema**(mockL1Result,见 §1)。入参 `mockBizId`;**返回 `photos[].miniAlbumId` → 链式验证成立**。
- ✅ **API#3 端点;行为模糊**(mockL1Result/del):2026-05-28 实测 del(X) 级联删 X 的数据 / del(Y≠X) 不动 X → **默认 = per-mockBizId 级联**;Ace 与后端确认"可清数据库",**后端或有额外配置**触发整库 wipe(具体触发未知)。runner 取 per-id 账本 teardown(两种模式下都对)。
- ✅ **鉴权全集(2026-05-27 跑通)**:header `x-gateway-checked: true` + `x-permission-tenant: 92` + **`x-user-id: 16069`(关键,缺它则 500)** + `tenantinfo`;query `developerTest=1` + `sign`(走环境变量 `SEENFUL_SIGN`)。
- ✅ **枚举码值(首跑实测,见 §1 实测码值)**:`status` PROCESSING→FINISHED(删后 NOT_FOUND);`route=L2`;`displayDecisionCode=show_mini_album`;`finalResultCode` init(0)→create_mini_album(2);`nextFlowCode=l2_5`;`decisionRemark=policy_final_A2`(真值表 pattern 在此,`truthTablePattern` 字段空);包装 `{data:{...}}`。
- ⏳ **剩余待观测码值**:L2.5/cascade 的 `decisionTierCode` / `associationStrength`(int→band) / auto_merge·ask_user·no_merge 对应码;`displayDecisionCode` 全集。下一步跑 L2.5/cascade 用例时补。
- ⏳ **轮询参数**:首跑 interval=3s / timeout=120s 够用(FINISHED 几秒内到)。后续按实测收敛默认值。

---

## 10. 实施步骤(等你批准后逐步做,单步完成再下一步)

- **Step 1**: ✅ **完成(2026-05-27)** —— `config.py` + `client.py`(3 API + 轮询 + per-id del + SSL 重试)+ `step1_smoke.py`;最小 case「提交→轮询(FINISHED)→删除→复查」全跑通,鉴权全解、删除行为校准(5-28 实测 per-mockBizId 级联;整库 wipe 模式或在后端配置项,见 §1)、码值摸到。
- **Step 2**: `adapter.py` 对齐新 L1 标准;把 76 场景映射成 3 条 persona 时间线 yaml。
- **Step 3**: `runner.py` 跑完整时间线 + 失败归因。
- **Step 4**: `gen_dashboard.py` + `_DASHBOARD.html` 出汇总。
- **Step 5**: 全 76 覆盖核对 + 真后端跑通 + 偏差清单。

---

*v0.9 · 2026-05-28(同日校准)· **API#3 行为校准**:airtight 实测 `del(其他id)` 不动 X、`del(X)` 才删 X → 默认 **per-mockBizId 级联**;Ace 与后端再确认"可清数据库,后端或有额外配置"——两种模式并存。§1/§3 改回 per-id 账本 + teardown 逐个删(在两种模式下都正确);v0.8 的「整库 wipe」措辞作废。CLAUDE 第5条 / TEST_PLAN §5/§7 同步;client.py / runner.py 同改*
*v0.8 · 2026-05-28 · **【作废,见 v0.9】**API#3 行为更正(误判为整库清空)*
*v0.7 · 2026-05-27 · **Step 1 跑通**:鉴权全解(关键 `x-user-id: 16069`)、`{data}` 包装、删除级联实测确认(隔离干净)、首跑码值落 §1 实测码值表;§9/§10 相应更新*
*v0.6 · 2026-05-27 · API#3 mockL1Result/del 落入 §1:**按 mockBizId 删除**(非整库 wipe)→ §3 隔离改为「场景 teardown 删本场景所有 mockBizId」+ runner 记账本;§8 目录加 reference/ 与 cases/(替代 timelines/);待确认「删 mockBizId 是否级联删小集」*
*v0.5 · 2026-05-27 · API#2 mockL1Result 完整 schema 落入 §1(入参 mockBizId → photos[].miniAlbumId 等);album_id 链式验证成立,§6 比对层级改为旧 expected→API#2 字段映射表;§3 改为「每场景隔离 session(清库→setup→trigger)」,失败归因落到 setup 阶段;state 归拢=单库自动累积(§9 ✅)*
*v0.4 · 2026-05-27 · API#1 mockL1Finish 完整 schema 落入 §1(photoList/l1Result/photoUrl → mockBizId/photoMetaIds/userId);photo_id/user_id 后端分配,§5 包装字段更新;§9 新增头号 open「state 按 user 归拢」*
*v0.3 · 2026-05-27 · §5 L1 映射定稿:theme_tags→ai_scene_tags(中文/翻译表)、salient_objects←main_subjects、face_count 顶层、emotional_tone 宽松、包装字段待 API 传参;新增 TEST_PLAN.md 接入 §4*
*v0.2 · 2026-05-27 · 折入 L1 字段裁决(A/B/C/D)+ API#1/#2 文档 URL + header;location 维度本轮延后并入 HTML 待办;API 字段 schema 待 Ace 后续提供*
*v0.1 · 2026-05-27 · 初稿,等 Ace 确认 §9 open items 与整体方向*
