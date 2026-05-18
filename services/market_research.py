"""
Market research pipeline (after framing): framed questions → Tavily (trusted domains) →
per-hit summaries → assimilator LLM → follow-up question LLM.

Plain dict in / dict out (no pipeline-level Pydantic). Tavily still returns typed hits internally.

Framing lives in ``services.market_study_framing``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from config.settings import (
    LOCAL_MODEL_SMALL,
    MARKET_RESEARCH_TAVILY_MAX_RESULTS_PER_QUESTION,
    OLLAMA_BASE_URL,
)
from schemas.tavily import TavilySearchHit
from tools.tavily import search_trusted_domains

logger = logging.getLogger(__name__)

# --- System prompts (per-step instructions for ChatOllama) ---
SYS_SUMMARIZE_HIT = (
    "Summarize the following article excerpt for a shopping assistant. "
    "Only use information from the excerpt — do not add outside knowledge. "
    "Focus on category insights: pricing themes, tradeoffs, segments, and debates. "
    "If the excerpt is thin or off-topic, say so in one sentence."
)

SYS_ASSIMILATE_BRIEF = (
    "You are synthesizing editorial research notes into a market brief for a shopper. "
    "Only use information from the provided notes — do not add outside knowledge. "
    "Organize the brief into 3–5 sections. Each section has a short topic heading "
    "and 2–3 sentences. Let the content determine the sections — do not force topics "
    "that are not supported by the notes. No product recommendations."
)

SYS_FOLLOW_UP_QUESTIONS = (
    "Based on the shopper context and the research brief, propose follow-up questions "
    "the assistant should ask to narrow preferences (use case, budget comfort, constraints, ecosystem). "
    "Only ask what is not already known from the context. "
    'Return strict JSON: {"questions": ["..."]}. 2–4 concise strings. No markdown fences.'
)

# Single-turn Ollama template reused for summarize / assimilate / follow-up
_LLM_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ]
)


def _ollama_text(system_prompt: str, user_prompt: str) -> str | None:
    """One ChatOllama call; returns assistant text or None on failure."""

    llm = ChatOllama(
        model=LOCAL_MODEL_SMALL,
        base_url=OLLAMA_BASE_URL.rstrip("/"),
        temperature=0,
    )
    chain = _LLM_PROMPT | llm
    try:
        msg = chain.invoke({"system_prompt": system_prompt, "user_prompt": user_prompt})
    except Exception:
        logger.exception("Ollama call failed")
        return None

    raw = msg.content
    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, list):
        text = "".join(
            part if isinstance(part, str) else (part.get("text", "") if isinstance(part, dict) else "")
            for part in raw
        )
    else:
        logger.error("Unexpected message content type: %s", type(raw))
        return None

    out = text.strip()
    return out if out else None


def _hit_to_dict(hit: TavilySearchHit) -> dict[str, str]:
    """Serialize a Tavily hit without exposing pydantic outside this boundary."""

    return {
        "url": str(hit.url),
        "title": str(hit.title) if hit.title else "",
        "raw_content": str(hit.raw_content),
    }


def _canonical_url_key(url: str) -> str:
    u = url.strip()
    if not u:
        return ""
    parsed = urlparse(u)
    path = parsed.path.rstrip("/") or ""
    rebuilt = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            "",
        )
    )
    return rebuilt.lower()


def _dedupe_hits_by_url(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for h in hits:
        key = _canonical_url_key(h.get("url") or "")
        if key:
            if key in seen:
                continue
            seen.add(key)
        out.append(h)
    return out


def _summarize_hit(url: str, title: str, raw_content: str) -> str | None:
    """Compress one page into a short neutral note for later assimilation."""

    header = f"Page title: {title or '(none)'}\nSource URL: {url}\n\nExcerpt:\n"
    user = header + raw_content
    return _ollama_text(SYS_SUMMARIZE_HIT, user)


def _parse_questions_json(text: str) -> list[str] | None:
    """Extract {\"questions\": [...]} from model output; tolerate optional fences."""

    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)

    try:
        payload = json.loads(t)
    except json.JSONDecodeError:
        logger.exception("Follow-up LLM returned invalid JSON")
        return None

    if not isinstance(payload, dict):
        return None
    raw_qs = payload.get("questions")
    if not isinstance(raw_qs, list):
        return None

    out: list[str] = []
    for item in raw_qs:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out if out else None


