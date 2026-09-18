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

    def generate_structured(
        self, request: LLMRequest, response_model: type[T]
    ) -> StructuredLLMResponse[T]:
        """Generate structured data, including with free models that lack JSON-schema support."""
        schema = response_model.model_json_schema()

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
            content = response.choices[0].message.content
            if content:
                try:
                    data = response_model.model_validate_json(content)
                    return StructuredLLMResponse(
                        data=data,
                        provider=self.name,
                        model=model,
                        usage=self._usage(response),
                    )
                except ValueError:
                    pass
        except Exception:
            pass

        fallback_request = LLMRequest(
            system_prompt=(
                request.system_prompt
                + "\nReturn ONLY one valid JSON object. Do not use Markdown, code fences, comments, or explanatory text."
                + "\nThe JSON must match this schema exactly:\n"
                + json.dumps(schema, separators=(',', ':'))
            ),
            user_prompt=request.user_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            metadata=request.metadata,
        )
        # Free OpenRouter models do not all implement JSON-schema response formatting.
        # Use JSON-object mode for the fallback.
        model, response = self._create(
            fallback_request,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        cleaned = content.strip()

        if cleaned.startswith("```"):
            parts = cleaned.splitlines()
            if parts and parts[0].strip().startswith("```"):
                parts = parts[1:]
            if parts and parts[-1].strip() == "```"):
                parts = parts[:-1]
            cleaned = "\n".join(parts).strip()

        try:
            data = response_model.model_validate_json(cleaned)
        except ValueError:
            decoder = json.JSONDecoder()
            extracted = None
            for index, char in enumerate(cleaned):
                if char != "{":
                    continue
                try:
                    candidate, _ = decoder.raw_decode(cleaned[index:])
                    if isinstance(candidate, dict):
                        extracted = candidate
                        break
                except json.JSONDecodeError:
                    continue
            if extracted is None:
                raise ValueError(
                    f"OpenRouter returned invalid structured output for {response_model.__name__}"
                )
            try:
                data = response_model.model_validate(extracted)
            except ValueError as exc:
                raise ValueError(
                    f"OpenRouter returned JSON that does not match {response_model.__name__}"
                ) from exc


        return StructuredLLMResponse(
            data=data,
            provider=self.name,
            model=model,
            usage=self._usage(response),
        )
