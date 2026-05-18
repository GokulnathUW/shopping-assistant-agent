from typing import Any, Literal

from langgraph.types import interrupt

from agent.state import CategoryGraphState, append_clarification_exchange
from schemas.category_extraction import (
    CategoryComplete,
    CategoryNeedsClarification,
    CategoryNoShoppingIntent,
)
from services.category_extraction import extract_category
from services.market_study_framing import generate_market_study_questions

MAX_CLARIFICATION_ROUNDS = 2



############# CATEGORY EXTRACTION ##############
def extract_category_node(state: CategoryGraphState) -> dict[str, Any]:
    user_query = state.get("user_query", "").strip()
    if not user_query:
        return {
            "terminal": "error",
            "error_message": "user_query is empty",
            "pending_questions": [],
        }

    ctx = (state.get("clarification_context") or "").strip()
    rounds = int(state.get("clarification_rounds_completed") or 0)
    final_attempt = rounds >= MAX_CLARIFICATION_ROUNDS

    raw = extract_category(
        user_query,
        clarification_context=ctx,
        final_attempt=final_attempt,
    )

    if raw is None:
        return {
            "terminal": "error",
            "error_message": "category extraction returned no result",
            "pending_questions": [],
        }

    if isinstance(raw, CategoryComplete):
        return {
            "terminal": "complete",
            "category_result": raw.model_dump(),
            "pending_questions": [],
        }

    if isinstance(raw, CategoryNoShoppingIntent):
        return {
            "terminal": "no_shopping_intent",
            "pending_questions": [],
        }

    if isinstance(raw, CategoryNeedsClarification):
        # Only before clarification rounds run out. The exhausted attempt uses the
        # force-complete system prompt (complete-only), so needs_clarification is out of policy there.
        return {
            "pending_questions": list(raw.questions),
        }

    return {
        "terminal": "error",
        "error_message": "unexpected category extraction type",
        "pending_questions": [],
    }


def human_clarification_node(state: CategoryGraphState) -> dict[str, Any]:
    questions = state.get("pending_questions") or []
    user_reply = interrupt({"questions": questions})
    reply_text = user_reply if isinstance(user_reply, str) else str(user_reply)

    prev_ctx = state.get("clarification_context") or ""
    new_ctx = append_clarification_exchange(prev_ctx, questions, reply_text)
    rounds = int(state.get("clarification_rounds_completed") or 0)

    return {
        "clarification_context": new_ctx,
        "clarification_rounds_completed": rounds + 1,
        "pending_questions": [],
    }


############# MARKET STUDY ##############
def market_study_node(state: CategoryGraphState) -> dict[str, Any]:
    """Ollama market study: Tavily-oriented analysis questions from shopper request + clarification."""

    user_query = state.get("user_query", "").strip()
    ctx = (state.get("clarification_context") or "").strip()
    parsed = generate_market_study_questions(
        user_query,
        clarification_context=ctx,
    )
    if parsed is None:
        return {"market_study_questions": []}
    return {"market_study_questions": list(parsed.questions)}


def route_after_extract(
    state: CategoryGraphState,
) -> Literal["clarify", "market_study", "end"]:
    if state.get("pending_questions"):
        return "clarify"
    if state.get("terminal") == "complete":
        return "market_study"
    return "end"
