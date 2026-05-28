"""L1 单图理解输出契约。

参考: docs/02_data_contracts.md, SCHEMA_REFERENCE.md §1
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SceneType = Literal[
    "home", "park", "travel", "restaurant",
    "street", "indoor", "outdoor", "unknown",
]
Activity = Literal[
    "walk", "meal", "gathering", "sightseeing",
    "gardening", "resting", "unknown",
]
PeoplePresence = Literal[
    "none", "single", "group", "family_like", "unknown",
]
PlaceCategory = Literal[
    "home_area", "scenic_spot", "community", "road", "restaurant", "unknown",
]
EventHint = Literal[
    # ADR-0009: 10 枚举 (6→10). 删 family_visit/festival, 新增 6 个.
    # 见 docs/15_event_aggregation.md §一.
    "meal", "outing", "gathering", "celebration",
    "performance", "sports", "work", "study",
    "daily_record", "unknown",
]
SensitiveLevel = Literal["none", "low", "medium", "high"]
CapturedAtSource = Literal["exif", "upload_time_fallback"]


class SemanticFacts(BaseModel):
    """结构化输出 (给系统消费)."""
    main_subjects: list[str] = Field(default_factory=list)
    scene_type: SceneType = "unknown"
    activity: Activity = "unknown"
    people_presence: PeoplePresence = "unknown"
    face_count: int = 0
    object_anchors: list[str] = Field(default_factory=list)
    place_category: PlaceCategory = "unknown"
    event_hint: EventHint = "unknown"


class ImageFacts(BaseModel):
    width: int = 0
    height: int = 0
    exif_time: datetime | None = None
    exif_location: tuple[float, float] | None = None
    exif_location_confidence: float = 0.0
    device_info: str | None = None


class PlaceSignals(BaseModel):
    is_high_frequency_place: bool = False
    place_frequency_count_30d: int = 0
    place_cluster_id: str | None = None


class SafetyFlags(BaseModel):
    is_damaged: bool = False
    is_duplicate: bool = False
    is_document_sensitive: bool = False
    is_child_related: bool = False
    is_medical_related: bool = False
    is_grief_related: bool = False
    sensitive_level: SensitiveLevel = "none"


class L1Output(BaseModel):
    """L1 单图理解输出。v0.1 由 fixture mock 生成。

    ⚠ 文学化字段语义边界 (与 LLM prompt 双向钉死, 详见 docs/02_data_contracts.md
    §L1 文学化字段语义边界):
      - 不做情绪推断 / 不引用人的缺席 / 不出现机器词 / 不评价用户
      - 任一违反视为 P0 bug
    """

    photo_id: str
    user_id: str = "user_demo"

    captured_at: datetime | None = None
    captured_at_source: CapturedAtSource = "exif"

    # ─── 文学化输出 (LLM 生成, 易漂移, 字段语义严格) ──────────────────
    individual_title: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description=(
            "照片标题, 2-10 字中文. "
            "允许: 具体物象 / 场景细节. "
            "禁止: 机器词(AI/分析/识别/检测) / 美学打分(绝美/壮丽) / "
            "缺席的人(妈妈不在). "
            "正例: '湖边的午后' / '夕阳留白'. "
            "反例: 'AI 识别风景' / '高质量户外照片'."
        ),
    )
    individual_understanding: str = Field(
        ...,
        min_length=10,
        max_length=200,
        description=(
            "单图理解段落, 60-120 字中文, 第一人称或观察者视角. "
            "允许: 物象细节 / 时间感 / 空间感. "
            "禁止: 情绪推断(用户当时焦虑/沮丧) / 缺席人(妈妈不在身边) / "
            "机器词 / 宏大词(壮丽/绝美). "
            "正例: '走到亭子边, 柳枝从头顶垂下来…'. "
            "反例: '用户拍下了一张照片, 展示了用户当时的孤独…'"
        ),
    )
    meaning_anchors: list[str] = Field(
        default_factory=list,
        description=(
            "意义锚点列表, 1-5 个, 每个 ≤4 字. "
            "允许: 具体物象(天光/树影) / 抽象意象(慢下来). "
            "禁止: 评价词(美丽/好看) / 情绪词(开心/孤独). "
            "正例: ['天光','树影','慢下来']. 反例: ['美','好看','赞']."
        ),
    )
    meaning_density: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="意义密度自评, 0.0-1.0, 越高越值得记录.",
    )
    aesthetic_density: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="视觉密度自评, 0.0-1.0.",
    )
    theme_tags: list[str] = Field(
        default_factory=list,
        description=(
            "主题/场景/情境的英文短标签, 1-6 个, snake_case. "
            "禁止: 中文 / 美学评价 / 长句 / 情绪. "
            "正例: ['lakeside','slow_life','spring']. "
            "反例: ['美丽湖景','relaxed_user']."
        ),
    )
    emotional_tone: str = Field(
        default="neutral",
        description=(
            "画面情感氛围单字符串 (中/英文均可, 3-10 字). "
            "允许: 描述画面属性的氛围词. "
            "例: 静谧 / 诗意 / 怀旧 / 喧闹 / 温馨 / 戏剧化 / 极简 / 生机 / 神秘 / 喜庆 / "
            "relaxed / calm / awe / quiet / warm / busy / serene / nostalgic / poetic. "
            "默认: neutral (中性, 无明显氛围). "
            "禁止: 推断用户内心情绪. 反例: depressed / anxious / lonely / happy / sad / "
            "joyful / melancholic / 开心 / 悲伤 / 忧郁 / 焦虑 / 孤独. "
            "区分: '诗意' (画面属性, 允许) vs '开心' (用户情绪, 禁止). "
            "符合产品红线 §1 '不做情绪推断' (ADR-0015 v0.2 扩开放词典)."
        ),
    )

    # 结构化输出
    semantic_facts: SemanticFacts = Field(default_factory=SemanticFacts)

    # 位置 / 高频
    image_facts: ImageFacts = Field(default_factory=ImageFacts)
    place_signals: PlaceSignals = Field(default_factory=PlaceSignals)

    # 安全
    safety_flags: SafetyFlags = Field(default_factory=SafetyFlags)

    # 便捷访问 (从 image_facts / place_signals / safety_flags 派生)
    @property
    def exif_location(self) -> tuple[float, float] | None:
        return self.image_facts.exif_location

    @property
    def is_high_frequency_place(self) -> bool:
        return self.place_signals.is_high_frequency_place

    @property
    def sensitive_level(self) -> SensitiveLevel:
        return self.safety_flags.sensitive_level
