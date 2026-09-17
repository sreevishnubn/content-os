from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """Provider-neutral request sent to an LLM."""

    system_prompt: str = ""
    user_prompt: str
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Normalized response returned by every provider."""

    text: str
    provider: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] | None = None


T = TypeVar("T", bound=BaseModel)


class StructuredLLMResponse(BaseModel, Generic[T]):
    """Validated structured output plus provider metadata."""

    data: T
    provider: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
