"""Factory dispatch: provider env var → correct client class.

These tests don't hit any network — they only check that the factory builds
the right concrete class with the right config.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.llm import (
    AnthropicLLMClient,
    OpenAILLMClient,
    TogetherLLMClient,
    build_llm_client,
)


def _settings(**overrides) -> Settings:
    base = {
        "llm_provider": "anthropic",
        "llm_model": "x",
        "anthropic_api_key": None,
        "openai_api_key": None,
        "together_api_key": None,
    }
    base.update(overrides)
    return Settings(**base)


def test_dispatch_anthropic():
    s = _settings(llm_provider="anthropic", anthropic_api_key="sk-a")
    c = build_llm_client(s)
    assert isinstance(c, AnthropicLLMClient)
    assert c.name == "anthropic"


def test_dispatch_openai():
    s = _settings(llm_provider="openai", openai_api_key="sk-o")
    c = build_llm_client(s)
    assert isinstance(c, OpenAILLMClient)
    assert c.name == "openai"


def test_dispatch_together():
    s = _settings(llm_provider="together", together_api_key="tg-key")
    c = build_llm_client(s)
    assert isinstance(c, TogetherLLMClient)
    assert c.name == "together"
    # TogetherLLMClient is also-an OpenAILLMClient (shared SDK), but the dispatch
    # must pick the Together subclass specifically.
    assert isinstance(c, OpenAILLMClient)


def test_together_uses_settings_base_url():
    s = _settings(
        llm_provider="together",
        together_api_key="tg-key",
        together_base_url="https://gateway.example.test/v1",
    )
    c = build_llm_client(s)
    assert isinstance(c, TogetherLLMClient)
    # The OpenAI SDK exposes the configured base URL on the client.
    assert "gateway.example.test" in str(c._client.base_url)


@pytest.mark.parametrize(
    ("provider", "expected_env_var"),
    [
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("together", "TOGETHER_API_KEY"),
    ],
)
def test_missing_key_raises_with_helpful_env_var_name(provider, expected_env_var):
    s = _settings(llm_provider=provider)
    with pytest.raises(RuntimeError, match=expected_env_var):
        build_llm_client(s)
