import os

from app.research.models import ResearchItem
from app.research.providers.youtube import YouTubeResilientProvider


class StubProvider:
    def __init__(self, result=None, error=None):
        self.result = result or []
        self.error = error

    def search(self, query="", *, limit=10):
        if self.error:
            raise self.error
        return self.result[:limit]


def test_resilient_provider_uses_ytdlp_without_api_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    provider = YouTubeResilientProvider(["UC1234567890123456789012"])
    assert [name for name, _ in provider._providers()] == [
        "youtube_ytdlp",
        "youtube_html",
        "youtube_rss",
    ]


def test_resilient_provider_puts_api_first_when_configured(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    provider = YouTubeResilientProvider(["UC1234567890123456789012"])
    assert [name for name, _ in provider._providers()] == [
        "youtube_api",
        "youtube_ytdlp",
        "youtube_html",
        "youtube_rss",
    ]


def test_resilient_provider_falls_back(monkeypatch):
    item = ResearchItem(
        title="Fallback video",
        summary="Fallback summary",
        url="https://www.youtube.com/watch?v=abc123",
        source_name="YouTube — Example",
    )

    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    provider = YouTubeResilientProvider(["UC1234567890123456789012"])

    class FakeProvider:
        def __init__(self, result=None, error=None):
            self.result = result
            self.error = error

        def search(self, query="", *, limit=10):
            if self.error:
                raise self.error
            return self.result

    calls = []

    def fake_providers():
        calls.append("providers")
        return [
            ("broken", lambda: FakeProvider(error=RuntimeError("temporary failure"))),
            ("working", lambda: FakeProvider(result=[item])),
        ]

    provider._providers = fake_providers
    results = provider.search(limit=1)

    assert results == [item]
    assert provider.last_provider == "working"
    assert calls == ["providers"]
