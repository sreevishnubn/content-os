from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class LearningSignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    source_video_id: str | None = None
    signal_type: str
    observation: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
