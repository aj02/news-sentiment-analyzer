"""Response models — wrap the LLM output with service-level metadata."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.sentiment import (
    Aspect,
    EntitySentiment,
    KeyClaim,
    LLMAnalysis,
    Quote,
    SentimentBlock,
)


class AnalyzeResponse(BaseModel):
    """Returned by POST /analyze. Mirrors the schema in the README."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str
    published_at: datetime | None = Field(
        default=None,
        description="From the feed item or page metadata, when available. Not invented by the LLM.",
    )
    summary: str
    sentiment: SentimentBlock
    entities: list[EntitySentiment]
    key_claims: list[KeyClaim]
    aspects: list[Aspect]
    quotes: list[Quote]
    topics: list[str]

    model_used: str
    tokens_used: int = Field(
        ge=0, description="Total prompt + completion tokens reported by the provider."
    )
    cached: bool
    analysis_ms: int = Field(ge=0, description="Wall time spent in the analyzer for this request.")

    @classmethod
    def from_llm(
        cls,
        *,
        url: str,
        analysis: LLMAnalysis,
        published_at: datetime | None,
        model_used: str,
        tokens_used: int,
        cached: bool,
        analysis_ms: int,
    ) -> AnalyzeResponse:
        return cls(
            url=url,
            title=analysis.title,
            published_at=published_at,
            summary=analysis.summary,
            sentiment=analysis.sentiment,
            entities=analysis.entities,
            key_claims=analysis.key_claims,
            aspects=analysis.aspects,
            quotes=analysis.quotes,
            topics=analysis.topics,
            model_used=model_used,
            tokens_used=tokens_used,
            cached=cached,
            analysis_ms=analysis_ms,
        )


class AnalyzeResponseError(BaseModel):
    """A per-item error in batched feed analysis. Lets callers see partial success."""

    model_config = ConfigDict(extra="forbid")

    url: str
    error_code: str
    error_message: str


class FeedItemResult(BaseModel):
    """One slot in the feed-analysis response. Either `analysis` or `error` is set."""

    model_config = ConfigDict(extra="forbid")

    analysis: AnalyzeResponse | None = None
    error: AnalyzeResponseError | None = None


class AnalyzeFeedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feed_url: str
    feed_title: str | None
    items_attempted: int
    items_succeeded: int
    results: list[FeedItemResult]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = "ok"
    version: str


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    redis: str  # "ok" | "disabled" | "down: <detail>"


class ErrorResponse(BaseModel):
    """Consistent error envelope. Used by the global exception handlers."""

    model_config = ConfigDict(extra="forbid")

    error: str = Field(description="Stable machine code, e.g. 'fetch_failed'.")
    message: str = Field(description="Human-readable summary.")
    detail: str | None = None
    request_id: str | None = None
