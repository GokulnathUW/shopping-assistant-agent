"""Batch-run category extraction against ``human_queries.txt``.
   uv run python tests/test_category_extraction_from_queries.py
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx

from config.settings import LOCAL_MODEL_MEDIUM, OLLAMA_BASE_URL
from schemas.category_extraction import (
    CategoryComplete,
    CategoryNeedsClarification,
    CategoryNoShoppingIntent,
)
from services.category_extraction import extract_category

logger = logging.getLogger(__name__)

PROJECT_ROOT = _PROJECT_ROOT
_CATEGORY_EXTRACTION_DIR = PROJECT_ROOT / "tests" / "category_extraction"
QUERIES_PATH = _CATEGORY_EXTRACTION_DIR / "human_queries.txt"
RESULTS_PATH = _CATEGORY_EXTRACTION_DIR / "category_extraction_results.txt"


def _ping_ollama(timeout: float = 5.0) -> bool:
    base = OLLAMA_BASE_URL.rstrip("/")
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{base}/api/tags")
            r.raise_for_status()
    except Exception:
        logger.exception("Ollama unreachable at %s", base)
        return False
    return True


def _load_rows(path: Path) -> list[tuple[str, str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[tuple[str, str, str]] = []
        for row in reader:
            label = (row.get("label") or "").strip()
            query = row.get("query") or ""
            ctx = row.get("clarification_context") or ""
            rows.append((label, query, ctx))
        return rows


def _format_block(
    index: int,
    label: str,
    query: str,
    clarification_context: str,
    result: CategoryComplete | CategoryNeedsClarification | CategoryNoShoppingIntent | None,
) -> str:
    ctx_display = clarification_context if clarification_context.strip() else "(empty)"
    lines = [
        "=" * 80,
        f"# case={index} label={label}",
        "=" * 80,
        "query:",
        query.strip(),
        "",
        "clarification_context:",
        ctx_display,
        "",
    ]
    if result is None:
        lines.extend(["outcome: NONE (call failed, invalid JSON, or unknown status)", ""])
        return "\n".join(lines)

    lines.extend(
        [
            f"outcome: {result.status}",
            "payload:",
            json.dumps(result.model_dump(), indent=2, ensure_ascii=False),
            "",
        ]
    )
    return "\n".join(lines)


def run_batch() -> Path:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not QUERIES_PATH.is_file():
        raise FileNotFoundError(f"Missing query file: {QUERIES_PATH}")

    if not _ping_ollama():
        sys.stderr.write(
            f"Aborting: Ollama not reachable at {OLLAMA_BASE_URL!r}. Start Ollama and retry.\n"
        )
        sys.exit(1)

    rows = _load_rows(QUERIES_PATH)
    blocks: list[str] = [
        "category_extraction batch results",
        f"model: {LOCAL_MODEL_MEDIUM}",
        f"queries_file: {QUERIES_PATH.relative_to(PROJECT_ROOT)}",
        "",
    ]

    for i, (label, query, ctx) in enumerate(rows, start=1):
        logger.info("Running case %s/%s %s", i, len(rows), label)
        try:
            parsed = extract_category(query, clarification_context=ctx)
        except Exception:
            logger.exception("Unexpected error for label=%s", label)
            parsed = None
            blocks.append(
                "\n".join(
                    [
                        "=" * 80,
                        f"# case={i} label={label}",
                        "=" * 80,
                        "query:",
                        query.strip(),
                        "",
                        "clarification_context:",
                        ctx if ctx.strip() else "(empty)",
                        "",
                        "outcome: EXCEPTION (see logs)",
                        "",
                    ]
                )
            )
            continue

        blocks.append(_format_block(i, label, query, ctx, parsed))

    RESULTS_PATH.write_text("\n".join(blocks), encoding="utf-8")
    logger.info("Wrote %s", RESULTS_PATH)
    return RESULTS_PATH


if __name__ == "__main__":
    run_batch()
