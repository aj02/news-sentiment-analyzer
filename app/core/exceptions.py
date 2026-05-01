"""Domain exceptions. Each maps to a specific HTTP status in the error handler."""

from __future__ import annotations


class AnalyzerError(Exception):
    """Base for all analyzer-domain errors."""

    status_code: int = 500
    code: str = "analyzer_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class FetchError(AnalyzerError):
    """Network failure, non-2xx, or oversized response when fetching a URL."""

    status_code = 502
    code = "fetch_failed"


class UnsupportedContentError(AnalyzerError):
    """Fetched URL did not yield extractable article text (e.g. paywall, JS-only page)."""

    status_code = 422
    code = "unsupported_content"


class RSSParseError(AnalyzerError):
    """Feed body could not be parsed as RSS/Atom."""

    status_code = 422
    code = "rss_parse_failed"


class LLMError(AnalyzerError):
    """LLM call failed after retries, or returned malformed output."""

    status_code = 502
    code = "llm_failed"
