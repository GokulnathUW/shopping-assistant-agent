"""Render the category LangGraph to ``agent_viz/`` (PNG + Mermaid source).

Run from repo root:
  uv run python scripts/export_category_graph_visual.py

PNG uses ``draw_mermaid_png`` (mermaid.ink API by default; needs network).
Local rendering: ``LANGGRAPH_GRAPH_DRAW_METHOD=pyppeteer``.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VIZ_DIR = _ROOT / "agent_viz"
_PNG_PATH = _VIZ_DIR / "category_graph.png"
_MMD_PATH = _VIZ_DIR / "category_graph.mmd"
_DRAW_METHOD_ENV = "LANGGRAPH_GRAPH_DRAW_METHOD"

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.runnables.graph import MermaidDrawMethod  # noqa: E402

from agent.graph import create_category_graph  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _VIZ_DIR.mkdir(parents=True, exist_ok=True)

    compiled = create_category_graph()
    lc_graph = compiled.get_graph()

    mermaid = lc_graph.draw_mermaid()
    _MMD_PATH.write_text(mermaid, encoding="utf-8")
    logger.info("Wrote %s", _MMD_PATH.relative_to(_ROOT))

    method_raw = os.environ.get(_DRAW_METHOD_ENV, "api").strip().lower()
    draw_method = (
        MermaidDrawMethod.PYPPETEER
        if method_raw == "pyppeteer"
        else MermaidDrawMethod.API
    )
    try:
        lc_graph.draw_mermaid_png(
            output_file_path=str(_PNG_PATH),
            draw_method=draw_method,
            max_retries=5,
            retry_delay=2.0,
        )
        logger.info("Wrote %s", _PNG_PATH.relative_to(_ROOT))
    except Exception:
        logger.exception(
            "PNG export failed; open %s in a Mermaid viewer.",
            _MMD_PATH.relative_to(_ROOT),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
