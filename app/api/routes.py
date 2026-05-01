"""HTTP routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app import __version__
from app.api.dependencies import get_analyzer, get_cache
from app.core.logging import get_logger
from app.schemas.requests import AnalyzeFeedRequest, AnalyzeRequest
from app.schemas.responses import (
    AnalyzeFeedResponse,
    AnalyzeResponse,
    HealthResponse,
    ReadyResponse,
)
from app.services.analyzer import Analyzer
from app.services.cache import AnalysisCache

router = APIRouter()
log = get_logger(__name__)

AnalyzerDep = Annotated[Analyzer, Depends(get_analyzer)]
CacheDep = Annotated[AnalysisCache, Depends(get_cache)]


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(version=__version__)


@router.get("/ready", response_model=ReadyResponse, tags=["meta"])
async def ready(cache: CacheDep) -> ReadyResponse:
    redis_status = await cache.ping()
    overall = "ok" if redis_status in ("ok", "disabled") else "degraded"
    return ReadyResponse(status=overall, redis=redis_status)


@router.post("/analyze", response_model=AnalyzeResponse, tags=["analyze"])
async def analyze(body: AnalyzeRequest, analyzer: AnalyzerDep) -> AnalyzeResponse:
    log.info("api.analyze", url=str(body.url), force_refresh=body.force_refresh)
    return await analyzer.analyze_url(str(body.url), force_refresh=body.force_refresh)


@router.post("/analyze/feed", response_model=AnalyzeFeedResponse, tags=["analyze"])
async def analyze_feed(body: AnalyzeFeedRequest, analyzer: AnalyzerDep) -> AnalyzeFeedResponse:
    log.info(
        "api.analyze_feed",
        feed_url=str(body.feed_url),
        limit=body.limit,
        force_refresh=body.force_refresh,
    )
    return await analyzer.analyze_feed(
        str(body.feed_url),
        limit=body.limit,
        force_refresh=body.force_refresh,
    )
