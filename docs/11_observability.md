# 11 · 决策落痕 / 可观测性

> 上线后排查 bad case 全靠这个。**不允许"内部计算不记录"**。
> 四种 log 对应四种路径/汇合 — 任何 L2 决策必有其一(或多个)落库。

## 落痕原则 (适用所有 log)

1. **每一 stage 必须有记录**, 即使被早返跳过也要标 `skipped: true` + reason
2. **policy_overrides 数组永远有**, 空数组 `[]` 也写出来, 便于排查
3. **不允许 silent fallback**: 任何"默认值兜底"必须打 override log
4. **score 永远在 final stage 出现**, 但 `display_decision` / `decision_tier` 不取决于 score, 仅看 strength/tier
5. **id 字段一律短 UUID** (`dec_xxxxxxxx` / `decg_xxxxxxxx` / `decb_xxxxxxxx` / `arb_xxxxxxxx`), 生产环境唯一

---

## 1. DecisionLog (路径 B · L2 主路径)

`src/contracts/decision.py::DecisionLog`

```python
{
  "decision_id": "dec_xxxxxxxx",
  "scenario": "batch_3_lakeside" | null,
  "path_taken": "path_B",

  "stages": {
    "step1_candidates": {
      "path_hint": "full_l2" | "light_judge_only" | "suppress_early_return",
      "photo_count": 3,
      "early_return_reason": null,          # all_sensitive / weak_fallback_time_only
    },

    "step2_features": {
      "location_score": 0.92,             # 派生展示, 真值表读 step3_bands.location
      "time_score": 0.85,
      "theme_score": 0.58,
      "event_score": 0.20,
      "people_score": 0.0,
      "anchor_score": 0.45,
      "emotional_score": 0.55,
      "is_high_frequency_place": false,
      "time_is_fallback": false,

      # ─── LocationFeature 子模型 (ADR-0010) ──────────
      "location": {
        "band": "strong",                  # ★ 直出, 真值表消费
        "rule_fired": "A1.6",              # 命中规则行
        "shape": "compact",
        "cluster_count_outer": 1,
        "cluster_count_inner": 1,
        "outer_length_km": 0.42,
        "outer_width_km": 0.15,
        "outer_ratio": 2.8,
        "convex_hull_diameter_km": 0.42,
        "trace_length_km": 0.5,
        "tortuosity": 1.19,
        "inter_outer_gap_km": null,
        "max_transit_kmh": 1.8,
        "outlier_count": 0,
        "score": 0.92,
      },

      # ─── TimeFeature 子模型 (ADR-0011) ──────────────
      "time": {
        "band": "strong",                  # ★ 直出, 真值表消费
        "rule_fired": "T1.5",              # "T1.5+near_eps_boundary" / "T3.1+k_days_uncertain"
        "shape": "extended_chain",
        "score": 0.9,                       # 派生展示
        "unique_days_count": 1,             # K_days
        "span_days": 1,
        "has_empty_days": false,
        "events_per_day": {"2026-05-15": 3},
        "max_events_in_any_day": 3,
        "total_span_hours": 8.5,
        "max_inter_cluster_gap_h": 2.5,
        "max_intra_cluster_span_h": 3.5,
        "has_overnight_chain": false,
        "has_dawn_photos": false,
        "near_eps_boundary_count": 0,
        "fallback_count": 0,
        "fallback_ratio": 0.0,
        "confidence": 1.0,
      },

      # ─── ThemeFeature 子模型 (ADR-0013 v0.3) ────────
      "theme": {
        "band": "strong",
        "rule_fired": "TH.2+secondary_boost",
        "shape": "dominant_themed",
        "score": 0.9,
        "primary_coverage": 0.8,
        "primary_theme_clusters": [["lakeside", "湖边", "lake"]],
        "primary_hit_rates": [0.8],
        "primary_outlier_ids": ["p5"],
        "secondary_coverage": 1.0,
        "secondary_action": "boost",
      },

      # ─── AnchorFeature 子模型 (ADR-0014 v0.3) ───────
      "anchor": {
        "band": "medium",
        "rule_fired": "AN.3",
        "shape": "partial_anchored",
        "score": 0.7,
        "primary_coverage": 0.6,
        "primary_anchor_clusters": [["天光", "阳光"]],
        "primary_outlier_ids": ["p4", "p5"],
        "secondary_coverage": 0.6,
        "secondary_action": "none",
      },

      # ─── EmotionalFeature 子模型 (ADR-0015 v0.2) ─────
      "emotional": {
        "band": "weak",
        "rule_fired": "EM.0",                # neutral_baseline preempt
        "shape": "neutral_baseline",
        "score": 0.4,
        "coverage": 1.0,                      # 即使 1.0, 但 neutral cap
        "primary_dominant_tone": "neutral",
        "is_neutral_baseline": true,
        "emotion_clusters": [["neutral"]],
        "detected_inferred_emotion_count": 0,  # 无红线违规
        "detected_inferred_emotions": [],
      },

      # ─── EventFeature 子模型 (ADR-0012) ─────────────
      "event": {
        "band": "strong",                  # ★ 直出, 真值表消费
        "rule_fired": "E.1",               # "E.1" / "E.2" / "E.7" 等
        "shape": "unanimous_event_activity",
        "score": 0.9,                       # 派生展示
        "total_photos": 5,                  # N
        "valid_event_count": 5,             # N_valid (event_hint != unknown)
        "unknown_share": 0.0,
        "primary_event": "meal",
        "primary_count": 5,
        "event_primary_share": 1.0,         # primary_count / N
        "secondary_events": [],
        "tertiary_events": [],
        "distinct_events": 1,
        "activity_primary": "meal",
        "activity_primary_count": 5,
        "activity_primary_share": 1.0,
        "used_activity_gate": true,          # E.1 双重门槛
        "used_activity_fallback": false,
      },
    },

    "step3_bands": {
      "location": "strong", "time": "strong",
      "theme": "medium", "event": "none",
      "people": "none", "anchor": "weak",
      "emotional": "medium",
    },

    "step4_truth_table": {
      "matched_pattern": "A1",
      "type": "location",
      "bounds_min": "medium",                # 输出约束: LLM 提议下限
      "bounds_max": "strong",                # 输出约束: LLM 提议上限
      "bands_snapshot": {                    # ★ 输入快照
        "location": "strong", "time": "strong",
        "theme": "medium", "event": "none",
        "people": "none", "anchor": "weak",
        "emotional": "medium",
      },
    },

    "step5_llm": {
      "proposed_type": "location",
      "proposed_strength": "strong",
      "semantic_reason": "...",
      "evidence_count": 3,
      "counter_evidence": "...",
      "confidence_adjustment": 0.05,
      "is_mock": true,
    },

    "step6_final": {
      "strength": "strong",
      "type": "location",
      "display_decision": "show_mini_album",
      "score": 0.78,                          # 仅监控, 不参与决策
      "primary_signal": "exif_location",
    },
  },

  "policy_overrides": [
    # {rule_id, before, after, reason}
  ],

  "decision_source": "policy_engine_with_llm_support" | "policy_override" |
                     "pre_filter_strong" | "pre_filter_reject" |
                     "truth_table_f1_suppress",

  "final_decision": { ... AssociationDecision ... }
}
```

