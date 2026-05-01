"""OpenAI provider. Uses Chat Completions with response_format=json_object."""

from __future__ import annotations

import openai
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

_RETRY_EXCS: tuple[type[BaseException], ...] = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
    openai.RateLimitError,
)


class OpenAILLMClient(LLMClient):
    name = "openai"

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
        self._client = openai.AsyncOpenAI(
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
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        max_tokens=self.max_output_tokens,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    )
        except _RETRY_EXCS as e:
            raise LLMError(
                f"OpenAI call failed after {self._max_retries} retries.",
                detail=f"{type(e).__name__}: {e}",
            ) from e
        except openai.APIError as e:
            raise LLMError("OpenAI API error.", detail=f"{type(e).__name__}: {e}") from e

        if not response.choices:
            raise LLMError("OpenAI returned no choices.")
        message = response.choices[0].message
        text = message.content or ""
        parsed = self._decode_json(text)

        usage = response.usage
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        return LLMResult(
            parsed=parsed,
            model=response.model,
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
        )

    async def aclose(self) -> None:
        await self._client.close()
