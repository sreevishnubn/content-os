from types import SimpleNamespace

from app.llm.models import LLMRequest
from app.integrations.openai_provider import OpenAIProvider


def test_openai_provider_normalizes_response(monkeypatch):
    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["model"] == "gpt-test"
            assert kwargs["input"] == "hello"
            assert kwargs["instructions"] is None
            return SimpleNamespace(
                id="resp_123",
                model="gpt-test",
                output_text='{"ok":true}',
                usage=SimpleNamespace(input_tokens=4, output_tokens=6, total_tokens=10),
            )

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "test-key"
            self.responses = FakeResponses()

    monkeypatch.setattr("app.integrations.openai_provider.OpenAI", FakeClient)
    provider = OpenAIProvider(api_key="test-key", default_model="gpt-test")
    response = provider.generate(LLMRequest(user_prompt="hello"))

    assert response.provider == "openai"
    assert response.model == "gpt-test"
    assert response.text == '{"ok":true}'
    assert response.usage["total_tokens"] == 10
