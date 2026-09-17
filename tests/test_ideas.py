import pytest
from pydantic import ValidationError

from app.database.models import IdeaScores
from app.ideas.generator import build_idea, build_ideas
from app.ideas.scorer import WEIGHTS, calculate_overall_score, rank_ideas, score_idea


def make_idea(title: str, **scores):
    defaults = dict(
        demand=5,
        curiosity=5,
        competition=5,
        monetization=5,
        production=5,
    )
    defaults.update(scores)
    return build_idea(
        title=title,
        topic="Test topic",
        audience="Test audience",
        hook="Test hook",
        **defaults,
    )


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_build_idea_strips_text_and_sets_defaults():
    idea = build_idea(
        title="  Test title  ",
        topic="  Topic  ",
        audience="  Audience  ",
        hook="  Hook  ",
    )

    assert idea.title == "Test title"
    assert idea.topic == "Topic"
    assert idea.audience == "Audience"
    assert idea.hook == "Hook"
    assert idea.overall_score is None


def test_build_ideas_accepts_multiple_items():
    ideas = build_ideas(
        [
            {"title": "One", "topic": "A", "audience": "X", "hook": "H"},
            {"title": "Two", "topic": "B", "audience": "Y", "hook": "H"},
        ]
    )
    assert len(ideas) == 2
    assert ideas[0].title == "One"
    assert ideas[1].title == "Two"


def test_scores_are_validated_between_zero_and_ten():
    with pytest.raises(ValidationError):
        IdeaScores(
            demand=11,
            curiosity=5,
            competition=5,
            monetization=5,
            production=5,
        )


def test_overall_score_uses_weighted_average():
    idea = make_idea(
        "Weighted",
        demand=10,
        curiosity=8,
        competition=6,
        monetization=4,
        production=2,
    )

    assert calculate_overall_score(idea) == pytest.approx(6.9)


def test_score_idea_does_not_mutate_original():
    idea = make_idea("Original")
    scored = score_idea(idea)

    assert idea.overall_score is None
    assert scored.overall_score == 5.0


def test_rank_ideas_highest_first():
    low = make_idea("Low", demand=2)
    high = make_idea("High", demand=10)
    middle = make_idea("Middle", demand=6)

    ranked = rank_ideas([low, high, middle])

    assert [idea.title for idea in ranked] == ["High", "Middle", "Low"]
    assert all(idea.overall_score is not None for idea in ranked)
