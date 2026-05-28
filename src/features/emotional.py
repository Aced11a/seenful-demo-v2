"""路径 B Emotional 维度 (ADR-0015): 开放字段 + 单层语义聚类 + neutral baseline.

参考:
  docs/21_path_b_emotional.md
  decisions/0015-path-b-emotional-single-tier-cluster.md
  config/path_b_emotional.yaml

输出: EmotionalFeature (含 band 终值 + neutral baseline 诊断 + 红线落痕)

⚠ 字段开放: emotional_tone: str. L1 prompt 引导, 算法层不硬校验.
⚠ EM.0 preempt: 主簇代表词=neutral 强制 cap weak.
⚠ 红线落痕不阻断: 推断情绪词 (happy/sad/...) 仍进 distribution, 仅 detected_inferred_* 落痕.
⚠ 复用 ADR-0013 _two_tier_cluster.build_two_tier_feature(enable_secondary=False).
"""
from __future__ import annotations

from src.contracts import EmotionalFeature, EmotionalShape, L1Output
from src.policy.config_loader import load_config

from ._two_tier_cluster import TwoTierResult, build_two_tier_feature


# ─── shape_code → EmotionalShape 映射 ──────────────────────


_SHAPE_MAP: dict[str, EmotionalShape] = {
    "EM.1": EmotionalShape.UNANIMOUS_EMOTION,
    "EM.2": EmotionalShape.DOMINANT_EMOTION,
    "EM.3": EmotionalShape.MIXED_EMOTION,
    "EM.4": EmotionalShape.SCATTERED_EMOTION,
    "EM.5": EmotionalShape.NO_EMOTION_SIGNAL,
}


def _band_to_score(band: str) -> float:
    return {"strong": 0.9, "medium": 0.7, "weak": 0.4, "none": 0.1}[band]


# ─── 字段抽取器 ──────────────────────────────────────────────


def _emotional_primary_extractor(p: L1Output) -> list[str]:
    """主字段: emotional_tone (单值). 包成 list[str] 兼容 _two_tier_cluster 接口."""
    tone = p.emotional_tone
    if not tone:
        return []
    return [tone]


def _emotional_secondary_extractor(p: L1Output) -> list[str]:
    """次字段占位: emotional 无次字段, 返回空 list (但 enable_secondary=False 会跳过)."""
    return []


# ─── 红线诊断 + neutral baseline 检测 ────────────────────────


def _detect_inferred_emotions(
    photos: list[L1Output],
    blacklist_cn: list[str],
    blacklist_en: list[str],
) -> tuple[int, list[str]]:
    """统计违反红线"不做情绪推断" 的 photo 数 + 出现的违规词.

    黑名单合并 (中英). 大小写不敏感 (英文).
    """
    blacklist = set(blacklist_cn) | {t.lower() for t in blacklist_en}
    detected_words: set[str] = set()
    count = 0
    for p in photos:
        tone = p.emotional_tone or ""
        norm = tone.lower() if tone.isascii() else tone
        if norm in blacklist:
            count += 1
            detected_words.add(tone)
    return count, sorted(detected_words)


def _primary_dominant_tone(
    result: TwoTierResult,
) -> str | None:
    """从 TwoTierResult 算主簇代表词.

    主簇 = primary_theme_clusters 中 hit_rate 最高的簇.
    代表词 = 簇里第一个 tag (字典序确定性).
    """
    if not result.primary_theme_clusters or not result.primary_hit_rates:
        return None
    max_idx = max(
        range(len(result.primary_hit_rates)),
        key=lambda i: result.primary_hit_rates[i],
    )
    cluster = result.primary_theme_clusters[max_idx]
    if not cluster:
        return None
    return sorted(cluster)[0]  # 字典序最小, 确定性


# ─── 高层入口 ────────────────────────────────────────────────


def build_emotional_feature(photos: list[L1Output]) -> EmotionalFeature:
    """从 photos 构造 EmotionalFeature (ADR-0015 直出 band).

    流水线 (docs/21 §2.1):
      Phase 1: 红线诊断 (落痕, 不阻断)
      Phase 2: 单层语义聚类 (复用 _two_tier_cluster, enable_secondary=False)
      Phase 3: 6 行 grid 判定 (EM.0 neutral preempt 优先)
    """
    cfg = load_config("path_b_emotional.yaml")["path_b_emotional"]

    # ─── Phase 1: 红线诊断 (落痕, 不阻断) ──────────────────
    blacklist_cfg = cfg.get("inferred_emotion_blacklist", {})
    detected_count, detected_words = _detect_inferred_emotions(
        photos,
        blacklist_cn=blacklist_cfg.get("chinese", []),
        blacklist_en=blacklist_cfg.get("english", []),
    )

    # ─── Phase 2: 调通用工具单层聚类 ───────────────────────
    result: TwoTierResult = build_two_tier_feature(
        photos=photos,
        primary_extractor=_emotional_primary_extractor,
        secondary_extractor=_emotional_secondary_extractor,
        cfg=cfg,
        rule_prefix="EM",
        enable_secondary=False,
    )

    # ─── Phase 3: EM.0 preempt + 6 行 grid 后处理 ──────────
    primary_tone = _primary_dominant_tone(result)
    neutral_cfg = cfg.get("neutral_baseline", {})
    neutral_enabled = bool(neutral_cfg.get("enabled", True))
    neutral_token = str(neutral_cfg.get("neutral_token", "neutral"))
    cap_band = neutral_cfg.get("cap_band", "weak")

    is_neutral = (
        neutral_enabled
        and primary_tone == neutral_token
        and result.band != "none"  # none 段不 cap (已经最低)
    )

    if is_neutral:
        result.band = cap_band
        result.rule_fired = "EM.0"
        shape = EmotionalShape.NEUTRAL_BASELINE
    else:
        shape = _SHAPE_MAP[result.shape_code]

    return EmotionalFeature(
        band=result.band,
        rule_fired=result.rule_fired,
        score=_band_to_score(result.band),
        total_photos=result.total_photos,
        valid_photo_count=result.valid_photo_count,
        tag_pool_size=result.primary_tag_pool_size,
        cluster_count=result.primary_cluster_count,
        emotion_clusters=result.primary_theme_clusters,
        hit_rates=result.primary_hit_rates,
        coverage=result.primary_coverage,
        outlier_photo_ids=result.primary_outlier_ids,
        primary_dominant_tone=primary_tone,
        is_neutral_baseline=is_neutral,
        detected_inferred_emotion_count=detected_count,
        detected_inferred_emotions=detected_words,
        shape=shape,
    )
