from app.ideas.from_research import (
    research_items_to_ideas,
    research_to_idea,
    research_to_ideas,
)
from app.research.models import ResearchItem


def make_item(title: str = "New AI workflow", url: str = "https://example.com/story") -> ResearchItem:
    return ResearchItem(
        title=title,
        summary="AI tools are changing how teams work.",
        url=url,
        source_name="Example Source",
        tags=["AI", "productivity"],
    )


def test_research_to_idea_preserves_evidence():
    item = make_item()
    idea = research_to_idea(item)

    assert idea.title == "New AI workflow: What is really happening?"
    assert idea.source == "Example Source"
    assert idea.why_now == "AI tools are changing how teams work."
    assert idea.metadata["research_key"] == item.normalized_key()
    assert idea.metadata["research_url"] == "https://example.com/story"
    assert idea.metadata["research_tags"] == ["AI", "productivity"]
    assert idea.metadata["angle"] == "explainer"


def test_research_to_ideas_generates_multiple_angles():
    ideas = research_to_ideas(make_item())

    assert len(ideas) == 3
    assert [idea.metadata["angle"] for idea in ideas] == [
        "explainer",
        "how_it_works",
        "why_it_matters",
    ]
    assert len({idea.title for idea in ideas}) == 3


def test_research_to_ideas_can_select_angles():
    ideas = research_to_ideas(make_item(), angles=["how_it_works", "why_it_matters"])

    assert [idea.metadata["angle"] for idea in ideas] == [
        "how_it_works",
        "why_it_matters",
    ]


def test_research_to_idea_uses_first_tag_as_topic():
    idea = research_to_idea(make_item())
    assert idea.topic == "AI"


def test_research_to_idea_has_reviewable_defaults():
    idea = research_to_idea(make_item())

    assert idea.audience == "Viewers interested in this topic"
    assert idea.hook == "Understand the story behind New AI workflow."
    assert idea.overall_score is None
    assert all(value == 0 for value in idea.scores.model_dump().values())


def test_research_items_to_ideas_expands_each_item():
    ideas = research_items_to_ideas([
        make_item("One", "https://example.com/one"),
        make_item("Two", "https://example.com/two"),
    ])

    assert len(ideas) == 6
    assert [idea.title for idea in ideas[:3]] == [
        "One: What is really happening?",
        "How One actually works",
        "Why One matters more than you think",
    ]
