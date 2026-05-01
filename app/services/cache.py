"""Redis cache wrapper.

The cache key is `nsa:v{prompt_version}:{model}:{sha256(url)}`. The model and
prompt version are part of the key so swapping providers/prompts naturally
invalidates old entries — no manual flushes needed.

Falls back to a no-op when CACHE_ENABLED=false. Logs (but doesn't raise) if
Redis is down so a Redis outage degrades the service from "cached" to "live"
rather than 500-ing every request.
"""

from __future__ import annotations

import contextlib
import hashlib
from typing import Protocol

import orjson
import redis.asyncio as redis_async
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


class _RedisLike(Protocol):
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ex: int | None = None) -> object: ...
    async def ping(self) -> object: ...
    async def aclose(self) -> None: ...


class AnalysisCache:
    def __init__(
        self,
        settings: Settings,
        *,
        redis: _RedisLike | None = None,
    ) -> None:
        self._settings = settings
        self._enabled = settings.cache_enabled
        if not self._enabled:
            self._redis: _RedisLike | None = None
        else:
            self._redis = redis or redis_async.from_url(  # type: ignore[assignment]
                settings.redis_url,
                decode_responses=False,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )

    @property
    def enabled(self) -> bool:
        return self._enabled and self._redis is not None

    def make_key(self, url: str) -> str:
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return f"nsa:{self._settings.prompt_version}:{self._settings.llm_model}:{url_hash}"

    async def get(self, url: str) -> dict | None:
        if not self.enabled:
            return None
        key = self.make_key(url)
        try:
            blob = await self._redis.get(key)  # type: ignore[union-attr]
        except RedisError as e:
            log.warning("cache.get_failed", key=key, err=str(e))
            return None
        if blob is None:
            return None
        try:
            return orjson.loads(blob)
        except orjson.JSONDecodeError as e:
            log.warning("cache.corrupt_entry", key=key, err=str(e))
            return None

    async def set(self, url: str, payload: dict) -> None:
        if not self.enabled:
            return
        key = self.make_key(url)
        try:
            await self._redis.set(  # type: ignore[union-attr]
                key,
                orjson.dumps(payload),
                ex=self._settings.cache_ttl_seconds or None,
            )
        except RedisError as e:
            log.warning("cache.set_failed", key=key, err=str(e))

    async def ping(self) -> str:
        """For /ready. Returns 'ok', 'disabled', or 'down: <detail>'."""
        if not self._enabled:
            return "disabled"
        if self._redis is None:
            return "disabled"
        try:
            await self._redis.ping()
        except RedisError as e:
            return f"down: {type(e).__name__}: {e}"
        return "ok"

    async def aclose(self) -> None:
        if self._redis is not None:
            with contextlib.suppress(RedisError):
                await self._redis.aclose()
