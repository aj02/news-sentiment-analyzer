"""FastAPI app factory.

The lifespan handler builds long-lived services (Fetcher, LLM client, cache)
and stows them on `app.state` so dependencies can pull them out per-request
without rebuilding clients.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response

from app import __version__
from app.api.errors import install_error_handlers
from app.api.routes import router as api_router
from app.core.config import Settings, get_settings
from app.core.logging import bind_request_id, configure_logging, get_logger
from app.services.analyzer import Analyzer
from app.services.cache import AnalysisCache
from app.services.fetcher import Fetcher
from app.services.llm.factory import build_llm_client

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = getattr(app.state, "settings", None) or get_settings()
    app.state.settings = settings

    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    log = get_logger("app.startup")
    log.info(
        "app.starting",
        version=__version__,
        env=settings.app_env,
        provider=settings.llm_provider,
        model=settings.llm_model,
        prompt_version=settings.prompt_version,
        cache_enabled=settings.cache_enabled,
    )

    # Tests can pre-populate any of these on app.state to inject fakes.
    fetcher = getattr(app.state, "fetcher", None) or Fetcher(settings)
    llm = getattr(app.state, "llm", None) or build_llm_client(settings)
    cache = getattr(app.state, "cache", None) or AnalysisCache(settings)

    app.state.fetcher = fetcher
    app.state.llm = llm
    app.state.cache = cache
    app.state.analyzer = getattr(app.state, "analyzer", None) or Analyzer(
        settings, fetcher=fetcher, llm=llm, cache=cache
    )

    try:
        yield
    finally:
        log.info("app.shutting_down")
        await fetcher.aclose()
        await llm.aclose()
        await cache.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="news-sentiment-analyzer",
        version=__version__,
        description=(
            "Fetches news articles or RSS feeds, extracts structured sentiment, "
            "entities, and key claims via LLM, and returns clean JSON."
        ),
        lifespan=lifespan,
    )
    if settings is not None:
        app.state.settings = settings

    install_error_handlers(app)

    @app.middleware("http")
    async def _request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = bind_request_id(request.headers.get("x-request-id"))
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def _ui_root() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")

    return app


app = create_app()
