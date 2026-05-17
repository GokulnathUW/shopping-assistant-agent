"""Unit tests for Tavily trusted-domain search (mocked client)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.tavily_search import search_trusted_domains


class TestTavilySearch(unittest.TestCase):
    @patch("services.tavily_search.TavilyClient")
    @patch("services.tavily_search.TAVILY_API_KEY", new="fake-key")
    def test_search_returns_raw_content_hits(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.return_value = {
            "results": [
                {
                    "url": "https://example.com/a",
                    "title": " A ",
                    "content": "snippet only",
                    "raw_content": " full page body ",
                },
                {
                    "url": "https://example.com/b",
                    "title": "B",
                    "content": "only snippet",
                    "raw_content": "second body",
                },
            ],
        }

        hits = search_trusted_domains(
            "best laptops",
            include_domains=["example.com"],
            max_results=10,
        )

        call_kw = mock_client_cls.return_value.search.call_args.kwargs
        self.assertTrue(call_kw["include_raw_content"])
        self.assertEqual(call_kw["max_results"], 10)
        self.assertEqual(call_kw["include_domains"], ["example.com"])

        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].url, "https://example.com/a")
        self.assertEqual(hits[0].title, " A ")
        self.assertEqual(hits[0].raw_content, " full page body ")
        self.assertEqual(hits[1].raw_content, "second body")

    @patch("services.tavily_search.TavilyClient")
    @patch("services.tavily_search.TAVILY_API_KEY", new="fake-key")
    def test_search_passes_empty_include_domains_list(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.return_value = {"results": []}

        search_trusted_domains("q", include_domains=[])

        call_kw = mock_client_cls.return_value.search.call_args.kwargs
        self.assertEqual(call_kw["include_domains"], [])

    @patch("services.tavily_search.TavilyClient")
    @patch("services.tavily_search.TAVILY_API_KEY", new="fake-key")
    def test_search_returns_empty_on_api_error(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.side_effect = RuntimeError("network")

        hits = search_trusted_domains("q", include_domains=["x.com"])

        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
