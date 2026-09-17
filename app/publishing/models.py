from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class PublishStatus(StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class PublishRequest(BaseModel):
    publish_id: str = Field(default_factory=lambda: str(uuid4()))
    production_id: str
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    scheduled_at: datetime | None = None
    status: PublishStatus = PublishStatus.DRAFT
    external_id: str | None = None
