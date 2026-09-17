"""OpenAI Responses API adapter for ContentOS."""

from __future__ import annotations

from openai import OpenAI

from app.llm.interface import LLMProvider
from app.llm.models import LLMRequest, LLMResponse


class OpenAIProvider(LLMProvider):
    """Provider adapter using the official OpenAI Python SDK."""

    name = "openai"

    def __init__(self, *, api_key: str, default_model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
        if not default_model:
            raise ValueError("CONTENTOS_LLM_MODEL is required for the OpenAI provider")
        self.client = OpenAI(api_key=api_key)
        self.default_model = default_model

    def generate(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        kwargs = {
            "model": model,
            "input": request.user_prompt,
            "store": False,
        }
        if request.system_prompt:
            kwargs["instructions"] = request.system_prompt
        if request.max_tokens:
            kwargs["max_output_tokens"] = request.max_tokens

        response = self.client.responses.create(**kwargs)
        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            text=response.output_text,
            provider=self.name,
            model=response.model,
            usage=usage,
            raw={"response_id": response.id},
        )
