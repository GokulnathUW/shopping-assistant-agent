"""Smoke-check `.env`: construct SDK clients — no API calls."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _groq() -> None:
    from langchain_groq import ChatGroq

    ChatGroq(model="llama-3.1-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))


def _tavily() -> None:
    from tavily import TavilyClient

    TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def _serpapi() -> None:
    from serpapi import Client

    Client(api_key=os.getenv("SERPAPI_API_KEY"))


def _ollama() -> None:
    from langchain_ollama import ChatOllama

    base = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
    ChatOllama(model="llama3.2:3b", base_url=base.rstrip("/"))


CHECKS: list[tuple[str, Callable[[], None]]] = [
    ("GROQ_API_KEY", _groq),
    ("TAVILY_API_KEY", _tavily),
    ("SERPAPI_API_KEY", _serpapi),
    ("OLLAMA_BASE_URL", _ollama),
]


def main() -> int:
    for attr, fn in CHECKS:
        if attr == "OLLAMA_BASE_URL":
            raw = os.getenv(attr) or "http://localhost:11434"
        else:
            raw = os.getenv(attr)
        if raw is None or not str(raw).strip():
            print(f"[skip] {attr}: empty or unset")
            continue
        try:
            fn()
            print(f"[ok] {attr}: client configured")
        except Exception as exc:  # noqa: BLE001 — smoke script
            print(f"[fail] {attr}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
