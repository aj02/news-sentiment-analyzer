"""Factory: picks an LLM client based on Settings.llm_provider."""

from __future__ import annotations

from app.core.config import Settings
from app.services.llm.anthropic import AnthropicLLMClient
from app.services.llm.base import LLMClient
from app.services.llm.openai import OpenAILLMClient


def build_llm_client(settings: Settings) -> LLMClient:
    api_key = settings.provider_api_key()
    if not api_key:
        raise RuntimeError(
            f"Missing API key for provider {settings.llm_provider!r}. "
            f"Set {'ANTHROPIC_API_KEY' if settings.llm_provider == 'anthropic' else 'OPENAI_API_KEY'}."
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
    return OpenAILLMClient(**common)
