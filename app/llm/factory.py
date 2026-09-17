"""Construct configured LLM providers from runtime settings."""

from app.config.settings import get_settings
from app.integrations.openai_provider import OpenAIProvider
from app.llm.interface import LLMProvider


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "openai":
        return OpenAIProvider(
            api_key=settings.llm_api_key or "",
            default_model=settings.llm_model or "",
        )
    raise RuntimeError(
        "No supported LLM provider is configured. Set CONTENTOS_LLM_PROVIDER=openai, "
        "CONTENTOS_LLM_MODEL and OPENAI_API_KEY."
    )
