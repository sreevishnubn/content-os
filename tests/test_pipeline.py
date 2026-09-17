import sqlite3

from app.database.repositories import IdeaRepository
from app.database.schema import initialize_schema
from app.database.models import IdeaStatus
from app.ideas.review import IdeaReviewService
from app.main import run_pipeline
from app.research.models import ResearchItem


def make_item(title: str, url: str) -> ResearchItem:
    return ResearchItem(
        title=title,
        summary=f"Evidence summary for {title}.",
        url=url,
        source_name="Integration Source",
        tags=["AI", "technology"],
    )


def test_end_to_end_research_to_ranked_ideas():
    first = make_item("First research story", "https://example.com/first")
    duplicate = make_item("Duplicate title", "https://example.com/first/")
    second = make_item("Second research story", "https://example.com/second")

    normalized, ranked = run_pipeline([first, duplicate, second])

    assert len(normalized) == 2
    assert normalized[0].title == "First research story"
    assert len(ranked) == 6
    assert all(idea.overall_score is not None for idea in ranked)
    assert all("research_key" in idea.metadata for idea in ranked)
    assert all("research_summary" in idea.metadata for idea in ranked)
    assert all(idea.overall_score == 0 for idea in ranked)


def test_end_to_end_persist_and_review():
    _, ranked = run_pipeline([make_item("Reviewable story", "https://example.com/review")])

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    repository = IdeaRepository(connection)
    review = IdeaReviewService(repository)

    repository.save_many(ranked)

    stored = repository.list()
    assert len(stored) == 3
    assert all(idea.status == IdeaStatus.DISCOVERED for idea in stored)

    selected = stored[0]
    review.shortlist(selected.idea_id)
    approved = review.approve(selected.idea_id)

    assert approved.status == IdeaStatus.APPROVED
    assert repository.list(status=IdeaStatus.APPROVED)[0].idea_id == selected.idea_id
