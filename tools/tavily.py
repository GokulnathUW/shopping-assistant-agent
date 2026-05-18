import logging
from collections.abc import Sequence

from tavily import TavilyClient

from config.settings import (
    TAVILY_API_KEY,
    TAVILY_SEARCH_MAX_RESULTS,
)
from schemas.tavily import TavilySearchHit

logger = logging.getLogger(__name__)


def search_trusted_domains(
    query: str,
    *,
    trusted_domains: Sequence[str],
    max_results: int | None = None,
) -> list[TavilySearchHit]:
    """Run Tavily search restricted to trusted sources; returns hits with full content."""

    q = query.strip()
    if not q:
        logger.error("search_trusted_domains: empty query")
        return []

    limit = max_results if max_results is not None else TAVILY_SEARCH_MAX_RESULTS

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=q,
            include_domains=trusted_domains,
            max_results=limit,
            include_raw_content=True,
        )
    except Exception:
        logger.exception("Tavily search failed")
        return []

    return [
        TavilySearchHit(url=r["url"], title=r.get("title"), raw_content=r["raw_content"])
        for r in response.get("results") or []
    ]
