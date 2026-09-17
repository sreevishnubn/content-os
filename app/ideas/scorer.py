"""Deterministic scoring for content opportunities.

V0 uses transparent weights. Every input score is an opportunity score from
0-10, where a higher value is better. Therefore competition means
"competitive opportunity" (10 = relatively low competitive pressure) and
production means "production ease" (10 = easy to produce).
"""

from app.database.models import ContentIdea


WEIGHTS = {
    "demand": 0.30,
    "curiosity": 0.25,
    "competition": 0.15,
    "monetization": 0.20,
    "production": 0.10,
}


def calculate_overall_score(idea: ContentIdea) -> float:
    """Return a 0-10 opportunity score, rounded to two decimals."""
    scores = idea.scores
    value = sum(
        getattr(scores, name) * weight for name, weight in WEIGHTS.items()
    )
    return round(value, 2)


def score_idea(idea: ContentIdea) -> ContentIdea:
    """Return a copy of the idea with its overall score populated."""
    return idea.model_copy(update={"overall_score": calculate_overall_score(idea)})


def rank_ideas(ideas: list[ContentIdea]) -> list[ContentIdea]:
    """Score and rank ideas from highest to lowest opportunity."""
    return sorted(
        (score_idea(idea) for idea in ideas),
        key=lambda idea: idea.overall_score or 0,
        reverse=True,
    )
