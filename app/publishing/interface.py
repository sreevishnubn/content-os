from abc import ABC, abstractmethod

from app.publishing.models import PublishRequest


class PublishingProvider(ABC):
    """Provider contract for publishing to a media platform."""

    name: str

    @abstractmethod
    def publish(self, request: PublishRequest, video_path: str) -> PublishRequest:
        """Publish a production artifact and return updated metadata."""
        raise NotImplementedError
