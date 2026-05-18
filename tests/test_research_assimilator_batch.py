"""Batch assimilator: summarizer JSON → digest → market brief per row.

Reads ``research_summarizer_output.json`` by default; writes JSON for follow-up batch.

  uv run python tests/test_research_assimilator_batch.py
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

from config.settings import LOCAL_MODEL_SMALL, OLLAMA_BASE_URL
from services.market_research import assimilate_digest, build_digest_from_summarize_blocks

from tests.research_batch_helpers import (
    ASSIMILATOR_OUTPUT_PATH,
    RESEARCH_ASSIMILATOR_SCHEMA_VERSION,
    SUMMARIZER_OUTPUT_PATH,
    assert_summarizer_doc,
    read_json,
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


def run_batch(*, summarizer_path: Path, output_path: Path) -> Path:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not summarizer_path.is_file():
        raise FileNotFoundError(f"Missing summarizer output: {summarizer_path}")

    if not _ping_ollama():
        sys.stderr.write(
            f"Aborting: Ollama not reachable at {OLLAMA_BASE_URL!r}. Start Ollama and retry.\n",
        )
        sys.exit(1)

    summarizer_doc = read_json(summarizer_path)
    assert_summarizer_doc(summarizer_doc)

    out_rows: list[dict] = []

    for row in summarizer_doc["rows"]:
        label = row.get("label") or ""
        blocks = row.get("summarize_blocks")
        if not isinstance(blocks, list):
            blocks = []

        base_pass = {
            "label": row.get("label", ""),
            "user_query": row.get("user_query", ""),
            "clarification_context": row.get("clarification_context", ""),
            "category": row.get("category", ""),
        }

        if row.get("outcome") != "ok":
            out_rows.append(
                {
                    **base_pass,
                    "summarizer_outcome": row.get("outcome"),
                    "summarizer_detail": row.get("detail"),
                    "digest_chars": 0,
                    "assimilated_brief": "",
                    "outcome": "skipped",
                    "detail": "summarizer_row_not_ok",
                },
            )
            continue

        digest_input = build_digest_from_summarize_blocks(blocks)
        if not digest_input.strip():
            out_rows.append(
                {
                    **base_pass,
                    "summarizer_outcome": "ok",
                    "summarizer_detail": None,
                    "digest_chars": 0,
                    "assimilated_brief": "",
                    "outcome": "skipped",
                    "detail": "empty_digest_no_summaries",
                },
            )
            continue

        logger.info("Assimilating %s", label)
        try:
            brief = assimilate_digest(digest_input)
        except Exception:
            logger.exception("Assimilate failed for label=%s", label)
            out_rows.append(
                {
                    **base_pass,
                    "summarizer_outcome": "ok",
                    "summarizer_detail": None,
                    "digest_chars": len(digest_input),
                    "assimilated_brief": "",
                    "outcome": "error",
                    "detail": "assimilate_exception",
                },
            )
            continue

        out_rows.append(
            {
                **base_pass,
                "summarizer_outcome": "ok",
                "summarizer_detail": None,
                "digest_chars": len(digest_input),
                "assimilated_brief": brief,
                "outcome": "ok" if brief.strip() else "skipped",
                "detail": None if brief.strip() else "empty_brief",
            },
        )

    doc = {
        "schema_version": RESEARCH_ASSIMILATOR_SCHEMA_VERSION,
        "stage": "assimilator",
        "summarizer_input": relative_repo_path(summarizer_path),
        "model": LOCAL_MODEL_SMALL,
        "rows": out_rows,
    }
    write_json(output_path, doc)
    logger.info("Wrote %s", output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Research assimilator batch.")
    parser.add_argument(
        "--input",
        type=Path,
        dest="summarizer_path",
        default=SUMMARIZER_OUTPUT_PATH,
        help="Summarizer JSON path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ASSIMILATOR_OUTPUT_PATH,
        help="Output JSON path",
    )
    args = parser.parse_args()
    run_batch(summarizer_path=args.summarizer_path, output_path=args.output)


if __name__ == "__main__":
    main()
