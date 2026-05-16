"""
Unit tests for category extraction LangGraph (mocked LLM).
Run: uv run python tests/test_category_graph.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from langgraph.types import Command

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agent.graph import create_category_graph  # noqa: E402
from schemas.category_extraction import (  # noqa: E402
    CategoryComplete,
    CategoryNeedsClarification,
    CategoryNoShoppingIntent,
)


class CategoryGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.thread_config = {"configurable": {"thread_id": "test-thread-graph"}}

    def test_empty_query_sets_error_terminal(self) -> None:
        graph = create_category_graph()
        out = graph.invoke({"user_query": ""}, config=self.thread_config)
        self.assertEqual(out["terminal"], "error")
        self.assertEqual(out.get("pending_questions"), [])

    def test_no_shopping_intent_ends(self) -> None:
        with patch(
            "agent.nodes.extract_category",
            return_value=CategoryNoShoppingIntent(status="no_shopping_intent"),
        ):
            graph = create_category_graph()
            out = graph.invoke(
                {"user_query": "what is the weather"},
                config=self.thread_config,
            )
        self.assertEqual(out["terminal"], "no_shopping_intent")

    def test_complete_without_clarification(self) -> None:
        with patch(
            "agent.nodes.extract_category",
            return_value=CategoryComplete(status="complete", category="Earbuds"),
        ):
            graph = create_category_graph()
            out = graph.invoke({"user_query": "wireless earbuds"}, config=self.thread_config)
        self.assertEqual(out["terminal"], "complete")
        self.assertEqual(out["category_result"]["category"], "Earbuds")
        self.assertNotIn("__interrupt__", out)

    def test_clarification_then_complete(self) -> None:
        with patch(
            "agent.nodes.extract_category",
            side_effect=[
                CategoryNeedsClarification(
                    status="needs_clarification",
                    questions=["In-ear or over-ear?"],
                ),
                CategoryComplete(status="complete", category="Over-ear headphones"),
            ],
        ):
            graph = create_category_graph()
            first = graph.invoke({"user_query": "headphones"}, config=self.thread_config)
            self.assertIn("__interrupt__", first)
            self.assertEqual(first["pending_questions"], ["In-ear or over-ear?"])

            second = graph.invoke(Command(resume="Over-ear"), config=self.thread_config)

        self.assertEqual(second["terminal"], "complete")
        self.assertEqual(second["clarification_rounds_completed"], 1)
        ctx = second.get("clarification_context") or ""
        self.assertIn("Q: In-ear or over-ear?", ctx)
        self.assertIn("A: Over-ear", ctx)

    def test_third_extraction_uses_final_attempt(self) -> None:
        calls: list[bool] = []

        def fake_extract(
            _query: str,
            *,
            clarification_context: str = "",
            final_attempt: bool = False,
        ):
            calls.append(final_attempt)
            n = len(calls)
            if n == 1:
                return CategoryNeedsClarification(
                    status="needs_clarification",
                    questions=["First?"],
                )
            if n == 2:
                return CategoryNeedsClarification(
                    status="needs_clarification",
                    questions=["Second?"],
                )
            return CategoryComplete(status="complete", category="Resolved")

        with patch("agent.nodes.extract_category", side_effect=fake_extract):
            graph = create_category_graph()
            graph.invoke({"user_query": "ambiguous"}, config=self.thread_config)
            graph.invoke(Command(resume="a"), config=self.thread_config)
            graph.invoke(Command(resume="b"), config=self.thread_config)

        self.assertEqual(calls, [False, False, True])


if __name__ == "__main__":
    unittest.main()
