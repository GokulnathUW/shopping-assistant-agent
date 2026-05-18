"""Shared paths + parsers for research pipeline batch tests (summarizer → assimilator → follow-up)."""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKET_STUDY_DIR = PROJECT_ROOT / "tests" / "market_study"
SOURCE_FINDER_RESULTS_PATH = PROJECT_ROOT / "tests" / "source_finder" / "source_finder_results.txt"

MARKET_STUDY_QUERIES_PATH = MARKET_STUDY_DIR / "market_study_queries.txt"
SUMMARIZER_OUTPUT_PATH = MARKET_STUDY_DIR / "research_summarizer_output.json"
ASSIMILATOR_OUTPUT_PATH = MARKET_STUDY_DIR / "research_assimilator_output.json"
FOLLOWUP_OUTPUT_PATH = MARKET_STUDY_DIR / "research_followup_output.json"

RESEARCH_SUMMARIZER_SCHEMA_VERSION = 1
RESEARCH_ASSIMILATOR_SCHEMA_VERSION = 1
RESEARCH_FOLLOWUP_SCHEMA_VERSION = 1


def normalize_category_key(category: str) -> str:
    return " ".join(category.strip().split()).lower()


def extract_json_array_after_prefix(block: str, prefix: str) -> list | None:
    """Parse a JSON array that appears right after ``prefix`` (e.g. ``domains:\\n``)."""

    pos = block.find(prefix)
    if pos == -1:
        return None
    start = block.find("[", pos + len(prefix))
    if start == -1:
        return None
    depth = 0
    for k in range(start, len(block)):
        ch = block[k]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    arr = json.loads(block[start : k + 1])
                except json.JSONDecodeError:
                    return None
                return arr if isinstance(arr, list) else None
    return None


def parse_domains_by_category(source_finder_results_path: Path) -> dict[str, list[str]]:
    """
    Map normalized category string → domain list for blocks with ``outcome: ok``.
    Categories without usable domains are omitted.
    """

    text = source_finder_results_path.read_text(encoding="utf-8")
    blocks = text.split("=" * 80)
    out: dict[str, list[str]] = {}

    for block in blocks:
        if "outcome: ok" not in block:
            continue
        cat_m = re.search(r"category:\s*\n\s*([^\n]+)", block)
        if not cat_m:
            continue
        category_raw = cat_m.group(1).strip()
        key = normalize_category_key(category_raw)
        domains_raw = extract_json_array_after_prefix(block, "domains:")
        if not domains_raw:
            logger.warning("Parsing domains failed for category %r", category_raw)
            continue
        domains: list[str] = []
        for d in domains_raw:
            if isinstance(d, str) and d.strip():
                domains.append(d.strip())
        if domains:
            out[key] = domains

    return out


def load_market_study_query_rows(queries_path: Path) -> list[dict[str, str]]:
    """CSV columns: label, user_query, clarification_context, category."""

    with queries_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append(
                {
                    "label": (row.get("label") or "").strip(),
                    "user_query": row.get("user_query") or "",
                    "clarification_context": row.get("clarification_context") or "",
                    "category": (row.get("category") or "").strip(),
                }
            )
        return rows


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def assert_summarizer_doc(doc: dict) -> None:
    """Validate summarizer batch JSON (for assimilator input)."""

    if doc.get("schema_version") != RESEARCH_SUMMARIZER_SCHEMA_VERSION:
        raise ValueError(
            f"summarizer doc schema_version must be {RESEARCH_SUMMARIZER_SCHEMA_VERSION}, "
            f"got {doc.get('schema_version')!r}",
        )
    if doc.get("stage") != "summarizer":
        raise ValueError(f"summarizer doc stage must be 'summarizer', got {doc.get('stage')!r}")
    rows = doc.get("rows")
    if not isinstance(rows, list):
        raise ValueError("summarizer doc 'rows' must be a list")


def assert_assimilator_doc(doc: dict) -> None:
    """Validate assimilator batch JSON (for follow-up input)."""

    if doc.get("schema_version") != RESEARCH_ASSIMILATOR_SCHEMA_VERSION:
        raise ValueError(
            f"assimilator doc schema_version must be {RESEARCH_ASSIMILATOR_SCHEMA_VERSION}, "
            f"got {doc.get('schema_version')!r}",
        )
    if doc.get("stage") != "assimilator":
        raise ValueError(f"assimilator doc stage must be 'assimilator', got {doc.get('stage')!r}")
    rows = doc.get("rows")
    if not isinstance(rows, list):
        raise ValueError("assimilator doc 'rows' must be a list")
