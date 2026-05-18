import logging
from collections.abc import Mapping

from serpapi import Client

from config.settings import SERPAPI_API_KEY

from schemas.serpapi_product_purchase import GoogleShoppingOffer

logger = logging.getLogger(__name__)


def _offer_link(row: Mapping[str, object]) -> str | None:
    pl = row.get("product_link")
    lk = row.get("link")
    for candidate in (pl, lk):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _row_to_offer(row: Mapping[str, object]) -> GoogleShoppingOffer | None:
    title_raw = row.get("title")
    if not isinstance(title_raw, str) or not title_raw.strip():
        return None

    src = row.get("source")
    store = src.strip() if isinstance(src, str) and src.strip() else None

    price_raw = row.get("price")
    price = price_raw.strip() if isinstance(price_raw, str) and price_raw.strip() else None

    ep = row.get("extracted_price")

    return GoogleShoppingOffer(
        title=title_raw.strip(),
        store=store,
        price=price,
        extracted_price=ep,
        product_link=_offer_link(row),
    )


def _dedupe_key(row: Mapping[str, object]) -> str:
    title = row.get("title")
    src = row.get("source")
    price = row.get("price")
    return f"{title}|{src}|{price}"


def fetch_google_shopping_offers(
    product_query: str,
    *,
    location: str | None = None,
    gl: str = 'us',
    hl: str = 'en',
    max_price: float | None = None,
) -> list[GoogleShoppingOffer]:
    """SerpAPI ``google_shopping`` search for the given product string; returns normalized offers across retailers."""

    q = product_query.strip()
    if not q:
        logger.error("fetch_google_shopping_offers: empty product_query")
        return []

    params: dict[str, str] = {
        "engine": 'google_shopping',
        "q": q,
        "gl": gl,
        "hl": hl,
        "sort_by": "1", # 1 = price low to high, 2 = price high to low, 3 = relevance
    }

    if location and location.strip():
        params["location"] = location.strip()

    if max_price is not None and max_price > 0:
        params["max_price"] = max_price

    try:
        client = Client(api_key=SERPAPI_API_KEY)
        raw = client.search(**params)
    except Exception:
        logger.exception("SerpAPI Google Shopping request failed")
        return []

    err = raw.get("error")
    if err:
        logger.error("SerpAPI Google Shopping error: %s", err)
        return []

    seen: set[str] = set()
    offers: list[GoogleShoppingOffer] = []
    for row in raw.get('shopping_results', []):
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        offer = _row_to_offer(row)
        if offer is not None:
            offers.append(offer)

    return offers
