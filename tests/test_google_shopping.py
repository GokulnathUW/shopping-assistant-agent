"""Unit tests for SerpAPI Google Shopping service (mocked client)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.google_shopping import fetch_google_shopping_offers


class TestGoogleShopping(unittest.TestCase):
    @patch("services.google_shopping.Client")
    @patch("services.google_shopping.SERPAPI_API_KEY", new="fake-key")
    def test_fetches_and_normalizes_shopping_results_only(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.return_value = {
            "shopping_results": [
                {
                    "title": "Test Widget Pro",
                    "source": "Example Mart",
                    "price": "$49.99",
                    "extracted_price": 49.99,
                    "product_link": "https://example.com/p/1",
                    "thumbnail": "https://cdn.example/t.jpg",
                },
                {
                    "title": "Test Widget Pro",
                    "source": "Example Mart",
                    "price": "$49.99",
                    "extracted_price": 49.99,
                    "product_link": "https://example.com/p/1",
                    "thumbnail": "https://cdn.example/t.jpg",
                },
            ],
        }

        offers = fetch_google_shopping_offers("Test Widget Pro")

        call_kw = mock_client_cls.return_value.search.call_args.kwargs
        self.assertEqual(call_kw["engine"], "google_shopping")
        self.assertEqual(call_kw["q"], "Test Widget Pro")
        self.assertEqual(call_kw["sort_by"], 1)
        self.assertEqual(call_kw["on_sale"], "true")

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].store, "Example Mart")
        self.assertEqual(offers[0].extracted_price, 49.99)

    @patch("services.google_shopping.Client")
    @patch("services.google_shopping.SERPAPI_API_KEY", new="fake-key")
    def test_passes_max_price_when_budget_set(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.return_value = {"shopping_results": []}

        fetch_google_shopping_offers("widget", max_price=199.99)

        self.assertEqual(
            mock_client_cls.return_value.search.call_args.kwargs["max_price"],
            199.99,
        )

    @patch("services.google_shopping.Client")
    @patch("services.google_shopping.SERPAPI_API_KEY", new="fake-key")
    def test_omits_max_price_when_none_or_non_positive(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.return_value = {"shopping_results": []}

        fetch_google_shopping_offers("widget", max_price=None)
        self.assertNotIn("max_price", mock_client_cls.return_value.search.call_args.kwargs)

        mock_client_cls.return_value.search.reset_mock()
        fetch_google_shopping_offers("widget", max_price=0)
        self.assertNotIn("max_price", mock_client_cls.return_value.search.call_args.kwargs)

    @patch("services.google_shopping.Client")
    @patch("services.google_shopping.SERPAPI_API_KEY", new="fake-key")
    def test_passes_location_when_given(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.return_value = {"shopping_results": []}

        fetch_google_shopping_offers("x", location="Austin, TX")

        self.assertEqual(
            mock_client_cls.return_value.search.call_args.kwargs["location"],
            "Austin, TX",
        )

    @patch("services.google_shopping.Client")
    @patch("services.google_shopping.SERPAPI_API_KEY", new="fake-key")
    def test_returns_empty_on_api_error_field(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.return_value = {"error": "Invalid API key"}

        offers = fetch_google_shopping_offers("coffee maker")

        self.assertEqual(offers, [])

    @patch("services.google_shopping.Client")
    @patch("services.google_shopping.SERPAPI_API_KEY", new="fake-key")
    def test_returns_empty_on_http_failure(self, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value.search.side_effect = RuntimeError("network")

        offers = fetch_google_shopping_offers("x")

        self.assertEqual(offers, [])


if __name__ == "__main__":
    unittest.main()
