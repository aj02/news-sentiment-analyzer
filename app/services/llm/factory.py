"""Factory: picks an LLM client based on Settings.llm_provider."""

from __future__ import annotations

from app.core.config import Settings
from app.services.llm.anthropic import AnthropicLLMClient
from app.services.llm.base import LLMClient
from app.services.llm.openai import OpenAILLMClient
from app.services.llm.together import TogetherLLMClient

_KEY_ENV_NAME = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "together": "TOGETHER_API_KEY",
}


def build_llm_client(settings: Settings) -> LLMClient:
    api_key = settings.provider_api_key()
    if not api_key:
        raise RuntimeError(
            f"Missing API key for provider {settings.llm_provider!r}. "
            f"Set {_KEY_ENV_NAME[settings.llm_provider]}."
        )

    common = {
        "api_key": api_key,
        "model": settings.llm_model,
        "max_output_tokens": settings.llm_max_output_tokens,
        "timeout_seconds": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }

    if settings.llm_provider == "anthropic":
        return AnthropicLLMClient(**common)
    if settings.llm_provider == "together":
        return TogetherLLMClient(base_url=settings.together_base_url, **common)
    return OpenAILLMClient(**common)
