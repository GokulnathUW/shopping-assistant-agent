"""Smoke-check `.env`: load bindings, construct SDK clients"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def _strip_outer_quotes(value: str) -> str:
    v = value.strip()
    while len(v) >= 2 and ((v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"'))):
        v = v[1:-1].strip()
    return v


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Return key → raw right-hand-side from `.env` (only names present there)."""
    bindings: dict[str, str] = {}
    if not path.is_file():
        return bindings
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        raw_key, _, raw_rest = line.partition("=")
        key = raw_key.strip()
        if not key or not key.isidentifier():
            continue
        bindings[key] = _strip_outer_quotes(raw_rest)
    return bindings


def _check_groq(_key: str, value: str) -> None:
    from langchain_groq import ChatGroq

    ChatGroq(model="llama-3.3-70b-versatile", api_key=value)
    print("[ok] GROQ_API_KEY: ChatGroq client configured (no invoke)")


def _check_tavily(_key: str, value: str) -> None:
    from tavily import TavilyClient

    TavilyClient(api_key=value)
    print("[ok] TAVILY_API_KEY: TavilyClient instantiated (no search)")


def _check_serpapi(_key: str, value: str) -> None:
    from serpapi import GoogleSearch

    GoogleSearch({"api_key": value})
    print("[ok] SERPAPI_API_KEY: GoogleSearch instantiated (no get)")


def _check_ollama_base(_key: str, value: str) -> None:
    from langchain_ollama import ChatOllama

    ChatOllama(model="llama3.2:latest", base_url=value.rstrip("/"))
    print("[ok] OLLAMA_BASE_URL: ChatOllama targeting configured base")


def _check_unknown_api(name: str, _value: str) -> None:
    print(f"[ok] {name}: set (wire a client later)")


def _truthy_binding(value: str) -> bool:
    return bool(value.strip())


def main() -> int:
    if not ENV_PATH.is_file():
        print(f"[error] missing {ENV_PATH}", file=sys.stderr)
        return 1

    bindings = _parse_dotenv(ENV_PATH)
    load_dotenv(ENV_PATH, override=False)

    checks: dict[str, Callable[[str, str], None]] = {
        "GROQ_API_KEY": _check_groq,
        "TAVILY_API_KEY": _check_tavily,
        "SERPAPI_API_KEY": _check_serpapi,
        "OLLAMA_BASE_URL": _check_ollama_base,
    }

    for name in bindings:
        declared = bindings[name]
        merged = declared or os.getenv(name, "")
        if not _truthy_binding(merged):
            print(f"[skip] {name}: empty or unset")
            continue
        fn = checks.get(name)
        if fn is None and name.endswith("_API_KEY"):
            fn = _check_unknown_api
        if fn is None:
            print(f"[skip] {name}: no smoke check registered")
            continue
        try:
            fn(name, merged)
        except Exception as exc:  # noqa: BLE001 — surface constructor issues for local runs
            print(f"[fail] {name}: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
