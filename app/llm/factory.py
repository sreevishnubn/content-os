"""Construct configured LLM providers from runtime settings."""

from app.config.settings import get_settings
from app.integrations.openai_provider import OpenAIProvider
from app.integrations.openrouter_provider import OpenRouterProvider
from app.llm.interface import LLMProvider


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "openrouter":
        if not settings.llm_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required when CONTENTOS_LLM_PROVIDER=openrouter")
        return OpenRouterProvider(
            api_key=settings.llm_api_key,
            default_model=settings.llm_model or "openai/gpt-oss-20b",
            site_url="https://dashboard.youtube.analysis.com",
            site_name="ContentOS",
        )
    if settings.llm_provider == "openai":
        if not settings.llm_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when CONTENTOS_LLM_PROVIDER=openai")
        return OpenAIProvider(
            api_key=settings.llm_api_key,
            default_model=settings.llm_model or "gpt-5-mini",
        )
    raise RuntimeError(
        "No supported LLM provider is configured. Set CONTENTOS_LLM_PROVIDER and its provider API key."
    )
