"""Anthropic Claude provider."""

from __future__ import annotations

import anthropic
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.services.llm.base import LLMClient, LLMResult

log = get_logger(__name__)

# Errors worth retrying — transient transport, server-side, or rate limits.
_RETRY_EXCS: tuple[type[BaseException], ...] = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.RateLimitError,
)


class AnthropicLLMClient(LLMClient):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        super().__init__(model=model, max_output_tokens=max_output_tokens)
        # The SDK's built-in retries are disabled; we wrap with tenacity for unified backoff.
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self._max_retries = max_retries

    async def complete_json(self, *, system: str, user: str) -> LLMResult:
        retrying = AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=15.0),
            retry=retry_if_exception_type(_RETRY_EXCS),
        )

        try:
            async for attempt in retrying:
                with attempt:
                    response = await self._client.messages.create(
                        model=self.model,
                        max_tokens=self.max_output_tokens,
                        system=system,
                        messages=[{"role": "user", "content": user}],
                    )
        except _RETRY_EXCS as e:
            raise LLMError(
                f"Anthropic call failed after {self._max_retries} retries.",
                detail=f"{type(e).__name__}: {e}",
            ) from e
        except anthropic.APIError as e:
            raise LLMError("Anthropic API error.", detail=f"{type(e).__name__}: {e}") from e

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        parsed = self._decode_json(text)

        usage = response.usage
        return LLMResult(
            parsed=parsed,
            model=response.model,
            prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
            completion_tokens=getattr(usage, "output_tokens", 0) or 0,
        )

    async def aclose(self) -> None:
        await self._client.close()
