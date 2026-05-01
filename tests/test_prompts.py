"""Prompt loader: versions exist on disk; rendered system message embeds JSON schema."""

from __future__ import annotations

import pytest

from app.prompts.loader import load_prompt


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
def test_load_known_versions(version: str):
    bundle = load_prompt(version)
    assert bundle.version == version
    assert bundle.system_template.strip()
    assert bundle.user_template.strip()


def test_unknown_version_raises():
    with pytest.raises(ValueError, match="Unknown prompt version"):
        load_prompt("v999")


def test_system_render_embeds_schema():
    bundle = load_prompt("v3")
    rendered = bundle.render_system()
    # The rendered prompt should embed the LLMAnalysis schema so the model knows
    # what shape to produce — including the new v3 fields.
    assert '"sentiment"' in rendered
    assert '"key_claims"' in rendered
    assert "confidence" in rendered
    # v3 adds these — verify the schema injection picked them up
    assert "subjectivity" in rendered
    assert "certainty" in rendered
    assert "aspects" in rendered
    assert "quotes" in rendered


def test_user_render_includes_article_text():
    bundle = load_prompt("v3")
    rendered = bundle.render_user(
        article_text="Hello world.",
        source_url="https://example.test/x",
        fetched_title="Test Title",
    )
    assert "Hello world." in rendered
    assert "https://example.test/x" in rendered
    assert "Test Title" in rendered
