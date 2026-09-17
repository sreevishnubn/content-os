import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

load_dotenv()


class Settings(BaseModel):
    """Central runtime configuration for local and hosted ContentOS."""

    app_name: str = "ContentOS"
    environment: str = "development"
    database_url: str | None = None
    database_path: str = "data/content.db"
    api_token: str | None = None
    cors_origins: list[str] = Field(default_factory=list)
    llm_provider: str | None = None
    llm_model: str | None = None

    @property
    def llm_api_key(self) -> str | None:
        keys = {
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "gemini": os.getenv("GEMINI_API_KEY"),
        }
        return keys.get(self.llm_provider or "")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_vercel(self) -> bool:
        return bool(os.getenv("VERCEL"))

    @model_validator(mode="after")
    def validate_production(self):
        if self.is_production:
            if not self.database_url:
                raise ValueError("DATABASE_URL is required in production")
            if not self.api_token:
                raise ValueError("CONTENTOS_API_TOKEN is required in production")
            if self.llm_provider and self.llm_provider != "openai":
                raise ValueError(f"Unsupported production LLM provider: {self.llm_provider}")
            if self.llm_provider and not self.llm_model:
                raise ValueError("CONTENTOS_LLM_MODEL is required when an LLM provider is configured")
            if self.llm_provider and not self.llm_api_key:
                raise ValueError(f"API credentials are missing for LLM provider '{self.llm_provider}'")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = os.getenv(
        "CONTENTOS_CORS_ORIGINS",
        "https://sreevishnubn.github.io,https://dashboard.youtube.analysis.com,http://localhost:5500,http://localhost:8000",
    )
    database_path = os.getenv("CONTENTOS_DATABASE_PATH")
    if not database_path:
        database_path = "/tmp/content.db" if os.getenv("VERCEL") else "data/content.db"

    return Settings(
        environment=os.getenv("CONTENTOS_ENVIRONMENT", "development"),
        database_url=os.getenv("DATABASE_URL") or None,
        database_path=database_path,
        api_token=os.getenv("CONTENTOS_API_TOKEN") or None,
        cors_origins=[item.strip() for item in origins.split(",") if item.strip()],
        llm_provider=os.getenv("CONTENTOS_LLM_PROVIDER") or None,
        llm_model=os.getenv("CONTENTOS_LLM_MODEL") or None,
    )
