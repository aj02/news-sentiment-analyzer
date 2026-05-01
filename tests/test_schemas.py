"""Schema-level checks: extra fields rejected, enums enforced, bounds applied."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.sentiment import LLMAnalysis


def _good_payload() -> dict:
    return {
        "title": "T",
        "summary": "S",
        "sentiment": {
            "overall": "neutral",
            "score": 0.0,
            "confidence": 0.7,
            "rationale": "r",
        },
        "entities": [],
        "key_claims": [],
        "topics": [],
    }


def test_strict_extra_fields_rejected():
    payload = _good_payload()
    payload["unexpected"] = "should fail"
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


def test_score_bounds():
    payload = _good_payload()
    payload["sentiment"]["score"] = 1.5
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


def test_invalid_overall_label_rejected():
    payload = _good_payload()
    payload["sentiment"]["overall"] = "very-positive"
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


def test_entity_type_enum_enforced():
    payload = _good_payload()
    payload["entities"] = [
        {"name": "A", "type": "deity", "sentiment": "neutral", "mentions": 1},
    ]
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


def test_minimal_payload_accepted():
    LLMAnalysis.model_validate(_good_payload())
