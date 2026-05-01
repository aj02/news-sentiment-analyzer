"""Analyzer orchestration: happy path, cache hit, LLM failure, schema failure, confidence clamp."""

from __future__ import annotations

import pytest

from app.core.exceptions import LLMError
from app.services.analyzer import Analyzer


@pytest.mark.asyncio
async def test_happy_path(analyzer: Analyzer):
    result = await analyzer.analyze_url("https://example.test/articles/fed-rates")

    assert result.title.startswith("Fed")
    assert result.sentiment.overall.value == "neutral"
    assert result.tokens_used == 300  # 120 prompt + 180 completion (from FakeLLMClient)
    assert result.cached is False
    assert result.analysis_ms >= 0
    assert any(e.name == "Federal Reserve" for e in result.entities)
    assert "monetary-policy" in result.topics


@pytest.mark.asyncio
async def test_cache_hit_skips_llm(analyzer: Analyzer, fake_llm):
    url = "https://example.test/articles/fed-rates"

    first = await analyzer.analyze_url(url)
    assert first.cached is False
    assert len(fake_llm.calls) == 1

    second = await analyzer.analyze_url(url)
    assert second.cached is True
    assert len(fake_llm.calls) == 1, "cache hit should not call the LLM"
    assert second.title == first.title
    assert second.sentiment.overall == first.sentiment.overall


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(analyzer: Analyzer, fake_llm):
    url = "https://example.test/articles/fed-rates"
    await analyzer.analyze_url(url)
    assert len(fake_llm.calls) == 1

    fresh = await analyzer.analyze_url(url, force_refresh=True)
    assert fresh.cached is False
    assert len(fake_llm.calls) == 2


@pytest.mark.asyncio
async def test_llm_failure_propagates(analyzer: Analyzer, fake_llm):
    fake_llm.next_error = LLMError("boom", detail="upstream went away")
    with pytest.raises(LLMError):
        await analyzer.analyze_url("https://example.test/articles/fed-rates")


@pytest.mark.asyncio
async def test_schema_violation_raises_llm_error(analyzer: Analyzer, fake_llm):
    # Output missing required `title` and `summary` — should fail Pydantic validation
    # and surface as LLMError with a helpful detail.
    fake_llm.override_payload = {
        "sentiment": {
            "overall": "neutral",
            "score": 0.0,
            "confidence": 0.7,
            "rationale": "r",
        },
    }
    with pytest.raises(LLMError) as ei:
        await analyzer.analyze_url("https://example.test/articles/fed-rates")
    assert "schema" in ei.value.message.lower()


@pytest.mark.asyncio
async def test_confidence_clamp_to_neutral(analyzer: Analyzer):
    # The greenline canned response has confidence 0.4 + overall=positive.
    # The analyzer must clamp it to neutral with score in [-0.2, 0.2].
    result = await analyzer.analyze_url("https://example.test/articles/greenline")
    assert result.sentiment.overall.value == "neutral"
    assert -0.2 <= result.sentiment.score <= 0.2


@pytest.mark.asyncio
async def test_feed_partial_success(analyzer: Analyzer):
    # The "feed-with-broken" fixture has one good item (fed-rates → 200) and
    # one broken item (server-error → 503). The analyzer should return both
    # results: one analysis, one structured error.
    feed = await analyzer.analyze_feed("https://example.test/feed-with-broken", limit=10)
    assert feed.items_attempted == 2
    assert feed.items_succeeded == 1
    successes = [r for r in feed.results if r.analysis is not None]
    failures = [r for r in feed.results if r.error is not None]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].error.error_code == "fetch_failed"
