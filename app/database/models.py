from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class IdeaStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    SHORTLISTED = "SHORTLISTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SCRIPTING = "SCRIPTING"
    PRODUCTION = "PRODUCTION"
    REVIEW = "REVIEW"
    PUBLISHED = "PUBLISHED"
    ANALYZING = "ANALYZING"


class IdeaScores(BaseModel):
    demand: float = Field(ge=0, le=10)
    curiosity: float = Field(ge=0, le=10)
    competition: float = Field(ge=0, le=10)
    monetization: float = Field(ge=0, le=10)
    production: float = Field(ge=0, le=10)


class ContentIdea(BaseModel):
    idea_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    topic: str
    audience: str
    hook: str
    source: str | None = None
    why_now: str | None = None
    monetization_angle: str | None = None
    scores: IdeaScores
    overall_score: float | None = Field(default=None, ge=0, le=10)
    status: IdeaStatus = IdeaStatus.DISCOVERED
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
