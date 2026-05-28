# 25 · Persona-based E2E Testing Framework (v0.6)

> 用户行为驱动的 e2e 测试. 算法依据: [ADR-0019 v0.6](../decisions/0019-persona-based-e2e-testing.md).
> **v0.6 (2026-05-20)**: 真 Qwen LLM 跑 (61/64 真接入) + HTML 看板加 3 个可视化工具 (📊时间轴 / 🗺GPS / 🏷标签云, 折叠按钮 lazy render).

> v0.2: 用户行为驱动 + 每张照片 unique 标签 + 3 persona.
> v0.3: 10 个旅游分布场景.
> v0.4: HTML 测试看板 + 6 补漏 scenarios.
> **v0.5 (2026-05-20)**: 补 14 L2.5 + 15 cascade scenarios (v0.4 暴露 L2.5/cascade 严重不足) + 加 **test_type 二分类** (red_line / robustness, Ace 拍板) + HTML 看板加 test_type 过滤. 总 64 scenarios, 路径覆盖 L2:34 / L2.5:15 / cascade:15.

## test_type 二分类 (v0.5 新增)

| 类型 | 含义 | 占比预估 |
|---|---|---|
| `red_line` | 基本功能, 各维度评分, 简单例子是否判断正确 | ~30% |
| `robustness` | 易错 / 干扰 / 边界 / 反例 | ~70% |

⚠ Ace 洞察 (2026-05-20): 红线测试**单测层面已充分覆盖** (ADR-0005~0018 各 ADR 都有 unit test). Persona-driven e2e 主要做**鲁棒性验证**.

scenario yaml 加 `test_type` 字段:
```yaml
test_type: red_line                  # 或 robustness
```

HTML 看板顶部加 toggle filter, 卡片 header 加 test_type 标签.

---

## 一、设计哲学

**用户行为驱动, 不是框架驱动**:
- ❌ 旧版 (v0.1): "为了测 location strong band, 设计 5 个 scenarios"
- ✅ 新版 (v0.2): "张奶奶被孙女抢手机自拍 3 张 → 戳一个鲁棒性痛点 → 验证算法是否捕捉产品意图"

**Expected 字段最小化**, 关心 invariants:
- 不验证 matched_pattern 细节
- 不验证 score 具体数字
- 验证: 算法行为不违反产品红线 (8 条 INV-01..08)

---

## 二、3 个 Persona

| Persona | 角色 | 照片数 | 时间线 | 重点模式 |
|---|---|---|---|---|
| `laoqi_zhang` (张奶奶 72 岁苏州) | 居家慢生活 | 43 | 40 天 | A.1-A.6 老人特有 |
| `laoli_youke` (李叔叔 58 岁上海) | 出差+旅游 | 50 | 40 天 | B.1-B.7 中年特有 |
| `xiaowang` (小王 28 岁上海) | 年轻爱拍 | 30 | 14 天 | C.3-C.8 年轻特有 |
| **总** | | **123** | | |

每张照片 unique 标签 (theme/event/tone/anchors/narrative), 同 group 内在共性 (语义簇可识别).

详细索引: [`tests/_PHOTO_CATALOG.md`](../tests/_PHOTO_CATALOG.md) (auto-generated)

---

## 三、18 个用户行为模式

| 群 | 模式 ID | 模式 | 算法应捕捉 |
|---|---|---|---|
| 老人 | A.1 | 保险式重复拍 30 秒 3 张 | 不错升 strong |
| 老人 | A.2 | 周期性散步 4 周 | 不强行成一集 |
| 老人 | A.4 | 突变自拍 (孙女抢手机) | 不污染老相册 |
| 老人 | A.5 | 商场反复来回 子区域 | 同 GPS 应聚 |
| 老人 | A.6 | 跟踪植物 30 天 | 持续记录 |
| 中年 | B.1 | 单点爆拍 + 顺路一张 | 长尾不丢 |
| 中年 | B.2 | 跨业务日 22:00→02:00 | 04:00 边界不切碎 |
| 中年 | B.3 | 中场长停顿 2-3h 午饭 | 不切集 |
| 中年 | B.5 | 出差 + 顺便游 | event 切换识别 |
| 中年 | B.6 | 送家人 + 回程 | 跨 location 同行程 |
| 中年 | B.7 | 接娃高频时间地点 | HR-POST-03 阻断 |
| 年轻 | C.3 | 网红打卡墙 30 秒 5 人 | 集体打卡识别 |
| 年轻 | C.4 | 餐厅一道菜 5 角度 | K_outer 不误判 |
| 年轻 | C.6 | GPS 漂移 ±150m | theme 兜底 |
| 年轻 | C.7 | 演唱会连拍 1 分钟 8 张 | T1.5 + activity 门槛 |
| 年轻 | C.8 | 同地不同主体 咖啡 vs 朋友 | 多维度博弈拆集 |
| 通用 | D.1 | 聚餐 + 截图穿插 | 截图过滤 |
| 通用 | D.2 | 医院敏感 | HR-PRE-02 强 suppress |
| 通用 | D.9 | 高频地点 + 强 event 家生日 | HR-POST-03 边界 |

