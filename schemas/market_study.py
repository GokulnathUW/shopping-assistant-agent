from pydantic import BaseModel, field_validator


class MarketStudyQuestions(BaseModel):
    """Ollama output: Tavily-oriented analysis questions from a quick market study."""

    questions: list[str]

    @field_validator("questions", mode="before")
    @classmethod
    def _coerce_questions(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("questions must be a list")
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        if not out:
            raise ValueError("questions must contain at least one non-empty string")
        return out
