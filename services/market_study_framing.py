"""Turn shopper context into Tavily-oriented analysis questions (single LLM call).

See ``services.market_research`` for search, summarization, and synthesis after framing.
"""

import logging

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import ValidationError

from config.settings import LOCAL_MODEL_SMALL, OLLAMA_BASE_URL
from prompts.market_study import MARKET_STUDY_SYSTEM, MARKET_STUDY_USER_TEMPLATE
from schemas.market_study import MarketStudyQuestions

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ]
)

_JSON_PARSER = JsonOutputParser()


def _response_text_to_str(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b if isinstance(b, str) else (b.get("text", "") if isinstance(b, dict) else "")
            for b in content
        )
    logger.error("Unexpected chat message content type: %s", type(content))
    return None


def _invoke_market_study_llm(user_prompt: str) -> str | None:
    llm = ChatOllama(
        model=LOCAL_MODEL_SMALL,
        base_url=OLLAMA_BASE_URL.rstrip("/"),
        temperature=0,
    )
    chain = _PROMPT | llm
    try:
        response = chain.invoke(
            {"system_prompt": MARKET_STUDY_SYSTEM, "user_prompt": user_prompt},
        )
    except Exception:
        logger.exception("Ollama market study failed")
        return None

    text = _response_text_to_str(response.content)
    return text.strip() if text else None


def _parse_market_study(reply_text: str) -> MarketStudyQuestions | None:
    try:
        payload = _JSON_PARSER.parse(reply_text)
    except OutputParserException:
        logger.exception("Market study response was not valid JSON")
        return None

    if not isinstance(payload, dict):
        logger.error("Market study JSON must be an object")
        return None

    try:
        return MarketStudyQuestions.model_validate(payload)
    except ValidationError:
        logger.exception("Market study JSON failed validation: %s", payload)
        return None


def generate_market_study_questions(
    user_query: str,
    *,
    clarification_context: str = "",
) -> MarketStudyQuestions | None:
    """Run Ollama market study; return analysis questions, or None on failure."""

    q = user_query.strip()
    ctx = clarification_context.strip()

    user_prompt = MARKET_STUDY_USER_TEMPLATE.format(
        user_query=q,
        clarification_context=ctx,
    )

    reply = _invoke_market_study_llm(user_prompt)
    if reply is None:
        return None
    return _parse_market_study(reply)
