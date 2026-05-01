"""Settings loaded from environment variables (Pydantic Settings v2)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["anthropic", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    llm_provider: LLMProvider = "anthropic"
    llm_model: str = "claude-haiku-4-5"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    llm_max_output_tokens: int = Field(default=2000, ge=256, le=8192)
    llm_timeout_seconds: float = Field(default=45.0, gt=0)
    llm_max_retries: int = Field(default=3, ge=0, le=8)
    prompt_version: str = "v3"

    # Fetcher
    fetch_timeout_seconds: float = Field(default=15.0, gt=0)
    fetch_max_bytes: int = Field(default=5_000_000, gt=0)
    fetch_user_agent: str = (
        "news-sentiment-analyzer/0.1 (+https://github.com/aj02/news-sentiment-analyzer)"
    )
    rss_hard_limit: int = Field(default=25, ge=1, le=200)

    # Cache
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = Field(default=86_400, ge=0)
    cache_enabled: bool = True

    # Server / logging
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    log_json: bool = True
    app_env: str = "local"

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()

    def provider_api_key(self) -> str | None:
        return self.anthropic_api_key if self.llm_provider == "anthropic" else self.openai_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor — call this in routes via Depends."""
    return Settings()
