"""Fetcher: extracts text, parses RSS, raises on paywall stubs and 404s."""

from __future__ import annotations

import pytest

from app.core.exceptions import FetchError, RSSParseError, UnsupportedContentError
from app.services.fetcher import Fetcher


@pytest.mark.asyncio
async def test_fetch_article_extracts_clean_text(fetcher: Fetcher):
    content = await fetcher.fetch_article("https://example.test/articles/rbi-policy")
    assert "Reserve Bank of India" in content.text
    assert "Subscribe to read" not in content.text
    assert content.title is not None
    assert "RBI" in content.title or "rate" in content.title.lower()


@pytest.mark.asyncio
async def test_fetch_article_paywall_raises_unsupported(fetcher: Fetcher):
    with pytest.raises(UnsupportedContentError):
        await fetcher.fetch_article("https://example.test/articles/paywall")


@pytest.mark.asyncio
async def test_fetch_article_404_raises_fetch_error(fetcher: Fetcher):
    with pytest.raises(FetchError):
        await fetcher.fetch_article("https://example.test/articles/missing")


@pytest.mark.asyncio
async def test_fetch_feed_returns_items(fetcher: Fetcher):
    feed = await fetcher.fetch_feed("https://example.test/feed", limit=10)
    assert feed.feed_title == "Indian Economy News"
    assert len(feed.items) == 2
    assert feed.items[0].url == "https://example.test/articles/rbi-policy"
    assert feed.items[0].published_at is not None


@pytest.mark.asyncio
async def test_fetch_feed_limit_applied(fetcher: Fetcher):
    feed = await fetcher.fetch_feed("https://example.test/feed", limit=1)
    assert len(feed.items) == 1


@pytest.mark.asyncio
async def test_fetch_feed_unparseable_raises(fetcher: Fetcher):
    with pytest.raises(RSSParseError):
        await fetcher.fetch_feed("https://example.test/garbage-feed", limit=10)
