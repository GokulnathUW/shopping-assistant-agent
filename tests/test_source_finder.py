"""
Batch-run trusted source domains (Groq) against categories.txt file.
   uv run python tests/test_source_finder.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import GROQ_API_KEY, GROQ_MODEL_SMALL  # noqa: E402
from services.trusted_sources import fetch_trusted_sources_domains  # noqa: E402

logger = logging.getLogger(__name__)

PROJECT_ROOT = _PROJECT_ROOT
_SOURCE_FINDER_DIR = PROJECT_ROOT / "tests" / "source_finder"
CATEGORIES_PATH = _SOURCE_FINDER_DIR / "categories.txt"
RESULTS_PATH = _SOURCE_FINDER_DIR / "source_finder_results.txt"


def _load_categories(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, category) for each active line."""

    text = path.read_text(encoding="utf-8")
    out: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append((lineno, stripped))
    return out


def _format_block(case_index: int, source_line: int, category: str, domains: list[str] | None) -> str:
    lines = [
        "=" * 80,
        f"# case={case_index} source_line={source_line}",
        "=" * 80,
        "category:",
        category,
        "",
    ]
    if domains is None:
        lines.extend(["outcome: NONE (missing key, Groq error, invalid JSON, or validation failed)", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "outcome: ok",
            "domains:",
            json.dumps(domains, indent=2, ensure_ascii=False),
            "",
        ]
    )
    return "\n".join(lines)


def run_batch() -> Path:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not GROQ_API_KEY:
        sys.stderr.write(
            "Aborting: GROQ_API_KEY is not set. Add it to .env and reload.\n",
        )
        sys.exit(1)

    if not CATEGORIES_PATH.is_file():
        raise FileNotFoundError(f"Missing categories file: {CATEGORIES_PATH}")

    pairs = _load_categories(CATEGORIES_PATH)
    if not pairs:
        sys.stderr.write(f"No categories found in {CATEGORIES_PATH}\n")
        sys.exit(1)

    blocks: list[str] = [
        "trusted_sources (source finder) batch results",
        f"model: {GROQ_MODEL_SMALL}",
        f"categories_file: {CATEGORIES_PATH.relative_to(PROJECT_ROOT)}",
        "",
    ]

    for case_index, (source_line, category) in enumerate(pairs, start=1):
        logger.info("Running case %s/%s %r", case_index, len(pairs), category)
        try:
            domains = fetch_trusted_sources_domains(category)
        except Exception:
            logger.exception("Unexpected error for category=%r", category)
            domains = None

        blocks.append(_format_block(case_index, source_line, category, domains))

    RESULTS_PATH.write_text("\n".join(blocks), encoding="utf-8")
    logger.info("Wrote %s", RESULTS_PATH)
    return RESULTS_PATH


if __name__ == "__main__":
    run_batch()
