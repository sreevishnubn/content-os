from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from app.llm.models import LLMRequest, LLMResponse, StructuredLLMResponse

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Contract implemented by every LLM provider adapter."""

    name: str

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a text response."""
        raise NotImplementedError

    def generate_structured(
        self, request: LLMRequest, response_model: type[T]
    ) -> StructuredLLMResponse[T]:
        """Generate text and validate it against a Pydantic model."""
        response = self.generate(request)
        try:
            data = response_model.model_validate_json(response.text)
        except ValueError as exc:
            raise ValueError(
                f"LLM provider '{response.provider}' returned invalid "
                f"structured output for {response_model.__name__}"
            ) from exc
        return StructuredLLMResponse(
            data=data,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
        )
