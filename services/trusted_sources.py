import logging

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import ValidationError

from config.settings import GROQ_API_KEY, GROQ_MODEL_SMALL
from prompts.trusted_sources import TRUSTED_SOURCES_SYSTEM, TRUSTED_SOURCES_USER_TEMPLATE
from schemas.trusted_sources import TrustedSourcesResponse

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ]
)

_JSON_PARSER = JsonOutputParser()


def _response_text_content(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b if isinstance(b, str) else (b.get("text", "") if isinstance(b, dict) else "")
            for b in content
        )
    logger.error("Unexpected chat message content type: %s", type(content))
    return None


def _invoke_trusted_sources_llm(user_prompt: str) -> str | None:
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY is not set; cannot fetch trusted sources")
        return None

    llm = ChatGroq(
        model=GROQ_MODEL_SMALL,
        api_key=GROQ_API_KEY,
        temperature=0,
    )
    chain = _PROMPT | llm

    try:
        response = chain.invoke(
            {
                "system_prompt": TRUSTED_SOURCES_SYSTEM,
                "user_prompt": user_prompt,
            }
        )
    except Exception:
        logger.exception("Groq trusted sources request failed")
        return None

    text = _response_text_content(response.content)
    return text.strip() if text else None


def _parse_trusted_sources(reply_text: str) -> TrustedSourcesResponse | None:
    try:
        payload = _JSON_PARSER.parse(reply_text)
    except OutputParserException:
        logger.exception("Trusted sources response was not valid JSON")
        return None

    try:
        return TrustedSourcesResponse.model_validate(payload)
    except ValidationError:
        logger.exception("Trusted sources JSON failed validation: %s", payload)
        return None


def fetch_trusted_sources_domains(category: str) -> list[str] | None:
    """Return 10–14 editorial domain names for Tavily ``include_domains``, or ``None`` on failure."""

    cat = category.strip()
    user_prompt = TRUSTED_SOURCES_USER_TEMPLATE.format(category=cat)

    reply  = _invoke_trusted_sources_llm(user_prompt)
    parsed = _parse_trusted_sources(reply)
    if parsed is None:
        return None

    return list(parsed.domains)
