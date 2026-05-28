"""persona 精简照片 spec → 后端 l1Result JSON。

参考: SPEC.md §5(A/B/C/D 映射) + CLAUDE.md「L1 字段对齐」。
单一事实源: reference/l1_standard_sample.json(C 桶占位的基底) + reference/theme_tag_zh_map.json(B 桶翻译)。

只读 ../tests/personas/*.yaml 的**原始精简 spec**(不经 src/_loader,不碰 src 契约 —— CLAUDE 第0条)。
映射要点:
- A 直接搬: individual_*, meaning_anchors, semantic_facts.{main_subjects,scene_type,activity,people_presence,object_anchors,place_category,event_hint}
- B 改写: theme→ai_scene_tags(中文); face_count 提顶层; salient_objects ← main_subjects
- C 占位: 质量分/构图/affordance 等用样例 mock; safety_flags 布尔用字符串
- D 不传: GPS / captured_at(微信小程序环境拿不到)→ 样例本就无此键,不添加
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).resolve().parent
_SAMPLE_PATH = _HERE / "reference" / "l1_standard_sample.json"
_THEME_MAP_PATH = _HERE / "reference" / "theme_tag_zh_map.json"
_PERSONA_DIR = _HERE.parent / "tests" / "personas"

# C 桶:自由文本字段重置为通用占位(样例里是「小笼包」专属,挂到别的照片上不合适)。
# 数值质量分 / generation_affordance 保留样例 mock(合理占位,本台子不判其对错)。
_RESET_FREETEXT = {
    "best_photo_reason": "",
    "face_expression_detail": "",
    "ai_review_text": "",
    "suggested_improvement": "",
    "ocr_text": "",
    "ai_composition_tags": [],
}


def _is_chinese(s: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in s)


def load_sample() -> dict[str, Any]:
    return json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))


def load_theme_map() -> dict[str, str]:
    raw = json.loads(_THEME_MAP_PATH.read_text(encoding="utf-8"))
    return raw["translations"]


def load_persona_photos(persona_id: str) -> dict[str, dict]:
    """读 persona yaml,返回 {photo_id: 精简 spec}。persona_id 如 'laoqi_zhang'。"""
    path = _PERSONA_DIR / f"{persona_id}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {p["id"]: p for p in raw.get("photos", [])}


def load_persona_albums(persona_id: str) -> dict[str, dict]:
    """读 persona yaml 的 albums 指纹段(L2.5 setup 选种子时参考)。"""
    path = _PERSONA_DIR / f"{persona_id}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw.get("albums", {})


def translate_themes(
    themes: list[str], theme_map: dict[str, str], missing: set[str] | None = None
) -> list[str]:
    """英文 theme → 中文 ai_scene_tags。已是中文的透传;表里没有的占位透传 + 记 missing。"""
    out: list[str] = []
    for t in themes:
        if _is_chinese(t):
            out.append(t)
        elif t in theme_map:
            out.append(theme_map[t])
        else:
            if missing is not None:
                missing.add(t)
            out.append(t)  # 占位:保留原值待补译(已记入 missing)
    return out


def to_l1_result(
    spec: dict,
    *,
    theme_map: dict[str, str] | None = None,
    sample: dict[str, Any] | None = None,
    missing: set[str] | None = None,
) -> dict[str, Any]:
    """单张 persona 精简 spec → 后端 l1Result JSON(SPEC §5)。"""
    theme_map = theme_map if theme_map is not None else load_theme_map()
    l1 = copy.deepcopy(sample if sample is not None else load_sample())

    subjects = list(spec.get("subjects", []))

    # ── B 桶 ──
    l1["ai_scene_tags"] = translate_themes(spec.get("theme", []), theme_map, missing)
    l1["salient_objects"] = subjects                       # ← main_subjects 复制
    l1["face_count"] = spec.get("face_count", 0)           # 提到顶层

    # ── A 桶:semantic_facts 直接搬 ──
    sf = l1["semantic_facts"]
    sf["main_subjects"] = subjects
    sf["scene_type"] = spec.get("scene", "unknown")
    sf["activity"] = spec.get("activity", "unknown")
    sf["people_presence"] = spec.get("people", "none")
    sf["event_hint"] = spec.get("event", "daily_record")
    sf["object_anchors"] = spec.get("object_anchors", [])
    sf["place_category"] = spec.get("place_category", "unknown")
    sf.pop("face_count", None)                             # B:不再放 semantic_facts 里

    # ── A 桶:文字/锚点 ──
    narrative = spec.get("narrative") or "一张照片"
    l1["individual_title"] = narrative[:12]
    l1["content_brief"] = narrative
    l1["individual_understanding"] = (
        f"画面记录了{narrative}的瞬间,是一张日常生活照片。"  # 仅占位,内容不对齐(SPEC §5 A)
    )
    l1["meaning_anchors"] = list(spec.get("anchors", []))
    l1["emotional_tone"] = spec.get("tone", "neutral")     # 留观测,填法宽松(§5)

    # ── C 桶:自由文本重置;数值/affordance 保留样例 mock ──
    l1.update(copy.deepcopy(_RESET_FREETEXT))

    # ── C 桶:safety_flags(布尔用字符串)──
    sflags = l1["safety_flags"]
    sflags["sensitive_level"] = spec.get("sensitive", "none")

    # ── D 桶:GPS / captured_at 不传(样例本无此键,不添加)──
    return l1


def build_photo_list(
    specs: list[dict],
    *,
    theme_map: dict[str, str] | None = None,
    sample: dict[str, Any] | None = None,
    missing: set[str] | None = None,
    url_prefix: str = "https://example.com/mock",
) -> list[dict[str, Any]]:
    """一批 spec → API#1 的 photoList(每张 {l1Result, photoUrl})。"""
    theme_map = theme_map if theme_map is not None else load_theme_map()
    sample = sample if sample is not None else load_sample()
    out = []
    for spec in specs:
        l1 = to_l1_result(spec, theme_map=theme_map, sample=sample, missing=missing)
        out.append({
            "l1Result": l1,
            "photoUrl": f"{url_prefix}/{spec.get('id', 'photo')}.jpg",
        })
    return out
