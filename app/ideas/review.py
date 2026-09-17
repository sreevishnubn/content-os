"""Human review boundary for content ideas."""

from app.database.models import ContentIdea, IdeaStatus
from app.database.repositories import IdeaRepository


class IdeaReviewService:
    """Apply the small set of allowed human-review transitions."""

    def __init__(self, repository: IdeaRepository) -> None:
        self.repository = repository

    def shortlist(self, idea_id: str) -> ContentIdea:
        return self._transition(idea_id, IdeaStatus.SHORTLISTED, {IdeaStatus.DISCOVERED})

    def approve(self, idea_id: str) -> ContentIdea:
        return self._transition(idea_id, IdeaStatus.APPROVED, {IdeaStatus.SHORTLISTED})

    def reject(self, idea_id: str) -> ContentIdea:
        return self._transition(
            idea_id,
            IdeaStatus.REJECTED,
            {IdeaStatus.DISCOVERED, IdeaStatus.SHORTLISTED},
        )

    def _transition(
        self,
        idea_id: str,
        target: IdeaStatus,
        allowed: set[IdeaStatus],
    ) -> ContentIdea:
        idea = self.repository.get(idea_id)
        if idea is None:
            raise ValueError(f"Idea not found: {idea_id}")
        if idea.status not in allowed:
            raise ValueError(
                f"Cannot move idea from {idea.status.value} to {target.value}"
            )
        updated = self.repository.update_status(idea_id, target)
        if updated is None:
            raise ValueError(f"Idea not found: {idea_id}")
        return updated
