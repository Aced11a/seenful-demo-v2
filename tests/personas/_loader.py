"""Persona loader · 把精简 yaml 展开成完整 L1Output / MiniAlbumFingerprint.

参考: docs/25_persona_e2e_testing.md (ADR-0019)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.contracts import (
    Cluster,
    L1Output,
    MiniAlbumFingerprint,
    PlaceAnchor,
)
from src.contracts.event import EventAggregation
from src.contracts.l1_output import (
    ImageFacts,
    PlaceSignals,
    SafetyFlags,
    SemanticFacts,
)
from src.contracts.theme import SemanticCluster

PERSONA_DIR = Path(__file__).resolve().parent


class Persona:
    """加载完毕的 persona, 含 identity / life_events / active_state / photos / albums."""

    def __init__(self, raw: dict[str, Any]):
        self.persona_id: str = raw["persona_id"]
        self.identity: dict = raw.get("identity", {})
        self.life_events: list = raw.get("life_events", [])
        self.active_state: dict = raw.get("active_state", {})
        self.groups: dict = raw.get("groups", {})
        self._raw_photos: list[dict] = raw.get("photos", [])
        self._raw_albums: dict = raw.get("albums", {})

        # 索引: photo_id → L1Output
        self._photo_cache: dict[str, L1Output] = {}
        for p in self._raw_photos:
            l1 = self._build_photo(p)
            self._photo_cache[l1.photo_id] = l1

        # 索引: album_name → MiniAlbumFingerprint
        self._album_cache: dict[str, MiniAlbumFingerprint] = {}
        for name, spec in self._raw_albums.items():
            self._album_cache[name] = self._build_album(name, spec)

    # ─── 查询 ───────────────────────────────────────────

    def get_photo(self, photo_id: str) -> L1Output:
        if photo_id not in self._photo_cache:
            raise KeyError(f"photo {photo_id} not in persona {self.persona_id}")
        return self._photo_cache[photo_id]

    def get_photos(self, photo_ids: list[str]) -> list[L1Output]:
        return [self.get_photo(pid) for pid in photo_ids]

    def get_album(self, album_name: str) -> MiniAlbumFingerprint:
        if album_name not in self._album_cache:
            raise KeyError(f"album {album_name} not in persona {self.persona_id}")
        return self._album_cache[album_name]

    def photos_by_group(self, group: str) -> list[L1Output]:
        return [
            self._photo_cache[p["id"]]
            for p in self._raw_photos
            if p.get("group") == group
        ]

    def all_photos(self) -> list[L1Output]:
        return list(self._photo_cache.values())

    def distractor_photos(self) -> list[L1Output]:
        return self.photos_by_group("distractors")

    # ─── 构造 ───────────────────────────────────────────

    def _build_photo(self, spec: dict) -> L1Output:
        """精简 spec → L1Output (填默认 + 必要派生)."""
        # 时间戳: ISO string → datetime
        ts_raw = spec.get("ts")
        if isinstance(ts_raw, str):
            captured_at = datetime.fromisoformat(ts_raw)
        elif isinstance(ts_raw, datetime):
            captured_at = ts_raw
        else:
            captured_at = None

        # GPS
        gps_raw = spec.get("gps")
        gps = tuple(gps_raw) if gps_raw else None

        # SemanticFacts
        sf = SemanticFacts(
            main_subjects=spec.get("subjects", []),
            scene_type=spec.get("scene", "unknown"),
            activity=spec.get("activity", "unknown"),
            people_presence=spec.get("people", "none"),
            face_count=spec.get("face_count", 0),
            object_anchors=spec.get("object_anchors", []),
            place_category=spec.get("place_category", "unknown"),
            event_hint=spec.get("event", "daily_record"),
        )

        # ImageFacts
        img = ImageFacts(
            exif_location=gps,  # type: ignore[arg-type]
            exif_time=captured_at,
        )

        # PlaceSignals (高频地点标记)
        ps = PlaceSignals(
            is_high_frequency_place=bool(spec.get("hf", False)),
            place_frequency_count_30d=10 if spec.get("hf", False) else 0,
        )

        # SafetyFlags
        sensitive = spec.get("sensitive", "none")
        sf_flags = SafetyFlags(sensitive_level=sensitive)

        # narrative → individual_title + understanding
        narrative = spec.get("narrative") or "一张照片"
        title = narrative[:8] if len(narrative) >= 2 else "照片"
        understanding = (
            f"{narrative}, 这是一张普通的生活照片, 记录了当时的情景。"
            * 2  # 凑够长度
        )[:180]

        return L1Output(
            photo_id=spec["id"],
            captured_at=captured_at,
            individual_title=title,
            individual_understanding=understanding,
            meaning_anchors=spec.get("anchors", []),
            theme_tags=spec.get("theme", []),
            emotional_tone=spec.get("tone", "neutral"),
            semantic_facts=sf,
            image_facts=img,
            place_signals=ps,
            safety_flags=sf_flags,
        )

    def _build_album(self, name: str, spec: dict) -> MiniAlbumFingerprint:
        """精简 album spec → MiniAlbumFingerprint (ADR-0019 测试用)."""
        # PlaceAnchor (build DBCH with single cluster around gps_center)
        anchor_gps = spec.get("place_anchor_gps", [30.0, 120.0])
        radius_m = spec.get("place_anchor_radius_m", 100)
        # 简化凸包: 中心点四周 4 个角 + 闭合
        lat, lng = anchor_gps
        delta = radius_m / 111000.0  # 大约 m → degrees
        hull = [
            (lat - delta, lng - delta),
            (lat + delta, lng - delta),
            (lat + delta, lng + delta),
            (lat - delta, lng + delta),
            (lat - delta, lng - delta),     # 闭合
        ]
        cluster = Cluster(
            cluster_id=f"cluster_{name}",
            member_photo_ids=[f"ph_{i}" for i in range(5)],
            convex_hull=hull,
            centroid=tuple(anchor_gps),
            is_low_quality=spec.get("is_high_freq", False),
        )
        place_anchor = PlaceAnchor(
            clusters=[cluster],
            outliers=[],
        )

        # 主题簇 (维度跟 config/theme_aggregation.yaml 一致)
        from src.mini_album.theme_aggregation import get_embedder
        from src.policy.config_loader import load_config
        ta_cfg = load_config("theme_aggregation.yaml")["theme_aggregation"]
        embedder = get_embedder(ta_cfg)
        theme_clusters = []
        for c in spec.get("theme_clusters", []):
            rep = c["rep"]
            freq = c["freq"]
            centroid = embedder([rep])[0]
            theme_clusters.append(SemanticCluster(
                representative=rep,
                members={rep: freq},
                frequency=freq,
                centroid=centroid,
            ))

        # event_agg
        ea_raw = spec.get("event_agg", {})
        primary = ea_raw.get("primary")
        event_agg = EventAggregation(
            primary=primary,
            secondary=ea_raw.get("secondary", []),
            tertiary=ea_raw.get("tertiary", []),
            distribution={primary: 5} if primary else {},
            total_events=5,
        )

        created = datetime(2026, 3, 1)
        updated = datetime(2026, 3, 31)

        return MiniAlbumFingerprint(
            mini_album_id=f"ma_{name}",
            user_id="user_demo",
            title=spec.get("title", name),
            created_at=created,
            last_updated_at=updated,
            place_anchor=place_anchor,
            theme_clusters=theme_clusters,
            theme_aggregated_at=updated,
            event_agg=event_agg,
            event_aggregated_at=updated,
            anchors_set=spec.get("anchors_set", []),
            is_growing=True,
            growth_lock_at=datetime(2026, 5, 31),
            photo_count=spec.get("photo_count", 5),
            max_photo_capacity=30,
            excluded_photo_ids=[],
        )


def load_persona(persona_id: str) -> Persona:
    """加载 persona yaml. persona_id = 'laoqi_zhang' / 'laoli_youke'."""
    path = PERSONA_DIR / f"{persona_id}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Persona(raw)
