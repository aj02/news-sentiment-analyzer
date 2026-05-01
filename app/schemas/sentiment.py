"""LLM structured output schema.

The model is told to emit JSON conforming to `LLMAnalysis.model_json_schema()`.
This file is the single source of truth — the prompt embeds the same schema,
and the analyzer validates the model's output against it before returning.

v3 of this schema adds three independent dimensions on top of polarity:
  - `emotions`        Plutchik 8-emotion intensities
  - `subjectivity`    factual ↔ opinionated
  - `certainty`       hedged ↔ definitive
plus two top-level lists:
  - `aspects`         per-topic sentiment (e.g. "inflation outlook: negative")
  - `quotes`          direct quotes with speaker, role, sentiment, framing

All new fields default to neutral / empty so older v1/v2 prompt outputs still
validate.
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


class QuoteFraming(StrEnum):
    SUPPORTIVE = "supportive"  # article frames the quote favorably
    NEUTRAL = "neutral"  # article presents the quote without framing
    SKEPTICAL = "skeptical"  # article challenges, undermines, or rebuts the quote


class EmotionScores(BaseModel):
    """Plutchik 8-emotion intensities, each in [0, 1].

    These do NOT have to sum to 1.0 — multiple emotions can co-occur strongly
    (e.g. an article about disaster relief can score high on both `sadness`
    and `trust`). Set 0.0 for emotions not present.
    """

    model_config = ConfigDict(extra="forbid")

    joy: float = Field(default=0.0, ge=0.0, le=1.0)
    trust: float = Field(default=0.0, ge=0.0, le=1.0)
    fear: float = Field(default=0.0, ge=0.0, le=1.0)
    surprise: float = Field(default=0.0, ge=0.0, le=1.0)
    sadness: float = Field(default=0.0, ge=0.0, le=1.0)
    disgust: float = Field(default=0.0, ge=0.0, le=1.0)
    anger: float = Field(default=0.0, ge=0.0, le=1.0)
    anticipation: float = Field(default=0.0, ge=0.0, le=1.0)


class SentimentBlock(BaseModel):
    """Top-level sentiment of the article — polarity + axes + emotions."""

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
        description="Continuous polarity: -1.0 strongly negative, 0.0 neutral, +1.0 strongly positive.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Self-assessed confidence in the polarity label. If <0.5, `overall` MUST be 'neutral'."
        ),
    )
    rationale: str = Field(
        min_length=1,
        max_length=500,
        description="One or two sentences citing language from the article that drove the polarity label.",
    )

    # ─── Independent axes ────────────────────────────────────────────────
    subjectivity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How opinionated the article is. 0.0 = pure factual reporting; "
            "1.0 = heavily editorialized / commentary. Independent of polarity."
        ),
    )
    certainty: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How definitive the article's claims are. 0.0 = heavily hedged "
            "('could', 'may', 'analysts speculate'); 1.0 = stated as definite fact. "
            "Independent of polarity."
        ),
    )
    emotions: EmotionScores = Field(
        default_factory=EmotionScores,
        description="Plutchik 8-emotion intensities, each in [0, 1].",
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


class Aspect(BaseModel):
    """Aspect-based sentiment: how the article treats a specific topic or issue.

    Different from `entities` — entities are people/orgs/places; aspects are
    *issues* discussed (e.g. 'inflation outlook', 'monsoon impact', 'GST rollout').
    """

    model_config = ConfigDict(extra="forbid")

    aspect: str = Field(
        min_length=1,
        max_length=120,
        description="A topic or issue discussed in the article, in 1-5 words.",
    )
    sentiment: SentimentLabel = Field(description="How the article treats this specific aspect.")
    score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Polarity score for this aspect, -1.0 to +1.0.",
    )
    evidence: str = Field(
        min_length=1,
        max_length=400,
        description="One sentence from or paraphrasing the article that supports this aspect-sentiment.",
    )


class Quote(BaseModel):
    """A direct quote attributed to a named speaker.

    `framing` captures how the article presents the quote — supportive,
    neutral, or skeptical. This is distinct from the quote's own sentiment.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        min_length=1,
        max_length=600,
        description="The quoted text, paraphrased if very long. Stay close to the article wording.",
    )
    speaker: str = Field(
        min_length=1,
        max_length=200,
        description="Name of the person quoted. If not named, use 'Unnamed source' or omit the quote.",
    )
    speaker_role: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "The speaker's role as the article describes them "
            "(e.g. 'RBI Governor', 'opposition leader', 'farmer in Vidarbha')."
        ),
    )
    sentiment: EntitySentimentLabel = Field(
        description="The sentiment expressed by the speaker in the quote itself."
    )
    framing: QuoteFraming = Field(
        description=(
            "How the surrounding article frames the quote: supportive (treated as authoritative), "
            "neutral (presented without framing), or skeptical (challenged or rebutted)."
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
        description="Up to 20 most prominent entities.",
    )
    key_claims: list[KeyClaim] = Field(
        default_factory=list,
        max_length=10,
        description="Up to 10 most load-bearing claims. Each must be supported by the article text.",
    )
    aspects: list[Aspect] = Field(
        default_factory=list,
        max_length=8,
        description="Up to 8 aspect-level sentiments — distinct topics within the article.",
    )
    quotes: list[Quote] = Field(
        default_factory=list,
        max_length=8,
        description="Up to 8 direct quotes with speaker attribution.",
    )
    topics: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Short topic tags, lowercase, hyphenated (e.g. 'monetary-policy', 'monsoon').",
    )
