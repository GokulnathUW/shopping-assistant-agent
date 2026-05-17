import logging

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import ValidationError

from config.settings import LOCAL_MODEL_SMALL, OLLAMA_BASE_URL
from prompts.category_extraction import (
    CATEGORY_EXTRACTION_FORCE_COMPLETE_SYSTEM,
    CATEGORY_EXTRACTION_SYSTEM,
    CATEGORY_EXTRACTION_USER_TEMPLATE,
)
from schemas.category_extraction import (
    CategoryComplete,
    CategoryNeedsClarification,
    CategoryNoShoppingIntent,
)

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ]
)

_CATEGORY_JSON_PARSER = JsonOutputParser()


def _extract_category(user_prompt: str, *, system_prompt: str) -> str | None:
    llm = ChatOllama(
        model=LOCAL_MODEL_SMALL,
        base_url=OLLAMA_BASE_URL.rstrip("/"),
        temperature=0,
    )
    chain = _PROMPT | llm

    try:
        response = chain.invoke(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
    except Exception:
        logger.exception("Ollama category extraction failed")
        return None

    # AIMessage.content may be str or a list of text/multimodal chunks depending on provider.
    raw = response.content
    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, list):
        text = "".join(
            b if isinstance(b, str) else (b.get("text", "") if isinstance(b, dict) else "")
            for b in raw
        )
    else:
        logger.error("Unexpected chat message content type: %s", type(raw))
        return None

    return text.strip()


def _parse_category(
    reply_text: str,
) -> CategoryNeedsClarification | CategoryComplete | CategoryNoShoppingIntent | None:

    try:
        payload = _CATEGORY_JSON_PARSER.parse(reply_text)
    except OutputParserException:
        logger.exception("Category extraction response was not valid JSON")
        return None

    if not isinstance(payload, dict):
        logger.error("Category extraction JSON must be an object")
        return None

    status = payload.get("status")
    try:
        if status == "needs_clarification":
            return CategoryNeedsClarification.model_validate(payload)
        if status == "complete":
            return CategoryComplete.model_validate(payload)
        if status == "no_shopping_intent":
            return CategoryNoShoppingIntent.model_validate(payload)
    except ValidationError:
        logger.exception("Category extraction JSON failed validation: %s", payload)
        return None

    logger.error("Unknown category status: %r", status)
    return None


def extract_category(
    user_query: str,
    *,
    clarification_context: str = "",
    final_attempt: bool = False,
) -> CategoryNeedsClarification | CategoryComplete | CategoryNoShoppingIntent | None:
    user_prompt = CATEGORY_EXTRACTION_USER_TEMPLATE.format(
        user_query=user_query.strip(),
        clarification_context=clarification_context.strip(),
    )
    system_prompt = (
        CATEGORY_EXTRACTION_FORCE_COMPLETE_SYSTEM
        if final_attempt
        else CATEGORY_EXTRACTION_SYSTEM
    )
    reply = _extract_category(user_prompt, system_prompt=system_prompt)
    parsed = _parse_category(reply)
    if final_attempt and parsed is not None and not isinstance(parsed, CategoryComplete):
        logger.warning(
            "Final category attempt returned non-complete payload (got %s); treating as failure",
            getattr(parsed, "status", type(parsed).__name__),
        )
        return None
    return parsed
