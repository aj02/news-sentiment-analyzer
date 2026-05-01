"""AnalysisCache: round-trip, key includes prompt + model, ping report."""

from __future__ import annotations

import pytest

from app.services.cache import AnalysisCache


@pytest.mark.asyncio
async def test_round_trip(cache: AnalysisCache):
    url = "https://example.test/articles/fed-rates"
    payload = {"hello": "world"}
    assert await cache.get(url) is None

    await cache.set(url, payload)
    assert await cache.get(url) == payload


@pytest.mark.asyncio
async def test_key_namespaced_by_model_and_prompt_version(cache: AnalysisCache, settings):
    key = cache.make_key("https://example.test/x")
    assert key.startswith(f"nsa:{settings.prompt_version}:{settings.llm_model}:")


@pytest.mark.asyncio
async def test_ping_ok(cache: AnalysisCache):
    assert await cache.ping() == "ok"


@pytest.mark.asyncio
async def test_disabled_cache_is_no_op(settings):
    settings.cache_enabled = False
    c = AnalysisCache(settings)
    assert await c.get("any") is None
    await c.set("any", {"x": 1})
    assert await c.get("any") is None
    assert await c.ping() == "disabled"
    await c.aclose()
