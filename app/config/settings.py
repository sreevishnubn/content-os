from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    """Runtime settings kept independent from business logic."""

    app_name: str = "ContentOS"
    environment: str = "development"
    database_path: str = "data/content.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
