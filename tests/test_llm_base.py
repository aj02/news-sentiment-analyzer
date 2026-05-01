"""LLMClient._decode_json — robustness against fences and prose."""

from __future__ import annotations

import pytest

from app.core.exceptions import LLMError
from app.services.llm.base import LLMClient


def test_strict_json():
    assert LLMClient._decode_json('{"a": 1}') == {"a": 1}


def test_fenced_json():
    text = '```json\n{"a": 2}\n```'
    assert LLMClient._decode_json(text) == {"a": 2}


def test_prose_around_json_recovered():
    text = 'Sure, here you go:\n{"a": 3}\nThanks.'
    assert LLMClient._decode_json(text) == {"a": 3}


def test_empty_raises():
    with pytest.raises(LLMError):
        LLMClient._decode_json("")


def test_no_json_raises():
    with pytest.raises(LLMError):
        LLMClient._decode_json("totally unrelated text with no braces")
