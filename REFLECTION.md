# Reflection — shopping-assistant-agent

This document records **what we built**, **decisions**, and **why**, so future changes stay intentional. It complements **`AGENT.md`** (how to write code), not replace it.

---

## Product intent

The assistant separates **review-vertical routing** (what kind of product research this is) from **product-specific search** (specs, prices, SKUs). Early steps should output a **coarse editorial category** and a **trusted-domain allowlist** for downstream search (e.g. Tavily `include_domains`), not long spec-heavy labels or biased queries.

---

## Category extraction

### Role

Turn free-text (plus optional clarification Q&A) into exactly one structured outcome:

- **`complete`** — vertical is clear enough for the next pipeline step.
- **`needs_clarification`** — real department / kind forks only (not brand/budget/spec shopping).
- **`no_shopping_intent`** — clearly not shopping research.

### Implementation

- **`services/category_extraction.py`** — LangChain **ChatOllama**, **`JsonOutputParser`**, Pydantic **`schemas/category_extraction.py`** at the boundary.
- **`prompts/category_extraction.py`** — system prompts + user template; **`CATEGORY_EXTRACTION_FORCE_COMPLETE_SYSTEM`** when clarification rounds are exhausted (graph forces a **`complete`** outcome policy in code too).

### Prompt evolution (why)

| Decision | Reason |
|----------|--------|
| **Coarse `category` (e.g. laptop, earbuds, monitor)** | Editorial sites group reviews that way; specs belong in a **later** product-search step, not in Tavily domain selection. |
| **Avoid redundant / contradictory instructions** | Repeating “JSON shape” or bias paragraphs diluted behavior; one authoritative section per concern. |
| **Few-shot count reduced (then expanded again with user rewrites)** | Too many examples anchored small models on wrong templates (e.g. desk question for unrelated queries). Final prompt set is whatever is in **`prompts/category_extraction.py`** now — tuned for clarity vs over-clarification. |
| **Physical vs digital — narrow rule** | Only when **both** tangible and app/subscription are plausible (journal, planner, …). Not for skincare, commute gear, baby gifts, etc., where “digital vs physical” produced nonsense. |
| **`paper notebook` / `journal notebook` vs bare `notebook`** | **Notebook** collides with **notebook PC**; two-word stationery vertical avoids wrong retrieval. |
| **Gift queries must resolve to a real aisle** | Meta labels like “gifts for cooking” are not review verticals — clarify or fail forward via **`needs_clarification`**. |
| **Gibberish → `no_shopping_intent`** | Avoid generic “what are you looking for?” on keyboard mash. |

### LangGraph workflow

- **`agent/graph.py`** — `StateGraph`: **`extract_category`** → conditional **`human_clarification`** loop → **`END`**.
- **`agent/nodes.py`** — **`MAX_CLARIFICATION_ROUNDS = 2`**; third extraction uses **`final_attempt=True`** (force-complete prompt). **`interrupt({"questions": …})`** + **`Command(resume=…)`** with checkpointer (**`InMemorySaver`** by default).
- **`agent/state.py`** — `CategoryTerminal` is **`complete` \| `no_shopping_intent` \| `error`** only — **not** `needs_clarification`, because clarification is a **pause** (`pending_questions` + **`__interrupt__`**), not a terminal outcome.

### Visualization

- **PNG export was removed from `create_category_graph()`** — compiling the graph should not hit the Mermaid API or slow tests.
- **`scripts/export_category_graph_visual.py`** writes **`agent_viz/category_graph.png`** and **`category_graph.mmd`**.

### Interactive debugging

- **`scripts/run_category_graph_interactive.py`** uses **`stream_mode=["updates", "values"]`** so each step’s patches and merged state are visible (vs opaque **`invoke`**).

---

## Trusted editorial sources

### Role

Given **only the coarse category** (not the full shopper query), propose **10–14** apex domains suitable for **`include_domains`**-style allowlists.

### Why category-only user message

The full query (“Blender”, “Steam”, …) biases the model toward niche sites that are not better **general** review sources for the vertical. **`TRUSTED_SOURCES_USER_TEMPLATE`** is **`Product category: {category}`** only.

