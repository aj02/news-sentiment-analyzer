"""LLM structured output schema.

The model is told to emit JSON conforming to `LLMAnalysis.model_json_schema()`.
This file is the single source of truth — the prompt embeds the same schema,
and the analyzer validates the model's output against it before returning.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class EntitySentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EntityType(StrEnum):
    PERSON = "person"
    ORG = "org"
    LOCATION = "location"
    PRODUCT = "product"
    OTHER = "other"


class Stance(StrEnum):
    ASSERTED = "asserted"  # author states it directly
    REPORTED = "reported"  # attributed to a source ("X said")
    SPECULATED = "speculated"  # framed as possibility / opinion


class SentimentBlock(BaseModel):
    """Top-level sentiment of the article."""

    model_config = ConfigDict(extra="forbid")

    overall: SentimentLabel = Field(
        description=(
            "One of positive, negative, neutral, mixed. Use 'mixed' only when the article "
            "presents clearly opposing valences. Use 'neutral' for factual reporting without "
            "evaluative language."
        )
    )
    score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Continuous score: -1.0 strongly negative, 0.0 neutral, +1.0 strongly positive.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Self-assessed confidence. If <0.5, `overall` MUST be 'neutral' "
            "regardless of score sign."
        ),
    )
    rationale: str = Field(
        min_length=1,
        max_length=500,
        description="One or two sentences citing language from the article that drove the label.",
    )


class EntitySentiment(BaseModel):
    """A single named entity mentioned in the article."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    type: EntityType
    sentiment: EntitySentimentLabel = Field(
        description="How the article portrays this entity (not the entity's own sentiment)."
    )
    mentions: int = Field(
        ge=1, description="Number of times the entity appears in the article body."
    )


class KeyClaim(BaseModel):
    """A factual or evaluative claim made in the article."""

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(
        min_length=1,
        max_length=500,
        description="The claim, paraphrased in one sentence. Must be present in the article — do not infer.",
    )
    stance: Stance = Field(
        description=(
            "asserted = author states it; "
            "reported = attributed to a named source; "
            "speculated = framed as possibility, opinion, or forecast."
        )
    )


class LLMAnalysis(BaseModel):
    """The full LLM output. Strict — extra fields rejected so we catch hallucinated keys early."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(
        min_length=1,
        max_length=800,
        description="Two or three neutral sentences. No editorial framing.",
    )
    sentiment: SentimentBlock
    entities: list[EntitySentiment] = Field(
        default_factory=list,
        max_length=20,
        description="Up to 20 most prominent entities. Omit if none.",
    )
    key_claims: list[KeyClaim] = Field(
        default_factory=list,
        max_length=10,
        description="Up to 10 most load-bearing claims. Each must be supported by the article text.",
    )
    topics: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Short topic tags, lowercase, hyphenated. e.g. 'monetary-policy', 'climate'.",
    )
