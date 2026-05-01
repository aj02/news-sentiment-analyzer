"""structlog setup. JSON in prod, key=value in dev. Request IDs via contextvars."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog
from structlog.types import EventDict, Processor

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def _inject_request_id(_: object, __: str, event_dict: EventDict) -> EventDict:
    rid = _request_id_var.get()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    return event_dict


def configure_logging(*, level: str = "INFO", json_logs: bool = True) -> None:
    """Idempotently configure stdlib logging + structlog."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _inject_request_id,
        structlog.processors.StackInfoRenderer(),
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib root logger so libraries (uvicorn, httpx) flow through.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Quiet noisy libs.
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(max(log_level, logging.WARNING))


def bind_request_id(request_id: str | None = None) -> str:
    """Bind a request ID to the current context. Returns the bound id."""
    rid = request_id or uuid.uuid4().hex
    _request_id_var.set(rid)
    structlog.contextvars.bind_contextvars(request_id=rid)
    return rid


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
