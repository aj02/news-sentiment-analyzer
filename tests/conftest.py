"""Shared fixtures.

We build a real FastAPI app with three real services and one fake:
- Fetcher: real, but its httpx client is mocked with respx so no network hits.
- Cache: real `AnalysisCache` wired to fakeredis (covers all serde paths).
- LLM: a fake client that returns canned JSON keyed by URL keyword.
- Analyzer: real — exercises the full orchestration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import fakeredis.aioredis
import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.analyzer import Analyzer
from app.services.cache import AnalysisCache
from app.services.fetcher import Fetcher
from app.services.llm.base import LLMClient, LLMResult
from tests.fixtures.articles import ARTICLES_BY_URL
from tests.fixtures.llm_responses import RESPONSES_BY_URL_KEYWORD


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider="anthropic",
        llm_model="claude-haiku-4-5",
        anthropic_api_key="test-key",
        prompt_version="v2",
        cache_enabled=True,
        log_level="WARNING",
        log_json=False,
        app_env="test",
        cache_ttl_seconds=60,
    )


class FakeLLMClient(LLMClient):
    """In-memory LLM that returns a canned response keyed by article URL."""

    name = "fake"

    def __init__(self) -> None:
        super().__init__(model="fake-model-1", max_output_tokens=2000)
        self.calls: list[dict[str, str]] = []
        # If set, the next call will raise this exception instead of returning canned data.
        self.next_error: Exception | None = None
        # Optional override: full parsed payload to return regardless of URL.
        self.override_payload: dict[str, Any] | None = None

    async def complete_json(self, *, system: str, user: str) -> LLMResult:
        self.calls.append({"system": system, "user": user})
        if self.next_error is not None:
            err = self.next_error
            self.next_error = None
            raise err

        if self.override_payload is not None:
            return LLMResult(
                parsed=self.override_payload,
                model=self.model,
                prompt_tokens=120,
                completion_tokens=180,
            )

        for keyword, payload in RESPONSES_BY_URL_KEYWORD.items():
            if keyword in user:
                return LLMResult(
                    parsed=payload,
                    model=self.model,
                    prompt_tokens=120,
                    completion_tokens=180,
                )
        raise AssertionError(
            f"FakeLLMClient: no canned response matched user prompt:\n{user[:200]}"
        )

    async def aclose(self) -> None:
        pass


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def fake_redis() -> Any:
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def cache(settings: Settings, fake_redis: Any) -> AnalysisCache:
    return AnalysisCache(settings, redis=fake_redis)


@pytest.fixture
def respx_mock() -> Iterator[respx.MockRouter]:
    """All HTTP routes used by the test suite are declared here.

    Tests that need different status codes or different bodies use the dedicated
    URLs below rather than overriding routes — keeps registration order obvious.
    """
    with respx.mock(assert_all_called=False) as router:
        for url, (body, content_type) in ARTICLES_BY_URL.items():
            router.get(url).mock(
                return_value=httpx.Response(
                    200,
                    content=body.encode("utf-8"),
                    headers={"content-type": content_type},
                )
            )
        # 404 for verifying FetchError on missing articles.
        router.get("https://example.test/articles/missing").mock(return_value=httpx.Response(404))
        # 503 used by the feed partial-success test (one item fails to fetch).
        router.get("https://example.test/articles/server-error").mock(
            return_value=httpx.Response(503)
        )
        # 200 OK but body is garbage — for RSSParseError.
        router.get("https://example.test/garbage-feed").mock(
            return_value=httpx.Response(
                200,
                content=b"this is not a feed",
                headers={"content-type": "text/plain"},
            )
        )
        yield router


@pytest.fixture
async def fetcher(settings: Settings, respx_mock: respx.MockRouter) -> AsyncIterator[Fetcher]:
    f = Fetcher(settings)
    yield f
    await f.aclose()


@pytest.fixture
async def analyzer(
    settings: Settings,
    fetcher: Fetcher,
    fake_llm: FakeLLMClient,
    cache: AnalysisCache,
) -> AsyncIterator[Analyzer]:
    a = Analyzer(settings, fetcher=fetcher, llm=fake_llm, cache=cache)
    yield a
    await cache.aclose()


@pytest.fixture
def app(
    settings: Settings,
    fetcher: Fetcher,
    fake_llm: FakeLLMClient,
    cache: AnalysisCache,
) -> FastAPI:
    """A real FastAPI app with services pre-injected via app.state."""
    a = create_app(settings)
    a.state.fetcher = fetcher
    a.state.llm = fake_llm
    a.state.cache = cache
    a.state.analyzer = Analyzer(settings, fetcher=fetcher, llm=fake_llm, cache=cache)
    return a


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
