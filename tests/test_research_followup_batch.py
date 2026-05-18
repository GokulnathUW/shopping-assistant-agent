"""Batch follow-up question generator: assimilator JSON → JSON questions per row.

Reads ``research_assimilator_output.json`` by default (shopper fields carried from summarizer chain).

  uv run python tests/test_research_followup_batch.py
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
from services.market_study_research import generate_follow_up_questions

from tests.research_batch_helpers import (
    ASSIMILATOR_OUTPUT_PATH,
    FOLLOWUP_OUTPUT_PATH,
    RESEARCH_FOLLOWUP_SCHEMA_VERSION,
    assert_assimilator_doc,
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


def _shopper_context(user_query: str, clarification_context: str) -> str:
    ctx = f"Shopper request:\n{(user_query or '').strip()}\n"
    if (clarification_context or "").strip():
        ctx += f"\nPrior clarification:\n{clarification_context.strip()}\n"
    return ctx


def run_batch(*, assimilator_path: Path, output_path: Path) -> Path:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not assimilator_path.is_file():
        raise FileNotFoundError(f"Missing assimilator output: {assimilator_path}")

    if not _ping_ollama():
        sys.stderr.write(
            f"Aborting: Ollama not reachable at {OLLAMA_BASE_URL!r}. Start Ollama and retry.\n",
        )
        sys.exit(1)

    assimilator_doc = read_json(assimilator_path)
    assert_assimilator_doc(assimilator_doc)

    out_rows: list[dict] = []

    for row in assimilator_doc["rows"]:
        label = row.get("label") or ""

        base_out = {
            "label": row.get("label", ""),
            "user_query": row.get("user_query", ""),
            "clarification_context": row.get("clarification_context", ""),
            "category": row.get("category", ""),
        }

        if row.get("outcome") != "ok" or not (row.get("assimilated_brief") or "").strip():
            out_rows.append(
                {
                    **base_out,
                    "assimilator_outcome": row.get("outcome"),
                    "assimilator_detail": row.get("detail"),
                    "follow_up_questions": [],
                    "outcome": "skipped",
                    "detail": "no_assimilated_brief",
                },
            )
            continue

        shopper_ctx = _shopper_context(row.get("user_query", ""), row.get("clarification_context", ""))
        brief = row.get("assimilated_brief") or ""

        logger.info("Follow-up questions %s", label)
        try:
            qs = generate_follow_up_questions(shopper_ctx, brief)
        except Exception:
            logger.exception("Follow-up generation failed for label=%s", label)
            out_rows.append(
                {
                    **base_out,
                    "assimilator_outcome": "ok",
                    "assimilator_detail": None,
                    "follow_up_questions": [],
                    "outcome": "error",
                    "detail": "follow_up_exception",
                },
            )
            continue

        out_rows.append(
            {
                **base_out,
                "assimilator_outcome": "ok",
                "assimilator_detail": None,
                "follow_up_questions": qs,
                "outcome": "ok" if qs else "skipped",
                "detail": None if qs else "empty_or_unparseable_questions",
            },
        )

    doc = {
        "schema_version": RESEARCH_FOLLOWUP_SCHEMA_VERSION,
        "stage": "follow_up",
        "assimilator_input": relative_repo_path(assimilator_path),
        "model": LOCAL_MODEL_SMALL,
        "rows": out_rows,
    }
    write_json(output_path, doc)
    logger.info("Wrote %s", output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Research follow-up question batch.")
    parser.add_argument(
        "--input",
        type=Path,
        dest="assimilator_path",
        default=ASSIMILATOR_OUTPUT_PATH,
        help="Assimilator JSON path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FOLLOWUP_OUTPUT_PATH,
        help="Output JSON path",
    )
    args = parser.parse_args()
    run_batch(assimilator_path=args.assimilator_path, output_path=args.output)


if __name__ == "__main__":
    main()
