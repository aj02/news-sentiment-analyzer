"""Global error handlers — convert domain exceptions to ErrorResponse."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AnalyzerError
from app.core.logging import get_logger
from app.schemas.responses import ErrorResponse

log = get_logger(__name__)


def _request_id() -> str | None:
    ctx = structlog.contextvars.get_contextvars()
    val = ctx.get("request_id")
    return val if isinstance(val, str) else None


def _to_response(exc: AnalyzerError) -> JSONResponse:
    payload = ErrorResponse(
        error=exc.code,
        message=exc.message,
        detail=exc.detail,
        request_id=_request_id(),
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AnalyzerError)
    async def _analyzer_error(_: Request, exc: AnalyzerError) -> JSONResponse:
        log.warning("api.error", code=exc.code, message=exc.message, detail=exc.detail)
        return _to_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        payload = ErrorResponse(
            error="invalid_request",
            message="Request body failed validation.",
            detail=str(exc.errors()),
            request_id=_request_id(),
        )
        return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("api.unhandled_exception", err=str(exc))
        payload = ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred.",
            request_id=_request_id(),
        )
        return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))
