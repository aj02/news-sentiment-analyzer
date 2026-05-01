"""Orchestrates: fetch → cache lookup → LLM → validate → cache write.

The analyzer is the only place that knows the full pipeline; routes call it
directly. Each step's logging keys are stable so dashboards can pivot on them.
"""

from __future__ import annotations

import time

from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AnalyzerError, LLMError
from app.core.logging import get_logger
from app.prompts.loader import load_prompt
from app.schemas.responses import (
    AnalyzeFeedResponse,
    AnalyzeResponse,
    AnalyzeResponseError,
    FeedItemResult,
)
from app.schemas.sentiment import LLMAnalysis, SentimentLabel
from app.services.cache import AnalysisCache
from app.services.fetcher import ArticleContent, Fetcher
from app.services.llm.base import LLMClient

log = get_logger(__name__)

# Truncate article text passed to the LLM to keep token cost bounded. Most news
# articles are well under this; very long ones get the head — usually where the
# lede + nut graf live.
_MAX_ARTICLE_CHARS = 18_000


class Analyzer:
    def __init__(
        self,
        settings: Settings,
        *,
        fetcher: Fetcher,
        llm: LLMClient,
        cache: AnalysisCache,
    ) -> None:
        self._settings = settings
        self._fetcher = fetcher
        self._llm = llm
        self._cache = cache

    async def analyze_url(self, url: str, *, force_refresh: bool = False) -> AnalyzeResponse:
        t0 = time.perf_counter()

        if not force_refresh:
            cached = await self._cache.get(url)
            if cached is not None:
                log.info("analyzer.cache_hit", url=url)
                cached["cached"] = True
                cached["analysis_ms"] = int((time.perf_counter() - t0) * 1000)
                return AnalyzeResponse.model_validate(cached)
            log.info("analyzer.cache_miss", url=url)
        else:
            log.info("analyzer.cache_bypass", url=url)

        article = await self._fetcher.fetch_article(url)
        analysis = await self._run_llm(article)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        response = AnalyzeResponse.from_llm(
            url=article.url,
            analysis=analysis.parsed_model,
            published_at=article.published_at,
            model_used=analysis.model_used,
            tokens_used=analysis.tokens_used,
            cached=False,
            analysis_ms=elapsed_ms,
        )

        # Cache the *fresh* payload (cached=False, analysis_ms=elapsed). On hit we
        # rewrite cached=True and recompute analysis_ms.
        await self._cache.set(article.url, response.model_dump(mode="json"))
        log.info(
            "analyzer.complete",
            url=article.url,
            model=analysis.model_used,
            tokens=analysis.tokens_used,
            sentiment=response.sentiment.overall.value,
            elapsed_ms=elapsed_ms,
        )
        return response

    async def analyze_feed(
        self, feed_url: str, *, limit: int, force_refresh: bool = False
    ) -> AnalyzeFeedResponse:
        feed = await self._fetcher.fetch_feed(feed_url, limit=limit)

        results: list[FeedItemResult] = []
        succeeded = 0
        for item in feed.items:
            try:
                analysis = await self.analyze_url(item.url, force_refresh=force_refresh)
                # If the feed gave us a published_at and the analyzer didn't have one, fill it.
                if analysis.published_at is None and item.published_at is not None:
                    analysis = analysis.model_copy(update={"published_at": item.published_at})
                results.append(FeedItemResult(analysis=analysis))
                succeeded += 1
            except AnalyzerError as e:
                log.warning(
                    "analyzer.feed_item_failed",
                    feed_url=feed_url,
                    item_url=item.url,
                    code=e.code,
                    detail=e.detail,
                )
                results.append(
                    FeedItemResult(
                        error=AnalyzeResponseError(
                            url=item.url,
                            error_code=e.code,
                            error_message=e.message,
                        )
                    )
                )

        return AnalyzeFeedResponse(
            feed_url=feed_url,
            feed_title=feed.feed_title,
            items_attempted=len(feed.items),
            items_succeeded=succeeded,
            results=results,
        )

    # ─── internals ───────────────────────────────────────────────────────────

    async def _run_llm(self, article: ArticleContent) -> _AnalysisResult:
        prompt = load_prompt(self._settings.prompt_version)
        truncated = article.text[:_MAX_ARTICLE_CHARS]

        system_msg = prompt.render_system()
        user_msg = prompt.render_user(
            article_text=truncated,
            source_url=article.url,
            fetched_title=article.title,
        )

        try:
            llm_result = await self._llm.complete_json(system=system_msg, user=user_msg)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                "Unexpected error calling LLM.", detail=f"{type(e).__name__}: {e}"
            ) from e

        try:
            parsed_model = LLMAnalysis.model_validate(llm_result.parsed)
        except ValidationError as e:
            log.warning(
                "analyzer.schema_validation_failed",
                url=article.url,
                errors=e.error_count(),
            )
            raise LLMError(
                "LLM output did not match expected schema.",
                detail=str(e),
            ) from e

        # Apply Hard Rule 2 server-side as belt-and-suspenders: if the model said
        # confidence < 0.5 but didn't move the label to neutral, fix it here so
        # we don't silently violate our own contract.
        sentiment = parsed_model.sentiment
        if sentiment.confidence < 0.5 and sentiment.overall is not SentimentLabel.NEUTRAL:
            log.info(
                "analyzer.confidence_clamp",
                original_overall=sentiment.overall.value,
                confidence=sentiment.confidence,
            )
            clamped_score = max(-0.2, min(0.2, sentiment.score))
            parsed_model = parsed_model.model_copy(
                update={
                    "sentiment": sentiment.model_copy(
                        update={"overall": SentimentLabel.NEUTRAL, "score": clamped_score}
                    )
                }
            )

        return _AnalysisResult(
            parsed_model=parsed_model,
            model_used=llm_result.model,
            tokens_used=llm_result.total_tokens,
        )


class _AnalysisResult:
    __slots__ = ("model_used", "parsed_model", "tokens_used")

    def __init__(self, *, parsed_model: LLMAnalysis, model_used: str, tokens_used: int) -> None:
        self.parsed_model = parsed_model
        self.model_used = model_used
        self.tokens_used = tokens_used


__all__ = ["Analyzer"]
