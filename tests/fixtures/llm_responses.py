"""VCR-style fixtures: canned LLM JSON responses keyed by URL.

These let tests run without hitting any real provider. The fake LLM client
in `tests/conftest.py` looks up the matching response by URL.

Responses follow the v3 schema (polarity + subjectivity + certainty + emotions
+ aspects + quotes). Older v2-shape responses still validate because the new
fields default to neutral / empty.
"""

from __future__ import annotations

# Canned response for the RBI policy article (neutral, factual).
RBI_POLICY_RESPONSE = {
    "title": "RBI holds repo rate at 6.50%, raises FY25 growth forecast to 7.2%",
    "summary": (
        "The Reserve Bank of India's Monetary Policy Committee unanimously held the repo rate "
        "at 6.50% and kept its withdrawal-of-accommodation stance. Governor Das said inflation "
        "was on a glide path to 4% but warned of risks from an uncertain monsoon. The MPC "
        "raised its FY25 GDP growth forecast to 7.2%."
    ),
    "sentiment": {
        "overall": "neutral",
        "score": 0.05,
        "confidence": 0.85,
        "rationale": (
            "Straight policy reporting with no evaluative framing. Slight tilt comes from the "
            "upward growth-forecast revision being a positive signal."
        ),
        "subjectivity": 0.10,
        "certainty": 0.88,
        "emotions": {
            "joy": 0.10,
            "trust": 0.55,
            "fear": 0.20,
            "surprise": 0.10,
            "sadness": 0.0,
            "disgust": 0.0,
            "anger": 0.0,
            "anticipation": 0.50,
        },
    },
    "entities": [
        {"name": "Reserve Bank of India", "type": "org", "sentiment": "neutral", "mentions": 2},
        {"name": "Shaktikanta Das", "type": "person", "sentiment": "neutral", "mentions": 1},
    ],
    "key_claims": [
        {
            "claim": "The MPC voted unanimously to hold the repo rate at 6.50%.",
            "stance": "asserted",
        },
        {"claim": "Retail inflation eased to 4.83% in April.", "stance": "asserted"},
    ],
    "aspects": [
        {
            "aspect": "repo rate trajectory",
            "sentiment": "neutral",
            "score": 0.0,
            "evidence": "MPC held the repo rate at 6.50% for a sixth consecutive meeting.",
        },
        {
            "aspect": "monsoon risk",
            "sentiment": "negative",
            "score": -0.30,
            "evidence": "Governor warned an uncertain monsoon could disrupt the inflation trajectory.",
        },
    ],
    "quotes": [
        {
            "text": "On a glide path to the 4% medium-term target.",
            "speaker": "Shaktikanta Das",
            "speaker_role": "RBI Governor",
            "sentiment": "positive",
            "framing": "supportive",
        },
    ],
    "topics": ["monetary-policy", "rbi", "inflation"],
}

# Confidence-clamp test: low confidence + non-neutral overall. Analyzer must clamp.
LOW_CONFIDENCE_RESPONSE = {
    "title": "Bengaluru Suburban Rail Project breaks ground",
    "summary": "Construction began on the Bengaluru Suburban Rail Project. Public reaction was mixed.",
    "sentiment": {
        "overall": "positive",
        "score": 0.6,
        "confidence": 0.4,
        "rationale": "CM called it long overdue but residents were divided.",
        "subjectivity": 0.30,
        "certainty": 0.60,
        "emotions": {
            "joy": 0.15,
            "trust": 0.20,
            "fear": 0.15,
            "surprise": 0.05,
            "sadness": 0.10,
            "disgust": 0.0,
            "anger": 0.10,
            "anticipation": 0.40,
        },
    },
    "entities": [
        {
            "name": "Bengaluru Suburban Rail Project",
            "type": "product",
            "sentiment": "neutral",
            "mentions": 2,
        },
    ],
    "key_claims": [
        {
            "claim": "Construction of the Bengaluru Suburban Rail Project has begun.",
            "stance": "asserted",
        },
    ],
    "aspects": [
        {
            "aspect": "project delivery timeline",
            "sentiment": "negative",
            "score": -0.40,
            "evidence": "Project broke ground ten years after announcement.",
        },
    ],
    "quotes": [],
    "topics": ["urban-transit", "bengaluru"],
}

# Mapping URL keyword → canned response. The fake LLM client picks by source_url
# substring appearing in the user prompt.
RESPONSES_BY_URL_KEYWORD: dict[str, dict] = {
    "rbi-policy": RBI_POLICY_RESPONSE,
    "bengaluru-rail": LOW_CONFIDENCE_RESPONSE,
}
