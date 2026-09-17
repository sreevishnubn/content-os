from app.database.models import ContentIdea, IdeaScores
from app.ideas.scorer import calculate_overall_score, rank_ideas


def make_idea(title: str, value: float) -> ContentIdea:
    return ContentIdea(
        title=title,
        topic="test",
        audience="test audience",
        hook="test hook",
        scores=IdeaScores(
            demand=value,
            curiosity=value,
            competition=value,
            monetization=value,
            production=value,
        ),
    )


def test_score_is_within_range():
    idea = make_idea("Test", 8)
    assert calculate_overall_score(idea) == 8.0


def test_rank_ideas_descending():
    ideas = [make_idea("Low", 4), make_idea("High", 9), make_idea("Mid", 7)]
    ranked = rank_ideas(ideas)
    assert [idea.title for idea in ranked] == ["High", "Mid", "Low"]


def test_score_is_rounded():
    idea = ContentIdea(
        title="Weighted",
        topic="test",
        audience="test",
        hook="test",
        scores=IdeaScores(
            demand=9,
            curiosity=8,
            competition=7,
            monetization=6,
            production=5,
        ),
    )
    assert calculate_overall_score(idea) == 7.45
