from abc import ABC, abstractmethod

from app.research.models import ResearchItem


class ResearchProvider(ABC):
    """Contract for external research sources."""

    name: str

    @abstractmethod
    def search(self, query: str, *, limit: int = 10) -> list[ResearchItem]:
        """Return normalized research evidence for a query."""
        raise NotImplementedError
