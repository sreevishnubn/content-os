from app.llm.interface import LLMProvider


class LLMRouter:
    """Select an LLM provider without coupling business logic to it."""

    def __init__(self, providers: dict[str, LLMProvider], default_provider: str) -> None:
        if default_provider not in providers:
            raise ValueError(f"Unknown default LLM provider: {default_provider}")
        self.providers = providers
        self.default_provider = default_provider

    def get(self, provider: str | None = None) -> LLMProvider:
        name = provider or self.default_provider
        try:
            return self.providers[name]
        except KeyError as exc:
            raise ValueError(f"Unknown LLM provider: {name}") from exc
