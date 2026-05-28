# Seenful Demo V2 — Schema 参考文档

> 来源：《登场识图知意 PRD v1.1》前五章对齐整理
> 用途：demo_v2 开发时的字段与逻辑基准，所有实现以本文档为准

---

## 目录

1. [L1 单图语义资产](#1-l1-单图语义资产)
2. [L2 关联记录](#2-l2-关联记录)
3. [Mini Album（小集）](#3-mini-album小集)
4. [状态枚举](#4-状态枚举)
5. [关键决策逻辑](#5-关键决策逻辑)

---

## 1. L1 单图语义资产

> 每张照片上传后，L1 视觉模型识图输出。是 L2 关联判断的上游输入。

```json
{
  "work_id": "work_xxx",
  "photo_id": "photo_xxx",
  "user_id": "user_xxx",

  "content_state": "generating | completed | failed | deleted",
  "display_state": "hidden | visible_new | visible_viewed",

  "source_batch_id": "batch_xxx | null",
  "source_session_id": "session_xxx | null",
  "uploaded_at": "2026-05-06T10:00:00+08:00",
  "captured_at": "datetime | null",
  "captured_at_source": "exif | upload_time_fallback",
  "captured_at_confidence": 1.0,

  "image_facts": {
    "width": 3024,
    "height": 4032,
    "exif_time": "datetime | null",
    "exif_location": "string | null",
    "exif_location_confidence": 1.0,
    "device_info": "string | null"
  },

  "place_signals": {
    "is_high_frequency_place": false,
    "place_frequency_count_30d": 1,
    "place_cluster_id": "place_xxx | null"
  },

  "l1_understanding": {
    "individual_title": "蓝天下的留白",
    "individual_understanding": "string (60-120字)",
    "meaning_anchors": ["天光", "树影", "慢下来"],
    "meaning_density": 0.78,
    "aesthetic_density": 0.64,
    "theme_tags": ["travel", "street", "slow_life"],
    "emotional_tone": "relaxed"
  },

  "semantic_facts": {
    "main_subjects": ["树影", "天光", "走路的人"],
    "scene_type": "home | park | travel | restaurant | street | indoor | outdoor | unknown",
    "activity": "walk | meal | gathering | sightseeing | gardening | resting | unknown",
    "people_presence": "none | single | group | family_like | unknown",
    "object_anchors": ["树枝", "光斑"],
    "place_category": "home_area | scenic_spot | community | road | restaurant | unknown",
    "event_hint": "meal | outing | gathering | celebration | performance | sports | work | study | daily_record | unknown"
  },

  "generation_affordance": {
    "daily_sign_score": 0.82,
    "album_cover_score": 0.76,
    "huabao_role": "hero | support | none",
    "nine_grid_role": "main_panel | support_panel | none",
    "recommended_styles": ["editorial_magazine", "travel_diary"]
  },

  "safety_flags": {
    "is_damaged": false,
    "is_duplicate": false,
    "is_document_sensitive": false,
    "is_child_related": false,
    "is_medical_related": false,
    "is_grief_related": false,
    "sensitive_level": "none | low | medium | high"
  },

  "memory_refs": {
    "event_log_id": "evt_xxx | null",
    "mini_album_id": "ma_xxx | null"
  },

  "is_deleted": false,
  "deleted_at": "datetime | null",
  "generation_version": "v1",
  "llm_version": "string",
  "vision_model_version": "string"
}
```

### semantic_facts 枚举速查

| 字段 | 枚举值 |
|---|---|
| `scene_type` | home / park / travel / restaurant / street / indoor / outdoor / unknown |
| `activity` | walk / meal / gathering / sightseeing / gardening / resting / unknown |
| `people_presence` | none / single / group / family_like / unknown |
| `place_category` | home_area / scenic_spot / community / road / restaurant / unknown |
| `event_hint` | meal / outing / gathering / celebration / performance / sports / work / study / daily_record / unknown (ADR-0009, 6→10 枚举) |

---

## 2. L2 关联记录

> L2 四层流程（代码 pre-filter → 代码 Feature Assembler → LLM Judge → 代码 Policy Engine）输出的完整记录。

```json
{
  "association_id": "assoc_xxx",
  "user_id": "user_xxx",
  "source_type": "batch_upload | rolling_window | dynamic_growth",
  "source_session_id": "session_xxx | null",
  "window_id": "window_xxx | null",

  "photo_ids": ["photo_1", "photo_2", "photo_3"],
  "l1_work_ids": ["work_1", "work_2", "work_3"],

  "score_breakdown": {
    "location_score": 0.10,
    "location_confidence": 0.0,
    "is_high_frequency_place": false,
    "time_score": 0.82,
    "time_confidence": 1.0,
    "theme_overlap_score": 0.66,
    "anchor_overlap_score": 0.58,
    "event_similarity_score": 0.70,
    "emotional_similarity_score": 0.62,
    "batch_intent_bonus": 0.08,
    "risk_flags": {
      "has_sensitive_photo": false,
      "gps_only_high_frequency": false,
      "time_only_fallback": false,
      "too_scattered": false
    }
  },

  "llm_judgement": {
    "proposed_type": "event",
    "proposed_strength": "medium",
    "semantic_reason": "string",
    "evidence": [
      { "photo_id": "p1", "evidence": "string" }
    ],
    "counter_evidence": "string",
    "confidence_adjustment": 0.05
  },

  "policy_overrides": [],

  "association": {
    "score": 0.61,
    "type": "location | temporal | event | thematic | emotional | visual | mixed | weak",
    "strength": "strong | medium | light | none",
    "primary_signal": "string",
    "primary_signal_confidence": 0.7,
    "reason": "string",
    "display_decision": "show_mini_album | show_inline_hint | suppress | merge_into_existing | ask_user_merge"
  },

  "decision_source": "policy_engine_with_llm_support | policy_override | pre_filter_strong | pre_filter_reject",

  "merge_decision": {
    "decision_tier": "auto_merge | ask_user | no_merge | not_applicable",
    "merge_target_album_id": "ma_xxx | null",
    "user_response": "accepted | declined | timeout | null",
    "user_response_at": "datetime | null"
  },

  "decision_reason": "string",
  "created_mini_album_id": "ma_xxx | null",
  "merged_into_mini_album_id": "ma_xxx | null",
  "created_at": "datetime",
  "generation_version": "v1"
}
```

### display_decision 枚举说明

| 值 | 含义 | 用户体验 |
|---|---|---|
| `show_mini_album` | 创建新记忆相册 | 生成标题 + 综述 + 圆圈展示 |
| `show_inline_hint` | 对话流轻提示 | 不成集，只在对话中轻轻一句 |
| `suppress` | 静默，不展示 | 无感知 |
| `merge_into_existing` | 自动并入已有相册 | 通知用户，"+N"微标 |
| `ask_user_merge` | 询问用户是否并入 | 喜宝发起询问 |

### 关联类型（8种）

| type | 含义 |
|---|---|
| location | 同一地点/路线 |
| temporal | 时间连续 |
| event | 同一事件 |
| thematic | 主题相近 |
| emotional | 情绪相近 |
| visual | 视觉气质相近 |
| mixed | 多因素轻关联 |
| weak | 关联较弱，不成集 |

---

## 3. Mini Album（小集）

> 工程内部技术名 Mini Album，团队内部叫"小集"，用户侧叫"记忆相册"。用户日常 UI 只显示具体标题，不出现统称。

```json
{
  "mini_album_id": "ma_xxxxxxxxxxxx",
  "user_id": "user_xxx",

  "content_state": "collecting | evaluating | generating | completed | failed | deleted",
  "display_state": "hidden | visible_new | visible_viewed | shared | visible_growing_new",

  "job_status": "queued | processing | succeeded | failed",
  "job_error_code": "string | null",
  "job_retry_count": 0,

  "source_type": "batch_upload | rolling_window",
  "source_session_id": "string | null",
  "source_association_id": "assoc_xxx",
  "trigger_condition": "batch | count_3_in_24h | window_expire",

  "created_at": "2026-05-06T18:00:00+08:00",
  "last_updated_at": "2026-05-06T18:00:00+08:00",
  "window_start_at": "datetime | null",
  "window_end_at": "datetime | null",
  "first_viewed_at": "datetime | null",

  "photo_count": 3,
  "max_photo_capacity": 30,

  "association": {
    "score": 0.72,
    "type": "location",
    "strength": "medium",
    "primary_signal": "exif_location",
    "reason": "这几张都在西湖周边，慢慢走的感觉"
  },

  "place_anchor": {
    "_comment": "DBCH 结构 (ADR-0005, 距离档位 v0.1 被 ADR-0007 临时统一)",
    "clusters": [
      {
        "cluster_id": "c_xxx",
        "member_photo_ids": ["photo_xxx"],
        "convex_hull": [[30.27, 120.13]],
        "centroid": [30.27, 120.13],
        "is_low_quality": false
      }
    ],
    "outliers": [],
    "is_high_frequency_anchor": false,
    "place_cluster_id": "place_xxx | null"
  },

  "theme_clusters": [
    {
      "_comment": "语义簇指纹 (ADR-0008, 见 docs/14)",
      "representative": "string",
      "members": {"string": 1},
      "frequency": 1,
      "centroid": [0.1, 0.2, "... dim 个 float"]
    }
  ],
  "theme_aggregated_at": "datetime | null",

  "cover": {
    "photo_id": "photo_xxx",
    "selection_reason": "meaning_density_peak | aesthetic_fallback | chronological_first"
  },

  "title": {
    "text": "西湖的午后",
    "tone": "literary | plain"
  },

  "synthesis": {
    "text": "string (50-80字)",
    "theme_mode": "thematic | temporal | emotional | mixed | location",
    "dominant_theme": "string | null",
    "emotional_arc": "string | null"
  },

  "growth": {
    "is_growing": true,
    "growth_lock_at": "2026-06-05T18:00:00+08:00",
    "growth_log": [
      {
        "added_at": "datetime",
        "added_photo_ids": ["photo_xxx"],
        "trigger_reason": "location_match | theme_match | mixed",
        "decision_tier": "auto_merge | ask_user",
        "association_score": 0.78,
        "primary_signal_confidence": 0.92,
        "user_notified": true,
        "user_notified_at": "datetime | null",
        "user_opened_after_notify": false
      }
    ],
    "excluded_photo_ids": [],
    "is_continuation": false,
    "continuation_of_album_id": null,
    "next_continuation_album_id": null
  },

  "photos": [
    {
      "photo_id": "photo_xxx",
      "origin_work_id": "work_xxx",
      "order": 1,
      "is_cover": true,
      "captured_at": "datetime | null",
      "added_via": "initial | dynamic_growth_auto | dynamic_growth_user_accepted",
      "added_at": "datetime",
      "individual_title": "string",
      "individual_understanding": "string",
      "meaning_anchors": ["string"]
    }
  ],

  "share_history": {
    "has_been_shared": false,
    "shared_snapshots": [
      {
        "snapshot_id": "snap_xxx",
        "render_version": 1,
        "shared_at": "datetime",
        "photo_count_at_share": 3,
        "title_at_share": "string",
        "synthesis_at_share": "string",
        "cover_photo_id_at_share": "photo_xxx"
      }
    ]
  },

  "regenerate": {
    "available": true,
    "used": false,
    "deadline_at": "datetime"
  },

  "render_version": 1,
  "is_deleted": false,
  "deleted_at": "datetime | null",
  "generation_version": "v1",
  "llm_version": "string",
  "vision_model_version": "string"
}
```

---

## 4. 状态枚举

### L1 Photo Semantic Asset

| content_state | display_state | 含义 |
|---|---|---|
| generating | hidden | L1 识图进行中 |
| completed | hidden → visible_new | 完成，首次展示 |
| completed | visible_new | 用户未看，NEW 标识 |
| completed | visible_viewed | 用户已看过 |
| completed | shared | 已分享 |
| failed | hidden | 失败，后台重试 |
| deleted | hidden | 已删除 |

### Mini Album

| content_state | display_state | 前端行为 |
|---|---|---|
| collecting | hidden | 不展示 |
| evaluating | hidden | 不展示 |
| generating | hidden | 不展示 |
| completed | visible_new | 圆圈 + NEW 标识，置顶 |
| completed | visible_viewed | 圆圈，无 NEW |
| completed | shared | 圆圈 + 已分享微标 |
| completed | visible_growing_new | 圆圈 + NEW + "+N" 微标，重新置顶 |
| failed | hidden | 不展示，后台重试 |
| deleted | hidden | 不展示 |

---

## 5. 关键决策逻辑

### 5.1 L2 四步流程

```
Step 1 · Candidate Builder（代码）
  决定哪些照片进入 L2 评估（≥3 张 或 rolling window 满足）
  ↓
Step 2 · Feature Assembler（代码）
  计算五维度客观信号 → score_breakdown
  ↓
Step 3 · LLM Judge（模型）
  输出 proposed_type + proposed_strength + evidence + counter_evidence + confidence_adjustment
  LLM 不输出 score 数值，不输出 display_decision
  ↓
Step 4 · Policy Engine（代码）
  加权计算 final_score，应用硬规则，输出 display_decision
  Policy Engine 强制执行，LLM 无权覆盖
```

### 5.2 五维度 strength 分级

| 维度 | 字段 | strong | medium | light | none |
|---|---|---|---|---|---|
| location（距离） | distance_grade | same_spot | nearby | far_nearby | different |
| location（重访） | revisit_strength | ≤30天 | ≤90天 | ≤365天 | >365天 |
| time（周年） | anniversary_strength | ±3天 | ±7天 | ±14天 | >14天 |
| person（重聚） | reunion_strength | ≤180天 | ≤365天 | ≤730天 | >730天 |
| theme（语义） | theme_strength | cos≥0.85 | ≥0.70 | ≥0.55 | <0.55 |

### 5.3 display_decision 触发条件

| display_decision | 触发条件 |
|---|---|
| `show_mini_album` | strength=strong/medium + Policy Engine 判定可成集（≥3张，非弱关联） |
| `show_inline_hint` | strength=light 或 type=weak，或 Policy Engine 降级 |
| `suppress` | 无信号 / 敏感照片 / 高频地点纯 GPS / 硬规则拦截 |
| `merge_into_existing` | 命中已有 is_growing=true 相册 + 高置信（GPS<200m 或 GPS<500m+主题叠加） |
| `ask_user_merge` | 命中已有相册 + 中置信（高频地点+主题叠加 / 仅主题匹配≥70%） |

**硬规则**（Policy Engine 强制，LLM 无权覆盖）：
- `weak` 类型 / `light` 强度 → 一律 `show_inline_hint`，不进圆圈相册区
- `sensitive_level >= medium` → 强制 `suppress`
- 高频地点 + 纯 GPS → 强制 `suppress`

### 5.4 L2.5 动态生长三档决策

| 信号组合 | 置信度 | 决策 |
|---|---|---|
| GPS < 200m + 非高频地点 | 高 | auto_merge |
| GPS < 500m + 非高频地点 + 主题/事件叠加 | 高 | auto_merge |
| GPS < 500m + 高频地点 + 主题或时间叠加 | 中 | ask_user |
| 仅主题匹配 ≥70%，无 GPS | 中 | ask_user |
| 仅 GPS < 500m + 高频地点，无其他信号 | 低 | no_merge |
| 仅上传时间接近（EXIF 缺失） | 低 | no_merge |
| 仅视觉气质相似 | 低 | no_merge |
| 敏感照片（sensitive_level ≥ medium） | 任意 | **强制 no_merge** |
| 用户曾从该相册移除 | 任意 | **强制 no_merge** |

### 5.5 多相册命中冲突优先级

```
1. GPS 完全匹配（< 200m）且非高频地点锚
2. 主题匹配且距离更近（创建时间更晚）
3. 时间上最近活跃（last_updated_at 最新）

一张新照片只能并入一个相册。
```

### 5.6 封面选择规则

```
Step 1: 按 meaning_density 降序
Step 2: 若最高分与次高分差值 < 0.05 → 按 aesthetic_density 降序（标记 aesthetic_fallback）
Step 3: 若差值仍 < 0.05 → 取时间最早一张（标记 chronological_first）
```

### 5.7 生长锁定规则

- **自然锁定**：created_at + 30天，自动 is_growing = false
- **容量锁定**：photo_count 达到 max_photo_capacity（默认30）
- **续集**：锁定后新照片继续匹配 → 创建续集相册，is_continuation = true

---

> 本文档对齐来源：《登场识图知意 PRD v1.1》§1-§5
> Demo 实现时，mock 数据须满足本文档所有字段定义和枚举约束
