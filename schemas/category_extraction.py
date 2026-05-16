from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class CategoryNeedsClarification(BaseModel):
    status: Literal["needs_clarification"]
    questions: list[str]

    @field_validator("questions")
    @classmethod
    def questions_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("questions must be non-empty")
        return value


class CategoryComplete(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["complete"]
    category: str

    @field_validator("category")
    @classmethod
    def category_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("category must be non-empty")
        return stripped


class CategoryNoShoppingIntent(BaseModel):
    status: Literal["no_shopping_intent"]
