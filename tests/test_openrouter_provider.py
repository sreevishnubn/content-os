from types import SimpleNamespace

from app.llm.models import LLMRequest
from app.integrations.openrouter_provider import OpenRouterProvider


def test_openrouter_provider_normalizes_response(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "test/model"
            assert kwargs["messages"][-1] == {"role": "user", "content": "hello"}
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
                usage=SimpleNamespace(prompt_tokens=4, completion_tokens=6, total_tokens=10),
            )

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "test-key"
            assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
            self.chat = FakeChat()

    monkeypatch.setattr("app.integrations.openrouter_provider.OpenAI", FakeClient)
    provider = OpenRouterProvider(api_key="test-key", default_model="test/model")
    response = provider.generate(LLMRequest(user_prompt="hello"))

    assert response.provider == "openrouter"
    assert response.model == "test/model"
    assert response.text == '{"ok":true}'
    assert response.usage["total_tokens"] == 10


def test_openrouter_structured_output(monkeypatch):
    class Result(BaseModel):
        ok: bool

    class FakeCompletions:
        def create(self, **kwargs):
            schema = kwargs["response_format"]["json_schema"]["schema"]
            assert schema["properties"]["ok"]["type"] == "boolean"
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
                usage=None,
            )

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    from pydantic import BaseModel

    monkeypatch.setattr("app.integrations.openrouter_provider.OpenAI", FakeClient)
    provider = OpenRouterProvider(api_key="test-key", default_model="test/model")
    result = provider.generate_structured(LLMRequest(user_prompt="hello"), Result)

    assert result.provider == "openrouter"
    assert result.data.ok is True