def collect_summaries_for_framed_questions(
    framed_questions: list[str],
    trusted_domains: list[str],
) -> list[dict[str, Any]]:
    """
    Tavily (max MARKET_RESEARCH_TAVILY_MAX_RESULTS_PER_QUESTION per question) then summarize each hit.
    Each block: ``framed_question``, ``sources`` list of ``url`` / ``title`` / ``summary``.
    """

    fq = [q.strip() for q in framed_questions if isinstance(q, str) and q.strip()]
    domains = [d.strip() for d in trusted_domains if isinstance(d, str) and d.strip()]
    blocks: list[dict[str, Any]] = []

    for question in fq:
        hits_models = search_trusted_domains(
            question,
            trusted_domains=domains,
            max_results=MARKET_RESEARCH_TAVILY_MAX_RESULTS_PER_QUESTION,
        )
        hits = _dedupe_hits_by_url([_hit_to_dict(h) for h in hits_models])

        sources: list[dict[str, str]] = []
        for h in hits:
            summ = _summarize_hit(h["url"], h["title"], h["raw_content"]) or ""
            sources.append(
                {
                    "url": h["url"],
                    "title": h["title"],
                    "summary": summ,
                }
            )

        blocks.append({"framed_question": question, "sources": sources})

    return blocks


def build_digest_from_summarize_blocks(blocks: list[dict[str, Any]]) -> str:
    """Turn summarize-stage blocks into the assimilator user prompt (same shape as full pipeline)."""

    lines: list[str] = []
    for block in blocks:
        fq = block.get("framed_question") or block.get("question") or ""
        lines.append(f"## Framed question\n{fq}\n")
        idx = 1
        for src in block.get("sources") or []:
            if not isinstance(src, dict):
                continue
            s = (src.get("summary") or "").strip()
            if not s:
                continue
            lines.append(f"- Summary {idx}: {s}")
            idx += 1
        lines.append("")
    return "\n".join(lines).strip()


def assimilate_digest(digest_input: str) -> str:
    if not digest_input.strip():
        return ""
    return _ollama_text(SYS_ASSIMILATE_BRIEF, digest_input) or ""


def generate_follow_up_questions(shopper_context: str, assimilated_brief: str) -> list[str]:
    user_b = shopper_context.strip() + "\nResearch brief:\n" + (assimilated_brief.strip() or "(empty)")
    reply = _ollama_text(SYS_FOLLOW_UP_QUESTIONS, user_b)
    if not reply:
        return []
    return _parse_questions_json(reply) or []


def run_market_research(
    framed_questions: list[str],
    trusted_domains: list[str],
    *,
    user_query: str = "",
    clarification_context: str = "",
) -> dict[str, Any]:
    """
    Run full pipeline. Returns plain dict:
    Decisions still open (call out in code): chunking vs clipping, dedupe strength, model tiers, Groq vs Ollama for long synthesis.
    """

    fq = [q.strip() for q in framed_questions if isinstance(q, str) and q.strip()]
    domains = [d.strip() for d in trusted_domains if isinstance(d, str) and d.strip()]

    summarize_blocks = collect_summaries_for_framed_questions(fq, domains)

    digest_input = build_digest_from_summarize_blocks(summarize_blocks)
    assimilated = assimilate_digest(digest_input)

    shopper_ctx = f"Shopper request:\n{user_query.strip()}\n"
    if clarification_context.strip():
        shopper_ctx += f"\nPrior clarification:\n{clarification_context.strip()}\n"

    followups = generate_follow_up_questions(shopper_ctx, assimilated)

    return {
        "per_question": summarize_blocks,
        "assimilated_brief": assimilated,
        "follow_up_questions": followups,
    }
