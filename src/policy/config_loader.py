"""配置加载器 (单例,支持运行时热替换以便测试).

参考: docs/07_dimension_thresholds.md
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@lru_cache(maxsize=8)
def load_config(filename: str) -> dict[str, Any]:
    """读取 config/<filename>。缓存,测试中如需重载请 cache_clear。"""
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clear_cache() -> None:
    """测试用:清掉缓存,重载配置。"""
    load_config.cache_clear()
