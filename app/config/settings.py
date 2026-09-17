import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    """Runtime configuration; secrets are read only from environment variables."""

    app_name: str = "ContentOS"
    environment: str = "development"
    database_path: str = "data/content.db"
    llm_provider: str | None = None
    llm_model: str | None = None

    @property
    def llm_api_key(self) -> str | None:
        """Resolve the configured provider's key without persisting it."""
        keys = {
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "gemini": os.getenv("GEMINI_API_KEY"),
        }
        return keys.get(self.llm_provider or "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("CONTENTOS_ENVIRONMENT", "development"),
        database_path=os.getenv("CONTENTOS_DATABASE_PATH", "data/content.db"),
        llm_provider=os.getenv("CONTENTOS_LLM_PROVIDER") or None,
        llm_model=os.getenv("CONTENTOS_LLM_MODEL") or None,
    )
