# ADR-0022 · TH.0 多并列主簇 → medium (避免 TH.1 误判 mixed 主题为 thematic strong)

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-20 |
| 决策人 | Ace — 戳出 B5 (上海开会 3 张 + 苏州游 3 张) theme=strong 不合理 |
| 影响范围 | 改 `docs/19_path_b_theme.md` + 改 `config/path_b_theme.yaml` 加规则配置 + 改 `src/features/_two_tier_cluster.py` 加 TH.0 优先匹配 + `src/contracts/features.py::ThemeShape` 加新枚举值 + 改 `tests/unit/test_features_theme.py` 新增 TH.0 单测 + 跑回归 |
| 相关文档 | `docs/19_path_b_theme.md` |
| 关联 OQ | OQ-024 (ADR-0013 接受边界真实数据验证) |
| 关联 ADR | **修订** [ADR-0013](./0013-path-b-theme-two-tier-cluster.md) TH.1 触发条件 (加 `primary_cluster_count == 1`); **不 supersede** |

---

## 1 · 背景

B5 scenario 暴露 ADR-0013 真值表 TH.1 设计漏洞:

输入 (李叔叔上海开会 3 张 + 苏州游 3 张):
- l07/08/09 theme=[work/conference/badge/business/...]
- l10/11/12 theme=[zhuozheng/garden/suzhou/...]

真 Qwen Embedding 聚类后:
- 主簇 1: `[work, business]` 覆盖 3 张 (l07/08/09)
- 主簇 2: `[zhuozheng, suzhou]` 覆盖 3 张 (l10/11/12)
- **primary_coverage = 6/6 = 1.0** → TH.1 → **theme=strong** (thematic)

**算法判定**: 强主题相册 ❌

**真实语义**: 工作 + 旅游两个**完全不同**主题的混合, 不该被识别为强主题相册. 应是 **mixed medium**.

---

## 2 · TH.1 设计漏洞

ADR-0013 TH.1 当前定义:
```
TH.1: primary_coverage = 1.0 → strong (thematic)
```

**意图**: 所有照片都属于某主题簇 → 强主题型相册
**实际行为**: 任意几个并列簇加起来覆盖 100% 也触发 → 把多并列主题误判为单一主题

---

## 3 · 决策: 加 TH.0 规则

### 3.1 真值表加新规则 (优先于 TH.1)

```
TH.0: primary_cluster_count >= 2 AND primary_coverage = 1.0
      → medium (type=mixed)

TH.1: primary_cluster_count == 1 AND primary_coverage = 1.0  (新增约束)
      → strong (type=thematic)

TH.2 ~ TH.5: 不变
```

**优先级**: 真值表查表顺序 TH.0 → TH.1 → TH.2 → TH.3 → TH.4 → TH.5.

### 3.2 ThemeShape 加新枚举

`src/contracts/features.py::ThemeShape` 加:
- `MULTI_PARALLEL_CLUSTERS` — 多并列主簇 (TH.0 输出)

### 3.3 type 判定

TH.0 命中时:
- `theme_band = medium`
- `theme_type = mixed` (不是 thematic, 因为 LLM 看到的是混合主题)

---

## 4 · 配置 (`config/path_b_theme.yaml`)

加规则配置 (跟 ADR-0013 风格一致):

```yaml
path_b_theme:
  # 新增 TH.0 阈值
  th0_min_cluster_count: 2          # primary_cluster_count >= 此值 才能命中 TH.0
```

---

## 5 · Case 验证

### Case 1 · 单一主题 100% 覆盖 (TH.1 strong, 不变)
3 张照片都 [lake, water, sunset], 聚成 1 个簇覆盖 100% → strong ✓

### Case 2 · 双主题并列 100% 覆盖 (新 TH.0 medium)
6 张照片 = 3 张 work + 3 张 zhuozheng, 聚成 2 个并列簇覆盖 100% → medium (mixed) ✓
**(B5 case 修复)**

### Case 3 · 主题 80% + 1 张干扰 (TH.2 medium, 不变)
5 张 lake + 1 张 random, 主簇 1 个覆盖 80% → primary_coverage=0.8 → TH.2 ✓

### Case 4 · 三并列主题 100% 覆盖 (TH.0 medium)
9 张 = 3 work + 3 zhuozheng + 3 lakeside, 3 个并列簇覆盖 100% → medium ✓

---

## 6 · 不变量

1. **TH.1 加约束**: 必须 `primary_cluster_count == 1`, 不破坏旧测试 (TH.1 设计意图本就是单主题)
2. **TH.0 优先级最高**: 在所有 TH.x 之前查表
3. **TH.2-TH.5 不变**: 现 unit test 不影响
4. **medium 不是 weak**: 多并列主题仍有一定关联性 (都有意义的内容), 不该 weak/none

---

## 7 · 实施清单 (6 步)

1. ✅ 写 ADR-0022 (本文档)
2. ⏳ 改 docs/19_path_b_theme.md (加 TH.0 + 修 TH.1 描述)
3. ⏳ 改 config/path_b_theme.yaml 加 th0_min_cluster_count
4. ⏳ 改 src/contracts/features.py::ThemeShape 加 MULTI_PARALLEL_CLUSTERS
5. ⏳ 改 src/features/_two_tier_cluster.py TH 真值表加 TH.0 匹配
6. ⏳ 写 tests/unit/test_features_theme.py::TestTH0MultiParallel 单测 + 跑回归

---

## 8 · 关联

- [ADR-0013](./0013-path-b-theme-two-tier-cluster.md) (本 ADR 修订其 TH.1)
- [docs/19_path_b_theme.md](../docs/19_path_b_theme.md) (规范主文档)
- [ADR-0021](./0021-llm-label-realism.md) (LLM 真实多样性, 暴露此漏洞)
