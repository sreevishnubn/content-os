"""OpenAI adapter for structured ContentOS generation."""

from typing import TypeVar
from pydantic import BaseModel
from openai import OpenAI

from app.llm.interface import LLMProvider
from app.llm.models import LLMRequest, LLMResponse, StructuredLLMResponse

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, default_model: str = "gpt-5-mini") -> None:
        self.client = OpenAI(api_key=api_key)
        self.default_model = default_model

    @staticmethod
    def _usage(response) -> dict:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            return usage.model_dump()
        return {
            key: getattr(usage, key)
            for key in ("input_tokens", "output_tokens", "total_tokens")
            if getattr(usage, key, None) is not None
        }

    @staticmethod
    def _request_kwargs(request: LLMRequest, model: str) -> dict:
        kwargs = {
            "model": model,
            "instructions": request.system_prompt or None,
            "input": request.user_prompt,
            "max_output_tokens": request.max_tokens,
        }
        # GPT-5/reasoning models use their default sampling behavior and do not
        # accept the legacy temperature control.
        if not model.startswith("gpt-5"):
            kwargs["temperature"] = request.temperature
        return kwargs

    def generate(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        response = self.client.responses.create(**self._request_kwargs(request, model))
        return LLMResponse(
            text=response.output_text,
            provider=self.name,
            model=model,
            usage=self._usage(response),
        )

    def generate_structured(
        self, request: LLMRequest, response_model: type[T]
    ) -> StructuredLLMResponse[T]:
        model = request.model or self.default_model
        response = self.client.responses.parse(
            **self._request_kwargs(request, model),
            text_format=response_model,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI returned no structured output")
        return StructuredLLMResponse(
            data=parsed,
            provider=self.name,
            model=model,
            usage=self._usage(response),
        )
