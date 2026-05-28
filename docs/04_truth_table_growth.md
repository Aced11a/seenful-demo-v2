# 04 · 动态生长真值表 (路径 A · L2.5)

> 10 条规则,按 `G-A → G-B → G-C → G-D → G-E → G-F1` 优先级查询,首条命中即返回。
> 配置: `config/truth_table_growth.yaml`
> 来源: Seenful_L1_L2_Full_Decision_Flow.md 路径 A · Step 4

## 与路径 B 的根本差异

| | 路径 B (L2 主) | 路径 A (动态生长) |
|---|---|---|
| 输入 | N 张新照片 | 1 张新照片 + 1 本"老相册"指纹 |
| 决策 | 是否成新集 | 是否并入老集 |
| 输出 | display_decision (show_mini_album / inline_hint / suppress) | decision_tier (auto_merge / ask_user / no_merge) |
| 候选维度 | 7 维 (location/time/theme/event/people/anchor/emotional) | 4 维 (location_match DBCH / theme_match 语义簇 / event_match 三级分层 / anchor_overlap) |
| 触发关系 | 用户上传后并行启动 | 用户上传后并行启动 |

## 候选集

只查满足以下条件的 `growing_albums`:
- `is_growing = true`
- `growth_lock_at > NOW()` (即 created_at + 30d 内)
- `photo_count < max_photo_capacity`
- 新照片 `photo_id NOT IN excluded_photo_ids`
- 新照片 `sensitive_level < medium`

## 维度计算 (vs 老相册"指纹")

新照片 P vs 老相册 album:

| 维度 | 计算 |
|---|---|
| `location` | DBCH match_new_photo(P.exif_location, album.place_anchor) → MatchResult.band (ADR-0005, v0.1 距离档位被 ADR-0007 临时统一) |
| `theme` | match_theme(P.theme_tags, album.theme_clusters) → ThemeMatchResult.band (ADR-0008, 见 docs/14) |
| `event` | match_event(P.event_hint, album.event_agg) → EventMatchResult.band (ADR-0009, 见 docs/15; 四档 strong/medium/weak/none) |
| `anchor_overlap` | jaccard(P.meaning_anchors / object_anchors, album.anchors_set) (OQ-009 §9d 仍待改) |

**分档**:
- `location` 直接读 MatchResult.band (跳过 score → band 转换, 见 ADR-0005)
- `theme` 直接读 ThemeMatchResult.band (跳过 score → band 转换, 见 ADR-0008; 阈值在 `config/theme_aggregation.yaml::band_thresholds`)
- `event` 直接读 EventMatchResult.band (跳过 score → band 转换, 见 ADR-0009; 三级分层 primary/secondary/tertiary → strong/medium/weak)
- `anchor` 仍用 `dimension_thresholds.yaml` 的强/中/弱/无阈值

**高频低质量地点降一档**: HR-BANDS-01 (ADR-0006 实时判定, location 分档时降, 见 docs/06)。

## 真值表 (10 条)

| pattern | 触发条件 | decision_tier | type |
|---|---|---|---|
| G-A1 | location=强 + (theme ≥ 中 OR event ≥ 中 OR anchor ≥ 中) | auto_merge | location |
| G-A2 | location=强 + 无主题/事件叠加 | ask_user | location |
| G-B1 | theme=强 + 无 location 矛盾(location ≠ 弱/none 之外的硬冲突) | auto_merge | thematic |
| G-B2 | event=强 + 无 location 矛盾 | auto_merge | event |
| G-B3 | anchor=强 + 无 location 矛盾 | auto_merge | anchor |
| G-C1 | location=中 + (theme ≥ 中 OR event ≥ 中) | auto_merge | mixed |
| G-C2 | location=中 + 仅 anchor=中 (无 theme/event 加持) | ask_user | location |
| G-D1 | 单一主载体 = 中,其他全弱/无 | ask_user | (按命中维度) |
| G-E1 | 多主载体 = 弱 + 辅证 ≥ 中×1 | ask_user | mixed |
| G-F1 | 不命中任何 | no_merge | weak |

### "无 location 矛盾"定义

B 系列规则的"无矛盾"条件:
- `location` band ∈ {`strong`, `medium`, `weak`, `none`} 都允许
- 真正硬冲突的判定靠 LLM 复核 (Step 5),Policy Engine 层不做

### 优先级

`G-A1 > G-A2 > G-B1 > G-B2 > G-B3 > G-C1 > G-C2 > G-D1 > G-E1 > G-F1`

## LLM Judge (Step 5 复核)

输入:新照片 L1 + 相册 theme_clusters (representative 列表) + 几张代表照片 L1
输出:是否真属于该相册 + evidence + counter_evidence
**约束**: LLM 只能在真值表给定 decision_tier 上下浮动 1 档,不能跨档。

v0.1 mock 阶段:`MockGrowthJudge` 直接返回 `accept=True`,evidence 占位。

## 后置硬规则

| ID | 规则 |
|---|---|
| HRG-POST-01 | 敏感照片(sensitive_level ≥ medium) → 强制 no_merge |
| HRG-POST-02 | 高频地点 + 无 theme/event 中以上 → auto_merge 降为 ask_user |
| HRG-POST-03 | 多相册命中冲突 → 按 location 优先 / 创建时间 / last_updated_at 排序,只入一本 |
| HRG-POST-04 | 容量已满 → 触发续集机制(v0.1 不实现) |
| HRG-POST-05 | excluded_photo_ids 命中 → 强制 no_merge (兜底, 候选集层应该已过滤) |

## Mini Album 指纹 (place_anchor / theme_clusters)

字段定义见 `src/contracts/growth.py::MiniAlbumFingerprint`. 各字段算法状态:

| 字段 | 算法 | 状态 |
|---|---|---|
| `place_anchor` (DBCH) | DBSCAN + 凸包 + buffer | ✅ ADR-0005 (v0.1 档位被 ADR-0007 临时统一) |
| `theme_clusters` | 语义聚类 + 频次加权匹配 | ✅ ADR-0008, 见 [docs/14](./14_theme_aggregation.md) |
| `event_agg` | 三级分层 (primary/secondary/tertiary) + 四档匹配 | ✅ ADR-0009, 见 [docs/15](./15_event_aggregation.md) |
| `anchors_set` | meaning + object 并集 (占位) | ⏳ OQ-008 §8e 待决 |
| 更新策略 | 增量 + 30 天冻结 | ⏳ OQ-008 §8h 待决 (theme 已由 ADR-0008 全量重算) |

v0.1 demo 用 `tests/fixtures/albums/*.json` 手填占位字段跑通流程; theme_clusters 用 mock embedding 表手填 centroid 值.

## 决策落痕 (GrowthDecisionLog)

```json
{
  "decision_id": "decg_xxx",
  "path_taken": "path_A",
  "new_photo_id": "photo_xxx",
  "candidate_albums": ["ma_aaa", "ma_bbb"],
  "per_album_evaluations": [
    {
      "album_id": "ma_aaa",
      "features": {
        "location_score": 1.0, "theme_overlap_score": 0.89,
        "location_match": { "band": "strong", "diagnostics": { ... } },
        "theme_match": { "band": "strong", "score": 0.89, "per_cluster": [ ... ] },
        ...
      },
      "bands": { "location": "strong", "theme": "medium", ... },
      "truth_table_match": "G-A1",
      "llm_judgement": { ... },
      "decision_tier": "auto_merge"
    }
  ],
  "final_decision": {
    "decision_tier": "auto_merge",
    "merge_target_album_id": "ma_aaa",
    "primary_signal": "exif_location"
  }
}
```
