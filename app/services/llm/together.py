"""Together AI provider.

Together's Chat Completions API is OpenAI-compatible — same wire format, same
`response_format={"type": "json_object"}` support on most Llama / Qwen / Mixtral
models. We hit it via the OpenAI SDK pointed at Together's base URL, so this
class is a thin subclass of `OpenAILLMClient` that injects the right URL and
relabels error messages.

Recommended models for this service (all support JSON mode at time of writing):
  - meta-llama/Llama-3.3-70B-Instruct-Turbo
  - Qwen/Qwen2.5-72B-Instruct-Turbo
  - mistralai/Mixtral-8x7B-Instruct-v0.1

If you pick a model that does NOT support JSON mode, Together returns a 400
that surfaces as an `LLMError` with the upstream detail — switch to a model
from the supported list rather than working around it client-side.
"""

from __future__ import annotations

from app.services.llm.openai import OpenAILLMClient


class TogetherLLMClient(OpenAILLMClient):
    name = "together"
    _provider_label = "Together"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: float,
        max_retries: int,
        base_url: str,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            base_url=base_url,
        )
