"""Batch-run market study (Ollama) against ``market_study_queries.txt``.
   uv run python tests/test_market_study_from_queries.py
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

from config.settings import LOCAL_MODEL_SMALL, OLLAMA_BASE_URL
from schemas.market_study import MarketStudyQuestions
from services.market_study import generate_market_study_questions

logger = logging.getLogger(__name__)

PROJECT_ROOT = _PROJECT_ROOT
_MARKET_STUDY_DIR = PROJECT_ROOT / "tests" / "market_study"
QUERIES_PATH = _MARKET_STUDY_DIR / "market_study_queries.txt"
RESULTS_PATH = _MARKET_STUDY_DIR / "market_study_results.txt"


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
            if label.startswith("#"):
                continue
            query = row.get("user_query") or ""
            ctx = row.get("clarification_context") or ""
            rows.append((label, query, ctx))
        return rows


def _format_block(
    index: int,
    label: str,
    user_query: str,
    clarification_context: str,
    result: MarketStudyQuestions | None,
) -> str:
    ctx_display = clarification_context if clarification_context.strip() else "(empty)"
    lines = [
        "=" * 80,
        f"# case={index} label={label}",
        "=" * 80,
        "user_query:",
        user_query.strip(),
        "",
        "clarification_context:",
        ctx_display,
        "",
    ]
    if result is None:
        lines.extend(["outcome: NONE (call failed, invalid JSON, or validation failed)", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "outcome: ok",
            "market_study_questions:",
            json.dumps(result.questions, indent=2, ensure_ascii=False),
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
            f"Aborting: Ollama not reachable at {OLLAMA_BASE_URL!r}. Start Ollama and retry.\n",
        )
        sys.exit(1)

    rows = _load_rows(QUERIES_PATH)
    if not rows:
        sys.stderr.write(f"No data rows found in {QUERIES_PATH}\n")
        sys.exit(1)

    blocks: list[str] = [
        "market_study batch results",
        f"model: {LOCAL_MODEL_SMALL}",
        f"queries_file: {QUERIES_PATH.relative_to(PROJECT_ROOT)}",
        "",
    ]

    for i, (label, user_query, ctx) in enumerate(rows, start=1):
        logger.info("Running case %s/%s %s", i, len(rows), label)
        try:
            parsed = generate_market_study_questions(
                user_query,
                clarification_context=ctx,
            )
        except Exception:
            logger.exception("Unexpected error for label=%s", label)
            parsed = None
            blocks.append(
                "\n".join(
                    [
                        "=" * 80,
                        f"# case={i} label={label}",
                        "=" * 80,
                        "user_query:",
                        user_query.strip(),
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

        blocks.append(_format_block(i, label, user_query, ctx, parsed))

    RESULTS_PATH.write_text("\n".join(blocks), encoding="utf-8")
    logger.info("Wrote %s", RESULTS_PATH)
    return RESULTS_PATH


if __name__ == "__main__":
    run_batch()
