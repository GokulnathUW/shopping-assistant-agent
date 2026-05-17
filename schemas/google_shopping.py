"""Pydantic boundary for normalized Google Shopping (SerpAPI) listings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoogleShoppingOffer(BaseModel):
    """One listing from ``engine=google_shopping`` (store + price for cross-retailer comparison)."""

    title: str = Field(min_length=1)
    store: str | None = None
    price: str | None = None
    extracted_price: float | None = None
    product_link: str | None = None
