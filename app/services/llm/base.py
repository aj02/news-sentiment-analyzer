"""LLM provider interface.

Both Anthropic and OpenAI implementations expose the same `complete_json` method.
The analyzer doesn't know or care which one it has — it gets a `LLMResult` back
either way.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.exceptions import LLMError


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Raw decoded JSON from the model, plus accounting metadata."""

    parsed: dict  # parsed JSON object (NOT yet validated against LLMAnalysis)
    model: str
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient(ABC):
    """Provider-agnostic JSON completion client."""

    name: str  # "anthropic" | "openai"

    def __init__(self, *, model: str, max_output_tokens: int) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens

    @abstractmethod
    async def complete_json(self, *, system: str, user: str) -> LLMResult:
        """Send system + user prompts; return parsed JSON object + token usage.

        Implementations MUST raise `LLMError` on transport failure (after retries),
        or when the model output cannot be parsed as JSON.
        """

    @abstractmethod
    async def aclose(self) -> None: ...

    @staticmethod
    def _decode_json(text: str) -> dict:
        """Robustly decode a JSON object from a model response.

        Models occasionally wrap output in ```json fences or prepend prose despite
        instructions. We try strict parse first, then a best-effort fallback that
        slices from the first '{' to the last '}'.
        """
        text = text.strip()
        if not text:
            raise LLMError("LLM returned empty response.")

        # Strip common ```json fences.
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop first fence line and the closing fence line if present.
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Last-ditch: slice from first '{' to last '}'.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as e:
                raise LLMError(
                    "LLM output was not valid JSON.",
                    detail=f"{type(e).__name__}: {e}",
                ) from e

        raise LLMError("LLM output contained no JSON object.", detail=text[:200])
