"""Article + RSS fetching with clean-text extraction.

Two responsibilities, one module so the analyzer has a single dependency:

- `Fetcher.fetch_article(url)` -> ArticleContent  (HTML -> trafilatura -> clean text)
- `Fetcher.fetch_feed(url, limit)` -> list[FeedItem]  (RSS/Atom -> feedparser)

Both use a single shared `httpx.AsyncClient` with timeouts and a max-byte guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import struct_time

import feedparser
import httpx
import trafilatura

from app.core.config import Settings
from app.core.exceptions import FetchError, RSSParseError, UnsupportedContentError
from app.core.logging import get_logger

log = get_logger(__name__)

# Min characters trafilatura must extract before we treat content as analyzable.
# Below this we assume paywall, JS-only, or extraction failure.
_MIN_ARTICLE_CHARS = 280


@dataclass(frozen=True, slots=True)
class ArticleContent:
    url: str
    title: str | None
    text: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class FeedItem:
    url: str
    title: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class FeedResult:
    feed_title: str | None
    items: list[FeedItem]


class Fetcher:
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or self._build_client(settings)
        self._owns_client = client is None

    @staticmethod
    def _build_client(settings: Settings) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(settings.fetch_timeout_seconds, connect=10.0),
            headers={"User-Agent": settings.fetch_user_agent, "Accept": "*/*"},
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ─── public API ──────────────────────────────────────────────────────────

    async def fetch_article(self, url: str) -> ArticleContent:
        body, final_url = await self._get(url, accept_kind="article")

        # Decode bytes -> str for trafilatura. trafilatura also accepts str.
        try:
            html = body.decode("utf-8", errors="replace")
        except (UnicodeDecodeError, AttributeError) as e:
            raise FetchError("Could not decode response body", detail=str(e)) from e

        extracted = trafilatura.extract(
            html,
            url=final_url,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
            with_metadata=False,
        )
        if not extracted or len(extracted) < _MIN_ARTICLE_CHARS:
            log.warning(
                "fetcher.extract_too_short",
                url=final_url,
                chars=len(extracted or ""),
            )
            raise UnsupportedContentError(
                "Could not extract substantive article text from URL.",
                detail=f"Extracted {len(extracted or '')} chars; need >= {_MIN_ARTICLE_CHARS}.",
            )

        # Pull title + date via metadata (trafilatura.bare_extraction is robust enough here).
        title: str | None = None
        published_at: datetime | None = None
        try:
            meta = trafilatura.extract_metadata(html)
        except Exception:
            meta = None
        if meta is not None:
            title = (meta.title or "").strip() or None
            if meta.date:
                published_at = _parse_iso_or_none(meta.date)

        log.info(
            "fetcher.article_ok",
            url=final_url,
            chars=len(extracted),
            had_title=title is not None,
            had_date=published_at is not None,
        )
        return ArticleContent(url=final_url, title=title, text=extracted, published_at=published_at)

    async def fetch_feed(self, feed_url: str, *, limit: int) -> FeedResult:
        body, final_url = await self._get(feed_url, accept_kind="feed")

        # feedparser is sync; it's fine to call directly (parsing is bounded by FETCH_MAX_BYTES).
        parsed = feedparser.parse(body)
        if parsed.bozo and not parsed.entries:
            log.warning(
                "fetcher.rss_bozo", url=final_url, exc=str(parsed.get("bozo_exception", ""))
            )
            raise RSSParseError(
                "Feed body could not be parsed.",
                detail=str(parsed.get("bozo_exception", "unknown")),
            )

        feed_title = (getattr(parsed.feed, "title", None) or "").strip() or None
        capped = min(limit, self._settings.rss_hard_limit)
        items: list[FeedItem] = []
        for entry in parsed.entries[:capped]:
            link = getattr(entry, "link", None)
            if not link:
                continue
            items.append(
                FeedItem(
                    url=link,
                    title=(getattr(entry, "title", None) or "").strip() or None,
                    published_at=_struct_time_to_dt(getattr(entry, "published_parsed", None))
                    or _parse_iso_or_none(getattr(entry, "published", None)),
                )
            )

        if not items:
            raise RSSParseError("Feed parsed but had no usable items (no <link> on any entry).")

        log.info("fetcher.feed_ok", url=final_url, items=len(items), feed_title=feed_title)
        return FeedResult(feed_title=feed_title, items=items)

    # ─── internals ───────────────────────────────────────────────────────────

    async def _get(self, url: str, *, accept_kind: str) -> tuple[bytes, str]:
        """GET a URL, enforcing FETCH_MAX_BYTES. Returns (body, final_url_after_redirects)."""
        try:
            async with self._client.stream("GET", url) as resp:
                resp.raise_for_status()
                final_url = str(resp.url)

                # Reject obviously huge bodies via Content-Length first.
                content_length = resp.headers.get("content-length")
                if (
                    content_length
                    and content_length.isdigit()
                    and int(content_length) > self._settings.fetch_max_bytes
                ):
                    raise FetchError(
                        "Response too large.",
                        detail=f"content-length {content_length} exceeds {self._settings.fetch_max_bytes}",
                    )

                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > self._settings.fetch_max_bytes:
                        raise FetchError(
                            "Response exceeded max bytes during streaming.",
                            detail=f"limit={self._settings.fetch_max_bytes}",
                        )
                return bytes(buf), final_url

        except httpx.HTTPStatusError as e:
            raise FetchError(
                f"Upstream returned HTTP {e.response.status_code}",
                detail=f"{accept_kind} fetch: {url}",
            ) from e
        except httpx.TimeoutException as e:
            raise FetchError("Upstream fetch timed out.", detail=str(e)) from e
        except httpx.HTTPError as e:
            raise FetchError("Upstream fetch failed.", detail=f"{type(e).__name__}: {e}") from e


def _struct_time_to_dt(st: struct_time | None) -> datetime | None:
    if st is None:
        return None
    try:
        return datetime(*st[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _parse_iso_or_none(value: str | None) -> datetime | None:
    """Best-effort parse of an ISO-8601 or RFC-2822 date string into UTC."""
    if not value:
        return None
    s = value.strip()
    # Try ISO-8601 first (also handles 'YYYY-MM-DD').
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        pass
    # Fall back to RFC-2822 (common in RSS <pubDate>).
    try:
        dt = parsedate_to_datetime(s)
        if dt is None:
            return None
        return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None
