from abc import ABC, abstractmethod

from app.analytics.models import VideoMetrics


class AnalyticsProvider(ABC):
    """Contract for pulling performance metrics from a publishing platform."""

    name: str

    @abstractmethod
    def fetch_metrics(self, external_video_id: str) -> VideoMetrics:
        raise NotImplementedError
