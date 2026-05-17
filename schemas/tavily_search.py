"""Pydantic boundary for Tavily search hits passed to downstream LLM steps."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TavilySearchHit(BaseModel):
    """One search result; ``raw_content`` is the full page body from Tavily (not the snippet)."""

    url: str = Field(min_length=1)
    title: str | None = None
    raw_content: str = Field(min_length=1)
