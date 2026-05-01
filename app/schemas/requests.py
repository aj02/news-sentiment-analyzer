"""Request bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl = Field(description="Absolute URL of the article to analyze.")
    force_refresh: bool = Field(
        default=False,
        description="If true, bypass cache lookup but still write the new result to cache.",
    )


class AnalyzeFeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feed_url: HttpUrl = Field(description="Absolute URL of an RSS or Atom feed.")
    limit: int = Field(default=10, ge=1, le=50, description="Max items to analyze from the feed.")
    force_refresh: bool = Field(default=False)
