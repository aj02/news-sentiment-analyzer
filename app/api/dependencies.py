"""FastAPI dependency providers.

Wired through `request.app.state` so tests can override individual services
(e.g. swap in a fake LLM client) by mutating state in a fixture.
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.services.analyzer import Analyzer
from app.services.cache import AnalysisCache


def get_settings_dep() -> Settings:
    return get_settings()


def get_analyzer(request: Request) -> Analyzer:
    return request.app.state.analyzer


def get_cache(request: Request) -> AnalysisCache:
    return request.app.state.cache


__all__ = [
    "Depends",
    "get_analyzer",
    "get_cache",
    "get_settings_dep",
]