---

## 2. GrowthDecisionLog (路径 A · 动态生长)

`src/contracts/growth.py::GrowthDecisionLog`

```python
{
  "decision_id": "decg_xxxxxxxx",
  "scenario": "growth_lakeside_continued" | null,
  "path_taken": "path_A",

  "new_photo_id": "lakeside_p004",
  "candidate_album_ids": ["ma_lakeside001", "ma_sunset002"],

  "per_album_evaluations": [
    {
      "album_id": "ma_lakeside001",
      "features": {
        "location_score": 1.0,            // 派生值, 实际分档看 location_match.band
        "theme_overlap_score": 0.89,      // 派生值, 实际分档看 theme_match.band
        "event_similarity_score": 0.9,
        "anchor_overlap_score": 0.66,
        "is_high_frequency_place": false,
        "location_match": {                // ★ DBCH 输出 (ADR-0005, 档位被 ADR-0007 临时统一)
          "band": "strong",
          "matched_target_type": "cluster",
          "matched_target_id": "c_lakeside_main",
          "diagnostics": {
            "cluster_id": "c_lakeside_main",
            "cluster_size": 3,
            "raw_distance_m": 0.0,         // 点在 hull 内
            "buffer_m": 150.68,            // ADR-0007: n=3, base=250 → ≈ 151m
            "effective_distance_m": 0.0,
            "context": "home_city",
            "band_table_used": "unified",  // ADR-0007; 回切后为 context 名
            "is_low_quality": false,       // ADR-0006, 实时判定结果
            "low_quality_reason": null     // signal_source: plan_a / frequency_failed / baseline_missing / disabled
          },
          "reason": ""
        },
        "theme_match": {                   // ★ 语义簇匹配输出 (ADR-0008)
          "band": "strong",
          "score": 0.89,
          "per_cluster": [
            {
              "representative": "lakeside",
              "frequency": 6,
              "weight": 0.6,
              "max_sim": 0.95,
              "matched_by": "lakeside",
              "contribution": 0.57
            }
            // ... 其他簇
          ],
          "reason": ""
        },
        "event_match": {                   // ★ event 三级分层匹配 (ADR-0009)
          "band": "strong",
          "matched_tier": "primary",       // primary | secondary | tertiary | none
          "diagnostics": {
            "new_event": "outing",
            "primary": "outing",
            "secondary": [],
            "tertiary": ["meal"]
          },
          "reason": ""                     // "unknown_event" / "empty_aggregation" / ""
        }
      },
      "bands": {
        "location": "strong",
        "theme": "medium",
        "event": "strong",
        "anchor": "medium",
      },
      "truth_table_match": {
        "matched_pattern": "G-A1",
        "type": "location",
        "decision_tier": "auto_merge",
        "bands_snapshot": { ... 4 维 ... },     # ★ 输入快照
      },
      "llm": {
        "accept": true,
        "semantic_reason": "mock:G-A1",
        "counter_evidence": "...",
        "is_mock": true,
      },
      "decision_tier": "auto_merge",
      "primary_signal": "exif_location",
    }
  ],

  "policy_overrides": [
    # 多相册冲突 / 高频降档 / LLM reject downgrade 等
  ],

  "final_decision": {
    "growth_decision_id": "gd_xxxxxxxx",
    "new_photo_id": "lakeside_p004",
    "decision_tier": "auto_merge",
    "merge_target_album_id": "ma_lakeside001",
    "primary_signal": "exif_location",
    "reason": "G-A1_auto_merge"
  }
}
```

