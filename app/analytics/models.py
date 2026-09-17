from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class VideoMetrics(BaseModel):
    metric_id: str = Field(default_factory=lambda: str(uuid4()))
    external_video_id: str
    captured_at: datetime
    views: int = Field(default=0, ge=0)
    watch_time_minutes: float = Field(default=0, ge=0)
    average_view_duration_seconds: float = Field(default=0, ge=0)
    impressions: int = Field(default=0, ge=0)
    click_through_rate: float = Field(default=0, ge=0, le=100)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    subscribers_gained: int = 0
    revenue: float = Field(default=0, ge=0)
