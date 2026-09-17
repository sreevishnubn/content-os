import sqlite3

import pytest

from app.database.models import ContentIdea, IdeaScores, IdeaStatus
from app.database.repositories import IdeaRepository
from app.database.schema import initialize_schema
from app.ideas.review import IdeaReviewService


def make_idea(title: str = "Test idea") -> ContentIdea:
    return ContentIdea(
        title=title,
        topic="AI",
        audience="Test audience",
        hook="Test hook",
        scores=IdeaScores(
            demand=8,
            curiosity=7,
            competition=6,
            monetization=5,
            production=4,
        ),
        overall_score=6.65,
        metadata={"research_key": "example-key", "tags": ["ai"]},
    )


def make_repository() -> IdeaRepository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return IdeaRepository(connection)


def test_save_and_get_round_trip():
    repository = make_repository()
    idea = make_idea()

    repository.save(idea)
    loaded = repository.get(idea.idea_id)

    assert loaded == idea


def test_save_many_and_list_by_status():
    repository = make_repository()
    first = make_idea("First")
    second = make_idea("Second")
    second = second.model_copy(update={"status": IdeaStatus.SHORTLISTED})

    repository.save_many([first, second])

    assert [idea.title for idea in repository.list()] == ["First", "Second"]
    assert [idea.title for idea in repository.list(status=IdeaStatus.SHORTLISTED)] == ["Second"]


def test_review_service_enforces_workflow():
    repository = make_repository()
    service = IdeaReviewService(repository)
    idea = repository.save(make_idea())

    shortlisted = service.shortlist(idea.idea_id)
    assert shortlisted.status == IdeaStatus.SHORTLISTED

    approved = service.approve(idea.idea_id)
    assert approved.status == IdeaStatus.APPROVED
    assert repository.get(idea.idea_id).status == IdeaStatus.APPROVED

    with pytest.raises(ValueError, match="Cannot move idea"):
        service.reject(idea.idea_id)


def test_reject_is_allowed_from_discovered():
    repository = make_repository()
    service = IdeaReviewService(repository)
    idea = repository.save(make_idea())

    rejected = service.reject(idea.idea_id)
    assert rejected.status == IdeaStatus.REJECTED
    assert repository.list(status=IdeaStatus.REJECTED)[0].idea_id == idea.idea_id
