from typing import Literal, NotRequired, TypedDict


CategoryTerminal = Literal["complete", "no_shopping_intent", "error"]


class CategoryGraphState(TypedDict, total=False):
    """LangGraph state for category extraction + clarification loop."""

    user_query: str
    clarification_context: str
    clarification_rounds_completed: int
    pending_questions: list[str]
    category_result: dict[str, object]
    terminal: CategoryTerminal
    error_message: str
    # Optional shopping constraint (SerpAPI ``max_price`` when fetching Google Shopping).
    budget_max: NotRequired[float]


def append_clarification_exchange(
    existing_context: str,
    questions: list[str],
    user_reply: str,
) -> str:
    qs_lines = "\n".join(f"Q: {q}" for q in questions)
    block = f"{qs_lines}\nA: {user_reply.strip()}"
    prev = existing_context.strip()
    if prev:
        return f"{prev}\n\n{block}"
    return block
