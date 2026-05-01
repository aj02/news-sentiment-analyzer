"""Schema-level checks: extra fields rejected, enums enforced, bounds applied,
v3 axes (subjectivity / certainty / emotions) and structures (aspects / quotes) validated."""

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


# ─── Existing v2 invariants ─────────────────────────────────────────────────


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
    """v2-shape payload (no aspects, quotes, or new sentiment axes) still validates —
    new fields default to neutral / empty so v2 prompt outputs do not break."""
    m = LLMAnalysis.model_validate(_good_payload())
    assert m.aspects == []
    assert m.quotes == []
    assert m.sentiment.subjectivity == 0.5
    assert m.sentiment.certainty == 0.5
    assert m.sentiment.emotions.joy == 0.0


# ─── v3: subjectivity / certainty bounds ────────────────────────────────────


def test_subjectivity_must_be_in_unit_interval():
    payload = _good_payload()
    payload["sentiment"]["subjectivity"] = 1.5
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


def test_certainty_must_be_in_unit_interval():
    payload = _good_payload()
    payload["sentiment"]["certainty"] = -0.1
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


# ─── v3: emotion bounds ─────────────────────────────────────────────────────


def test_emotion_must_be_in_unit_interval():
    payload = _good_payload()
    payload["sentiment"]["emotions"] = {"joy": 1.2}
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


def test_emotion_extra_key_rejected():
    payload = _good_payload()
    payload["sentiment"]["emotions"] = {"joy": 0.5, "envy": 0.3}
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


# ─── v3: aspects ────────────────────────────────────────────────────────────


def test_aspect_validates():
    payload = _good_payload()
    payload["aspects"] = [
        {
            "aspect": "monsoon risk",
            "sentiment": "negative",
            "score": -0.5,
            "evidence": "Governor warned an uncertain monsoon could disrupt inflation.",
        },
    ]
    m = LLMAnalysis.model_validate(payload)
    assert m.aspects[0].aspect == "monsoon risk"


def test_aspect_invalid_sentiment_label_rejected():
    payload = _good_payload()
    payload["aspects"] = [
        {"aspect": "x", "sentiment": "very-bad", "score": 0.0, "evidence": "e"},
    ]
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


# ─── v3: quotes ─────────────────────────────────────────────────────────────


def test_quote_validates():
    payload = _good_payload()
    payload["quotes"] = [
        {
            "text": "On a glide path to 4%.",
            "speaker": "Shaktikanta Das",
            "speaker_role": "RBI Governor",
            "sentiment": "positive",
            "framing": "supportive",
        },
    ]
    m = LLMAnalysis.model_validate(payload)
    assert m.quotes[0].speaker == "Shaktikanta Das"
    assert m.quotes[0].framing.value == "supportive"


def test_quote_framing_enum_enforced():
    payload = _good_payload()
    payload["quotes"] = [
        {
            "text": "x",
            "speaker": "y",
            "speaker_role": "z",
            "sentiment": "positive",
            "framing": "enthusiastic",  # not in the enum
        },
    ]
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)


def test_quote_sentiment_label_rejects_mixed():
    """Quote sentiment uses the 3-value EntitySentimentLabel — `mixed` is not allowed."""
    payload = _good_payload()
    payload["quotes"] = [
        {
            "text": "x",
            "speaker": "y",
            "speaker_role": "z",
            "sentiment": "mixed",
            "framing": "neutral",
        },
    ]
    with pytest.raises(ValidationError):
        LLMAnalysis.model_validate(payload)