**关键区别**: 路径 A 没有 bounds/clamp 概念,decision_tier 直接由真值表给出;LLM 只能选 accept/reject。

---

## 3. BackfillDecisionLog (路径 C · 兜底回扫)

`src/contracts/backfill.py::BackfillDecisionLog`

```python
{
  "decision_id": "decb_xxxxxxxx",
  "scenario": "backfill_sunset_chase" | null,
  "path_taken": "path_C",

  "new_photo_id": "sunset_chase_p004",
  "coarse_filter_candidates": ["sunset_chase_p001", "sunset_chase_p002", "sunset_chase_p003"],

  // ─── ADR-0017 新增: 维度强度总分排序落痕 (cascade_backfill_single 走时填) ───
  "priority_ranking": [
    {"photo_id": "sunset_chase_p001", "gps_within_1km": true, "theme_jaccard_above_0_5": true, "event_match": true, "score": 2.5, "selected": true},
    {"photo_id": "sunset_chase_p002", "gps_within_1km": true, "theme_jaccard_above_0_5": true, "event_match": false, "score": 2.0, "selected": true},
    {"photo_id": "sunset_chase_p003", "gps_within_1km": false, "theme_jaccard_above_0_5": true, "event_match": true, "score": 1.5, "selected": true}
  ],

  "main_truth_table_match": {
    "matched_pattern": "A3",
    "type": "event",
    "bounds_min": "medium",
    "bounds_max": "strong",
    "bands_snapshot": { ... },                # ★ 复用主表的 7 维快照
  },

  "llm_judgement": {
    "proposed_type": "event",
    "proposed_strength": "strong",
    "semantic_reason": "... | backfill_context: 这是兜底回扫场景...",
    "evidence": [...],
    "counter_evidence": "...",
    "is_mock": true,
  },

  "backfill_caps_applied": [
    {
      "rule": "BACKFILL-CAP-03-recall_count",
      "passed": true,
      "detail": "recalled=3, min_required=2"
    },
    {
      "rule": "BACKFILL-CAP-01-bounds_max_strong",
      "passed": true,
      "detail": "matched_pattern=A3, bounds_max=strong"
    },
    {
      "rule": "BACKFILL-CAP-02-llm_strength_strong",
      "passed": true,
      "detail": "proposed_strength=strong"
    }
  ],

  "policy_overrides": [],

  "final_decision": {
    "backfill_decision_id": "bd_xxxxxxxx",
    "new_photo_id": "sunset_chase_p004",
    "decision_tier": "create_new_album",
    "recalled_photo_ids": ["sunset_chase_p001", "sunset_chase_p002", "sunset_chase_p003"],
    "target_album_strength": "strong",
    "primary_signal": "event_hint",
    "reason": "backfill_A3_strong"
  }
}
```

