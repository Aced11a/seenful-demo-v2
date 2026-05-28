"""测试 autouse fixture: 每个测试清缓存避免污染."""
from __future__ import annotations

import pytest

from src.mini_album.geocoder import clear_cache as clear_geocoder_cache
from src.policy.config_loader import clear_cache


@pytest.fixture(autouse=True)
def reset_config_cache():
    """每个测试前清掉 config + geocoder 缓存,避免污染.

    ADR-0016 geocoder yaml default provider="mock", 测试天然走 mock 不打真 API.
    """
    clear_cache()
    clear_geocoder_cache()
    yield
    clear_cache()
    clear_geocoder_cache()
