"""VCR-style fixtures: canned LLM JSON responses keyed by URL.

These let tests run without hitting any real provider. The fake LLM client
in `tests/conftest.py` looks up the matching response by URL.
"""

from __future__ import annotations

# Canned response for the "neutral Fed rates" article.
FED_RATES_RESPONSE = {
    "title": "Fed holds rates steady amid inflation progress",
    "summary": (
        "The Federal Reserve kept its benchmark interest rate unchanged at a range of 4.25% to 4.5%. "
        "Chair Jerome Powell said the committee was in no hurry to adjust policy further."
    ),
    "sentiment": {
        "overall": "neutral",
        "score": 0.0,
        "confidence": 0.85,
        "rationale": "Pure factual reporting of a policy decision; no evaluative language.",
    },
    "entities": [
        {"name": "Federal Reserve", "type": "org", "sentiment": "neutral", "mentions": 2},
        {"name": "Jerome Powell", "type": "person", "sentiment": "neutral", "mentions": 1},
    ],
    "key_claims": [
        {"claim": "The Fed held its benchmark rate at 4.25-4.5%.", "stance": "asserted"},
        {"claim": "The committee is in no hurry to adjust policy.", "stance": "reported"},
    ],
    "topics": ["monetary-policy", "federal-reserve"],
}

# Canned response demonstrating the confidence-clamp rule. Confidence is below
# 0.5 but the model "incorrectly" reports overall=positive — the analyzer must
# clamp to neutral.
LOW_CONFIDENCE_RESPONSE = {
    "title": "GreenLine breaks ground",
    "summary": "Construction began on the GreenLine transit project. Public reaction was mixed.",
    "sentiment": {
        "overall": "positive",
        "score": 0.6,
        "confidence": 0.4,
        "rationale": "Officials called it a milestone but residents were divided.",
    },
    "entities": [
        {"name": "GreenLine", "type": "product", "sentiment": "neutral", "mentions": 2},
    ],
    "key_claims": [
        {"claim": "GreenLine transit project began construction.", "stance": "asserted"},
    ],
    "topics": ["transit"],
}

# Mapping URL → canned response. The fake LLM client picks by source_url
# substring.
RESPONSES_BY_URL_KEYWORD: dict[str, dict] = {
    "fed-rates": FED_RATES_RESPONSE,
    "greenline": LOW_CONFIDENCE_RESPONSE,
}
