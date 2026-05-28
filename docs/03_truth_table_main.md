# 03 · 主真值表 (路径 B)

> 28 条规则,按 **A → B → G → C → D → E → F1** 优先级查询,首条命中即返回。
> 来源:工程规范 v1.3.1。配置见 `config/truth_table_main.yaml`。

## 维度术语

- **主载体** (单独足以构成关联): location / theme / event / people
- **放大器** (单独不构成,叠加极强): time
- **辅证** (修饰作用): anchor / emotional

## bounds 语义

`bounds_min` / `bounds_max` 定义 LLM 输出 `proposed_strength` 的允许区间:

- `light`(对应 `weak` 强度) / `medium` / `strong` / `none`
- LLM 提议会被 Policy Engine clamp 到 `[bounds_min, bounds_max]`

---

## A 系列 · 任一主载体 = 强

| pattern | 触发条件 | bounds_min | bounds_max | type |
|---|---|---|---|---|
| A1 | location = 强 | medium | strong | location |
| A2 | theme = 强 | medium | strong | thematic |
| A3 | event = 强 | medium | strong | event |
| A4 | people = 强 | medium | strong | people |

> ⚠️ P0 阶段 people 上限 0.65,无法达"强",A4 在 v0.1 实质永不触发,但保留规则。

## B 系列 · 多主载体 = 中 (两两/三/四)

| pattern | 触发条件 | bounds_min | bounds_max | type |
|---|---|---|---|---|
| B1 | location=中 + theme=中 | medium | strong | mixed |
| B2 | location=中 + event=中 | medium | strong | event |
| B3 | location=中 + people=中 | medium | strong | people |
| B4 | theme=中 + event=中 | medium | strong | event |
| B5 | theme=中 + people=中 | medium | strong | people |
| B6 | event=中 + people=中 | medium | strong | event |
| B7 | location + theme + event 三者中 | strong | strong | mixed |
| B8 | 任三主载体 = 中 | strong | strong | mixed |
| B9 | 任四主载体 = 中 (全部主载体) | strong | strong | mixed |

> 注:B8/B9 仅在 B7 不命中且仍满足"三/四个主载体=中"时触发。优先级 B7 > B8 > B9。

## G 系列 · time 放大器

| pattern | 触发条件 | bounds_min | bounds_max | type |
|---|---|---|---|---|
| G1 | time=强 + 任一主载体 ≥ 中 + evidence 充分 | medium | strong | temporal |
| G2 | time=强 + 任一主载体 = 弱 + 辅证 ≥ 中 | light | medium | temporal |
| G3 | time=中 + 任一主载体 = 中 | medium | strong | temporal |
| G4 | time=中 + 任一主载体 = 弱 + 辅证 ≥ 中 | light | light | temporal |

> G1 特殊门槛:LLM evidence 质量分 ≥ 2 才允许 strong,否则封顶 medium。
> 具体门槛见 `08_llm_prompts.md` (v0.2),v0.1 mock 阶段默认不达标(封顶 medium)。

## C 系列 · 单主载体 = 中 + 辅证 ≥ 中×1

| pattern | 触发条件 | bounds_min | bounds_max | type |
|---|---|---|---|---|
| C1 | location=中 + 辅证 ≥ 中×1 | light | medium | location |
| C2 | theme=中 + 辅证 ≥ 中×1 | light | medium | thematic |
| C3 | event=中 + 辅证 ≥ 中×1 | light | medium | event |
| C4 | people=中 + 辅证 ≥ 中×1 | light | medium | people |

## D 系列 · 单主载体 = 中 (其他全弱/无)

| pattern | 触发条件 | bounds_min | bounds_max | type |
|---|---|---|---|---|
| D1 | location=中 (其他主载体全弱/无) | light | light | location |
| D2 | theme=中 (其他主载体全弱/无) | light | light | thematic |
| D3 | event=中 (其他主载体全弱/无) | light | light | event |
| D4 | people=中 (其他主载体全弱/无) | light | light | people |

## E 系列 · 多主载体 = 弱 + 辅证

| pattern | 触发条件 | bounds_min | bounds_max | type |
|---|---|---|---|---|
| E1 | ≥2 个主载体 = 弱 + 辅证 ≥ 中×2 | light | medium | mixed |
| E2 | ≥2 个主载体 = 弱 + 辅证 ≥ 中×1 | light | light | mixed |

## F1 · 兜底

| pattern | 触发条件 | bounds_min | bounds_max | type |
|---|---|---|---|---|
| F1 | 不命中以上任何 | none | none | weak |

→ 直接 suppress,跳过 LLM。

---

## 优先级实现细节

实现时按 **A→B→G→C→D→E→F1** 顺序遍历,首条命中即返回。同系列内按编号顺序(A1<A2<…)。

> ⚠️ **不允许"为了简化"合并规则**。即使 A1/A2/A3/A4 看起来对称,也必须分别命中并标注 `matched_pattern`。
