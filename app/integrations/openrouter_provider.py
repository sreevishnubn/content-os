"""OpenRouter adapter using its OpenAI-compatible Chat Completions API."""

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.llm.interface import LLMProvider
from app.llm.models import LLMRequest, LLMResponse, StructuredLLMResponse

T = TypeVar("T", bound=BaseModel)


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        default_model: str = "openai/gpt-oss-20b",
        site_url: str | None = None,
        site_name: str | None = None,
    ) -> None:
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                **({"HTTP-Referer": site_url} if site_url else {}),
                **({"X-Title": site_name} if site_name else {}),
            },
        )
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
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if getattr(usage, key, None) is not None
        }

    @staticmethod
    def _messages(request: LLMRequest) -> list[dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})
        return messages

    def _create(self, request: LLMRequest, **extra):
        model = request.model or self.default_model
        kwargs = {
            "model": model,
            "messages": self._messages(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            **extra,
        }
        response = self.client.chat.completions.create(**kwargs)
        return model, response

    def generate(self, request: LLMRequest) -> LLMResponse:
        model, response = self._create(request)
        content = response.choices[0].message.content or ""
        return LLMResponse(
            text=content,
            provider=self.name,
            model=model,
            usage=self._usage(response),
        )

    @staticmethod
    def _strict_json_schema(response_model: type[BaseModel]) -> dict:
        """Convert a Pydantic schema to the portable strict JSON Schema subset."""
        raw = response_model.model_json_schema()
        definitions = raw.get("$defs", {})

        def transform(node: dict) -> dict:
            if "$ref" in node:
                ref_name = node["$ref"].rsplit("/", 1)[-1]
                return transform(definitions[ref_name])

            result = {}
            node_type = node.get("type")
            if node_type:
                result["type"] = node_type
            if "enum" in node:
                result["enum"] = node["enum"]
            if node_type == "object":
                properties = node.get("properties", {})
                result["properties"] = {name: transform(value) for name, value in properties.items()}
                result["required"] = list(properties.keys())
                result["additionalProperties"] = False
            elif node_type == "array":
                result["items"] = transform(node["items"])
            return result

        return transform(raw)
    def generate_structured(
        self, request: LLMRequest, response_model: type[T]
    ) -> StructuredLLMResponse[T]:
        """Generate schema-validated structured data through OpenRouter free routing."""
        schema = self._strict_json_schema(response_model)

        try:
            model, response = self._create(
                request,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
        except Exception as exc:
            raise ValueError(
                f"OpenRouter free structured-output request failed for {response_model.__name__}: {exc}"
            ) from exc

        content = response.choices[0].message.content or ""
        try:
            data = response_model.model_validate_json(content)
        except ValueError as exc:
            raise ValueError(
                f"OpenRouter returned invalid structured output for {response_model.__name__}: {exc}"
            ) from exc

        return StructuredLLMResponse(
            data=data,
            provider=self.name,
            model=model,
            usage=self._usage(response),
        )
