from app.ideas.scorer import calculate_overall_score
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

    # Research normalization removes the duplicate before idea generation.
    assert len(normalized) == 2
    assert normalized[0].title == "First research story"

    # Each normalized research item produces three editorial candidates.
    assert len(ranked) == 6
    assert all(idea.overall_score is not None for idea in ranked)

    # Evidence survives the conversion into ContentIdea metadata.
    assert all("research_key" in idea.metadata for idea in ranked)
    assert all("research_summary" in idea.metadata for idea in ranked)

    # V0 candidates use neutral zero-valued scoring until scoring intelligence exists.
    assert all(calculate_overall_score(idea) == 0 for idea in ranked)
