"""Niche-independent content idea generation boundary.

V0 keeps generation provider-agnostic: callers can pass ideas produced by an
LLM, a research adapter, or a human. This prevents business logic from being
coupled to one AI provider.
"""

from collections.abc import Iterable
from typing import Any

from app.database.models import ContentIdea, IdeaScores


def build_idea(
    *,
    title: str,
    topic: str,
    audience: str,
    hook: str,
    source: str | None = None,
    why_now: str | None = None,
    monetization_angle: str | None = None,
    demand: float = 0,
    curiosity: float = 0,
    competition: float = 0,
    monetization: float = 0,
    production: float = 0,
    metadata: dict[str, Any] | None = None,
) -> ContentIdea:
    """Create one validated content idea from structured generation output."""
    return ContentIdea(
        title=title.strip(),
        topic=topic.strip(),
        audience=audience.strip(),
        hook=hook.strip(),
        source=source,
        why_now=why_now,
        monetization_angle=monetization_angle,
        scores=IdeaScores(
            demand=demand,
            curiosity=curiosity,
            competition=competition,
            monetization=monetization,
            production=production,
        ),
        metadata=metadata or {},
    )


def build_ideas(items: Iterable[dict]) -> list[ContentIdea]:
    """Convert dictionaries from a research/LLM adapter into validated ideas."""
    return [build_idea(**item) for item in items]
