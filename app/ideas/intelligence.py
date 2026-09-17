from app.database.models import ContentIdea
from app.ideas.scorer import rank_ideas


class IdeaIntelligence:
    """Business-facing idea pipeline; provider calls stay outside this layer."""

    def process(self, ideas: list[ContentIdea]) -> list[ContentIdea]:
        return rank_ideas(ideas)