### Implementation

- **`services/trusted_sources.py`** — **ChatGroq** + **`GROQ_MODEL_SMALL`**, same template pattern as category extraction; **`fetch_trusted_sources_domains(category)`**.
- **`prompts/trusted_sources.py`** — librarian-style system prompt; downstream wording describes **domain restriction / allowlist** (not misleading **`site:`** copy if you use Tavily).

### Schema coercion (`TrustedSourcesResponse`)

| Decision | Reason |
|----------|--------|
| **Truncate to max length** | Models sometimes return **>14** domains; failing the whole response is worse than **capping** the list. |
| **Skip invalid entries; URL → hostname** | Messy strings (`https://www.foo.com/path`) should yield **`foo.com`** when parsable; garbage should **drop**, not fail the batch. |
| **Dedupe (first wins)** | Repeated **`www.`** / duplicates after normalize should not inflate the list. |
| **Counts in `config/settings.py`** | **`TRUSTED_SOURCES_DOMAIN_COUNT_MIN`** / **`MAX`** — **`AGENT.md`** asks for central env/constants; keeps prompts and validation aligned. |
| **Still enforce minimum count after cleanup** | If fewer than **MIN** valid domains remain, validation fails → **`None`** from the service — signals upstream that Groq output was unusable. |

---

## Testing strategy

| Artifact | Purpose |
|----------|---------|
| **`tests/test_category_graph.py`** | LangGraph **control flow** only — **`extract_category` mocked**; no Ollama/Mermaid; fast CI-friendly checks (interrupt, **`final_attempt`** flag, terminals). |
| **`tests/test_category_extraction_from_queries.py`** | **Integration batch** — CSV **`human_queries.txt`**, real **Ollama**, results **`category_extraction_results.txt`** (gitignored). |
| **`tests/test_source_finder.py`** | **Integration batch** — line-based **`categories.txt`**, real **Groq**, results **`source_finder_results.txt`** (gitignored). |
| **Removed `tests/test_prompt_behaviour.py`** | Mock-heavy “prompt unit tests” duplicated intent poorly; **batch scripts** match how prompts are actually validated (live model + fixtures). |

---

## Configuration & secrets

- **`config/settings.py`** — **`GROQ_API_KEY`**, **`OLLAMA_BASE_URL`**, model names, Tavily/SerpAPI keys as needed, trusted-sources domain bounds.
- **`.env`** loaded from project root (gitignored patterns per repo).

---

## Dependencies (implicit choices)

- **LangGraph** — human-in-the-loop **`interrupt`** + checkpointing.
- **LangChain** — prompts, parsers, Ollama/Groq chat wrappers.
- **Pydantic v2** — boundaries; **`TrustedSourcesResponse`** uses **`model_validator(mode="before")`** for coercion.

---

## Known limitations / follow-ups

- **Category / trusted quality** still depends on **model + prompt adherence**; batch txt outputs are the regression surface.
- **`TrustedSourcesResponse`** minimum count is strict after sanitization — if you want to **lower MIN** or **pad** with fallbacks, that’s a product decision (not implemented here).
- **Notebook `experiments/category_extraction_playground.ipynb`** may drift from committed prompt text until cells are re-run / synced manually.

---

## File map (high level)

| Area | Paths |
|------|--------|
| Category prompts | `prompts/category_extraction.py` |
| Trusted prompts | `prompts/trusted_sources.py` |
| Category service | `services/category_extraction.py` |
| Trusted service | `services/trusted_sources.py` |
| Schemas | `schemas/category_extraction.py`, `schemas/trusted_sources.py` |
| LangGraph | `agent/graph.py`, `agent/nodes.py`, `agent/state.py` |
| Batch runners | `tests/test_category_extraction_from_queries.py`, `tests/test_source_finder.py` |
| Graph viz export | `scripts/export_category_graph_visual.py` |
| Interactive stream | `scripts/run_category_graph_interactive.py` |
| Diagram output | `agent_viz/` (PNG/MMD from export script) |

This reflection is a snapshot of reasoning at authoring time; when behavior changes, update this file or trim stale sections so it stays trustworthy.
