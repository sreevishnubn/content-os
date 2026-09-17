"""Deterministic scoring for content opportunities.

The scorer intentionally uses transparent rules in V0. Later we can compare
these scores with real YouTube performance and replace the rules with a
data-informed model without changing the ContentIdea interface.
"""

from app.database.models import ContentIdea


# Weights sum to 1.0. Competition and production are inverted because a lower
# raw difficulty is desirable.
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
    value = (
        scores.demand * WEIGHTS["demand"]
        + scores.curiosity * WEIGHTS["curiosity"]
        + scores.competition * WEIGHTS["competition"]
        + scores.monetization * WEIGHTS["monetization"]
        + scores.production * WEIGHTS["production"]
    )
    return round(value, 2)


def score_idea(idea: ContentIdea) -> ContentIdea:
    """Return a copy of the idea with its overall score populated."""
    return idea.model_copy(update={"overall_score": calculate_overall_score(idea)})


def rank_ideas(ideas: list[ContentIdea]) -> list[ContentIdea]:
    """Score and rank ideas from highest to lowest opportunity."""
    return sorted((score_idea(idea) for idea in ideas), key=lambda x: x.overall_score or 0, reverse=True)
