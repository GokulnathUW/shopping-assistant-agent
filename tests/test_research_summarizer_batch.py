"""Batch summarizer: market study queries + source_finder domains → Tavily + per-hit summaries.

Writes JSON consumed by ``tests/test_research_assimilator_batch.py``.
Each ``summarize_blocks`` entry has ``framed_question`` and ``sources`` with ``url``, ``title``, ``summary``.

  uv run python tests/test_research_summarizer_batch.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx

from config.settings import LOCAL_MODEL_SMALL, OLLAMA_BASE_URL, TAVILY_API_KEY
from services.market_study import generate_market_study_questions
from services.market_study_research import collect_summaries_for_framed_questions

from tests.research_batch_helpers import (
    MARKET_STUDY_QUERIES_PATH,
    RESEARCH_SUMMARIZER_SCHEMA_VERSION,
    SOURCE_FINDER_RESULTS_PATH,
    SUMMARIZER_OUTPUT_PATH,
    load_market_study_query_rows,
    normalize_category_key,
    parse_domains_by_category,
    relative_repo_path,
    write_json,
)

logger = logging.getLogger(__name__)


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


def run_batch(*, queries_path: Path, source_finder_path: Path, output_path: Path) -> Path:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not queries_path.is_file():
        raise FileNotFoundError(f"Missing queries file: {queries_path}")
    if not source_finder_path.is_file():
        raise FileNotFoundError(f"Missing source finder results: {source_finder_path}")

    if not TAVILY_API_KEY:
        sys.stderr.write(
            "Aborting: TAVILY_API_KEY is not set. Export it or add it to .env and retry.\n",
        )
        sys.exit(1)

    if not _ping_ollama():
        sys.stderr.write(
            f"Aborting: Ollama not reachable at {OLLAMA_BASE_URL!r}. Start Ollama and retry.\n",
        )
        sys.exit(1)

    domain_map = parse_domains_by_category(source_finder_path)
    rows_in = load_market_study_query_rows(queries_path)
    if not rows_in:
        sys.stderr.write(f"No rows in {queries_path}\n")
        sys.exit(1)

    out_rows: list[dict] = []

    for i, row in enumerate(rows_in, start=1):
        label = row["label"]
        if not label or label.startswith("#"):
            continue

        cat_key = normalize_category_key(row["category"])
        domains = domain_map.get(cat_key)

        if not domains:
            logger.warning(
                "Skipping %s: no trusted domains for category %r (normalize_key=%r)",
                label,
                row["category"],
                cat_key,
            )
            out_rows.append(
                {
                    "label": label,
                    "user_query": row["user_query"],
                    "clarification_context": row["clarification_context"],
                    "category": row["category"],
                    "category_key": cat_key,
                    "domains_resolved": [],
                    "outcome": "skipped",
                    "detail": "no_domains_for_category_in_source_finder_ok_blocks",
                    "summarize_blocks": [],
                },
            )
            continue

        logger.info("Summarizer %s/%s %s", i, len(rows_in), label)

        try:
            framed = generate_market_study_questions(
                row["user_query"],
                clarification_context=row["clarification_context"],
            )
        except Exception:
            logger.exception("Framing failed for label=%s", label)
            out_rows.append(
                {
                    "label": label,
                    "user_query": row["user_query"],
                    "clarification_context": row["clarification_context"],
                    "category": row["category"],
                    "category_key": cat_key,
                    "domains_resolved": domains,
                    "outcome": "error",
                    "detail": "framing_exception",
                    "summarize_blocks": [],
                },
            )
            continue

        if framed is None or not framed.questions:
            out_rows.append(
                {
                    "label": label,
                    "user_query": row["user_query"],
                    "clarification_context": row["clarification_context"],
                    "category": row["category"],
                    "category_key": cat_key,
                    "domains_resolved": domains,
                    "outcome": "skipped",
                    "detail": "framing_failed_or_empty_questions",
                    "summarize_blocks": [],
                },
            )
            continue

        try:
            summarize_blocks = collect_summaries_for_framed_questions(
                list(framed.questions),
                domains,
            )
        except Exception:
            logger.exception("Summarize stage failed for label=%s", label)
            out_rows.append(
                {
                    "label": label,
                    "user_query": row["user_query"],
                    "clarification_context": row["clarification_context"],
                    "category": row["category"],
                    "category_key": cat_key,
                    "domains_resolved": domains,
                    "outcome": "error",
                    "detail": "summarize_exception",
                    "summarize_blocks": [],
                },
            )
            continue

        out_rows.append(
            {
                "label": label,
                "user_query": row["user_query"],
                "clarification_context": row["clarification_context"],
                "category": row["category"],
                "category_key": cat_key,
                "domains_resolved": domains,
                "outcome": "ok",
                "detail": None,
                "summarize_blocks": summarize_blocks,
            },
        )

    doc = {
        "schema_version": RESEARCH_SUMMARIZER_SCHEMA_VERSION,
        "stage": "summarizer",
        "inputs": {
            "queries_file": relative_repo_path(queries_path),
            "source_finder_file": relative_repo_path(source_finder_path),
        },
        "models": {
            "framing": LOCAL_MODEL_SMALL,
            "summarize": LOCAL_MODEL_SMALL,
        },
        "rows": out_rows,
    }
    write_json(output_path, doc)
    logger.info("Wrote %s", output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Research summarizer batch (Tavily + summarize).")
    parser.add_argument(
        "--queries",
        type=Path,
        default=MARKET_STUDY_QUERIES_PATH,
        help="CSV: label,user_query,clarification_context,category",
    )
    parser.add_argument(
        "--source-finder",
        type=Path,
        default=SOURCE_FINDER_RESULTS_PATH,
        help="source_finder_results.txt (domains by category)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SUMMARIZER_OUTPUT_PATH,
        help="JSON output path",
    )
    args = parser.parse_args()
    run_batch(queries_path=args.queries, source_finder_path=args.source_finder, output_path=args.output)


if __name__ == "__main__":
    main()