**关键区别**:`backfill_caps_applied` 数组永远有,即使全过也写出来,便于排查"是哪条 cap 让 backfill 失败的"。

**ADR-0017 字段**: `priority_ranking` (`list[PriorityRankingEntry]`) — cascade_backfill_single 单次 cascade 后落痕**所有粗筛候选**的维度强度总分 + 是否进入 top 4. 老入口 `run_backfill_path` 单张 cascade 不填该字段 (兼容老 scenarios). 详见 [docs/23](./23_pipeline_cascade_backfill.md).

**ADR-0018 字段**: DecisionLog 加 `feature_assembler_plan: "L2_2.0" | "L2_1.0"` — 落痕 path B 7 维度算法版本 (L2 2.0 默认 / L2 1.0 v1.3 抄本 demo 对比). 详见 [docs/24](./24_feature_assembler_plan_ab.md).

---

## 4. ArbitrationResult (三路 + 仲裁最终输出)

`src/contracts/arbitration.py::ArbitrationResult`

```python
{
  "arbitration_id": "arb_xxxxxxxx",
  "scenario": "full_case1_add_to_album" | null,

  # 三路原始日志 (None = 未触发)
  "growth_log": { ... GrowthDecisionLog ... } | null,
  "l2_log": { ... DecisionLog ... } | null,
  "backfill_log": { ... BackfillDecisionLog ... } | null,    # 单张 N=1 走 C 时填

  # ─── ADR-0017 新增: 多张拆 N 张产物 ───
  "cascade_albums": [...],                    # cascade 产出的新相册 (可 0~N)
  "growth_merges": [                          # 拆 N 张走 A 加入老相册的记录
    {"photo_id": "p001", "target_album_id": "ma_xihu", "decision_tier": "auto_merge"}
  ],
  "settled_photo_ids": ["p004", "p005"],      # 拆 N 张 A C 都失败的 photos
  "cascade_logs": [                           # 各 P_i cascade 单次完整 log
    { ... BackfillDecisionLog for P_i ... }
  ],

  # 最终判决
  "arbitration_winner": "path_A" | "path_B" | "path_C" | "cascade" | "none",
  "ending": "add_to_existing_album" | "ask_user_confirm" |
            "create_new_album_path_b" | "create_new_album_backfill" |
            "create_multiple_cascade_albums" |              # ADR-0017
            "single_photo_sediment" | "ask_user_pending",

  "target_album_id": "ma_lakeside001" | null,
  "target_album_strength": "strong" | null,
  "user_facing_message": "那本《ma_lakeside001》又添了一笔",

  # 仲裁过程留痕
  "discarded_paths": ["path_C"],              # 被作废的路径
  "case_matched": "Case 1"                    # Case 1-8 (Case 5-8 = ADR-0017 多张拆 N 张)
}
```

**作废留痕**: `discarded_paths` 必须完整记录,避免事后争议"为什么 C 命中 strong 但没用"。例如 Case 1 命中时,即使 C 也命中 create_new_album,也要标 `discarded_paths=["path_C"]` 并保留 `backfill_log` 原文,只是不采纳其结论。

---

## 输出位置 (v0.1)

- **单元测试**: pytest assertion 直接对比 model
- **场景测试**: `tests/golden/<scenario>.expected.json` 比对完整 log
- **demo 脚本**: `scripts/run_demo.py` 把 log 打到 stdout (JSON pretty)

v0.2 计划:
- 接 structlog 写文件 + 落 PostgreSQL 决策日志表
- 加 trace_id 跨路径串联
- 加 metrics 出 Grafana (commitment_rate / suppress_rate / arbitration_case 分布)
