from datetime import datetime, timezone

from pydantic import AnyHttpUrl, BaseModel, Field


class ResearchItem(BaseModel):
    """A normalized piece of evidence that may inform a content idea."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    url: AnyHttpUrl | None = None
    source_name: str | None = None
    published_at: datetime | None = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = Field(default_factory=list)

    def normalized_key(self) -> str:
        """Return a stable key used to detect duplicate research items."""
        if self.url:
            return str(self.url).rstrip("/").lower()
        return f"{self.title.strip().lower()}::{self.source_name or ''}".strip()
