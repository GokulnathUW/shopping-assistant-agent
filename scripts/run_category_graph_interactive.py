"""Interactive smoke test for the category LangGraph (real Ollama via extract_category).

Uses ``graph.stream(..., stream_mode=["updates", "values"])`` so each node write and
merged state are visible on the terminal.

From repo root:
  uv run python scripts/run_category_graph_interactive.py

Requires Ollama reachable per config/settings.py. Thread id defaults to
``interactive-demo``; override with env ``CATEGORY_GRAPH_THREAD_ID``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint

from langgraph.types import Command

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.graph import create_category_graph  # noqa: E402


def _print_stream_chunk(mode: str, payload: object) -> None:
    print(f"\n[{mode}]")
    pprint(payload, sort_dicts=False, width=100)


def _run_stream_turn(
    graph,
    cmd: dict[str, str] | Command,
    config: dict,
) -> dict | None:
    """Consume one ``stream`` call; return last merged ``values`` dict (or None)."""
    last_values: dict | None = None
    print("\n======== stream ========")
    for mode, payload in graph.stream(
        cmd,
        config=config,
        stream_mode=["updates", "values"],
    ):
        _print_stream_chunk(mode, payload)
        if mode == "values" and isinstance(payload, dict):
            last_values = payload
    print("======== end stream ========")
    return last_values


def main() -> None:
    thread_id = os.environ.get("CATEGORY_GRAPH_THREAD_ID", "interactive-demo")
    config = {"configurable": {"thread_id": thread_id}}
    graph = create_category_graph()

    print(f"thread_id={thread_id!r} (override with CATEGORY_GRAPH_THREAD_ID)")
    query = input("Shopper request: ").strip()
    if not query:
        print("Empty query — exiting.")
        return

    cmd: dict[str, str] | Command = {"user_query": query}

    while True:
        last = _run_stream_turn(graph, cmd, config)
        if last is None:
            print("No state from stream — exiting.")
            return

        if last.get("__interrupt__"):
            qs = last.get("pending_questions") or []
            print("\n--- Clarification needed ---")
            for i, q in enumerate(qs, 1):
                print(f"  {i}. {q}")
            ans = input("\nYour answer (empty = stop): ").strip()
            if not ans:
                print("Stopped.")
                return
            cmd = Command(resume=ans)
            continue

        print("\n--- Result ---")
        print("terminal:", last.get("terminal"))
        if last.get("category_result"):
            pprint(last["category_result"], sort_dicts=False)
        if last.get("error_message"):
            print("error_message:", last["error_message"])
        return


if __name__ == "__main__":
    main()
