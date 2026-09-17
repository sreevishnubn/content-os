"""Construct configured external providers without leaking provider details into domain code."""

from app.config.settings import get_settings
from app.integrations.openai_provider import OpenAIProvider


def build_llm_provider():
    settings = get_settings()
    if settings.llm_provider == "openai":
        if not settings.llm_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when CONTENTOS_LLM_PROVIDER=openai")
        return OpenAIProvider(
            api_key=settings.llm_api_key,
            default_model=settings.llm_model or "gpt-5-mini",
        )
    raise RuntimeError(
        "No production LLM provider configured. Set CONTENTOS_LLM_PROVIDER and its provider API key."
    )