---

## 四、19 个 Scenarios (1 模式 1 scenario, A.4 多 1 个)

详见 [`tests/_TEST_INDEX.md`](../tests/_TEST_INDEX.md) auto-generated 总览.

格式:
```yaml
name: "A.1 张奶奶保险式重复拍 3 张同物 30 秒内"
persona: laoqi_zhang
behavior_pattern: A.1
test_path: L2
product_intent: "3 张同物体不应被错误升 strong, 算法应识别为保险拍而非真 burst"
input:
  new_photos: [z02, z03, z04]
expected: {}                              # 不强求, 关心 invariants
invariants: [INV-01]                      # 弱关联绝不 create_new_album
```

---

## 五、Runner 设计

`tests/personas/test_persona_scenarios.py` 按 test_path 跑:
- `L2`: `run_l2_path_b(photos)` 路径 B 整批
- `L2.5`: `run_growth_path(photo, albums)` 路径 A 单张 vs 老相册
- `cascade`: `cascade_backfill_single(photo, pool)` 路径 C 回滚
- `full_l2`: 预留, 现 NotImplementedError (待 ADR-0020)

默认跑 8 条 invariants. spec 可指定 `invariants: [...]` 只校验某几条.

---

## 六、Photo Catalog 自动生成

```bash
python tests/personas/_gen_catalog.py    # 生成 tests/_PHOTO_CATALOG.md (123 张索引)
python tests/personas/_gen_index.py      # 生成 tests/_TEST_INDEX.md (测试总览)
python tests/personas/_gen_scenarios.py  # 重生 19 个 scenarios yaml
```

回答 Ace 关心: "编号找不到对应标签" 一目了然.

---

## 七、跑测试

```bash
# 跑全部 persona scenarios (19 个)
python -m pytest tests/personas/ -v

# 跑特定模式
python -m pytest tests/personas/ -k "B2" -v   # 跨业务日
python -m pytest tests/personas/ -k "C7" -v   # 演唱会连拍

# 跑总测试 (含 451 单测 + 19 persona scenarios = 470)
python -m pytest -q
```

---

## 八、不变性 / 8 条产品红线

详见 `src/test_utils/invariants.py`:
- INV-01: 弱关联绝不 create_new_album
- INV-02: sensitive_level >= medium 永远 suppress
- INV-03: 高频地点不能仅凭 GPS 自动并入
- INV-04: cascade 召回 ≥ 2 张才能成集
- INV-05: cascade strong-only
- INV-06: cascade 召回 ≤ 4 张
- INV-07: event 权重 0.5
- INV-08: plan A/B 切换 + DecisionLog 落痕

---

## 九、跟 ADR-0020 关系

ADR-0019 v0.2 (现) = **测试集真实化**, 算法逻辑不动.
ADR-0020 (待) = **真 LLM + Embedding + Amap 接入**.

接完 ADR-0020 后, 跑这 19 个 scenarios 看真 LLM 怎么判, 通过 `_gen_visual_report.py` 输出可视化报告.

---

## 十、关联

- [ADR-0019 v0.2](../decisions/0019-persona-based-e2e-testing.md)
- [tests/_PHOTO_CATALOG.md](../tests/_PHOTO_CATALOG.md) (auto-generated)
- [tests/_TEST_INDEX.md](../tests/_TEST_INDEX.md) (auto-generated)
- 外部参考: `D:/user/Downloads/喜宝记忆系统架构设计.md` (四层记忆架构)
