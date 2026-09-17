"""Convert research evidence into reviewable content ideas."""

from collections.abc import Iterable

from app.database.models import ContentIdea
from app.research.models import ResearchItem


def research_to_idea(item: ResearchItem) -> ContentIdea:
    """Create a deterministic candidate idea while preserving its evidence."""
    title = item.title.strip()
    topic = item.tags[0] if item.tags else "General"
    audience = "Viewers interested in this topic"
    hook = f"What you need to know about {title}"

    return ContentIdea(
        title=title,
        topic=topic,
        audience=audience,
        hook=hook,
        source=item.source_name,
        why_now=item.summary,
        metadata={
            "research_key": item.normalized_key(),
            "research_url": str(item.url) if item.url else None,
            "research_tags": item.tags,
        },
        scores={
            "demand": 0,
            "curiosity": 0,
            "competition": 0,
            "monetization": 0,
            "production": 0,
        },
    )


def research_to_ideas(items: Iterable[ResearchItem]) -> list[ContentIdea]:
    """Convert multiple research items into candidate ideas."""
    return [research_to_idea(item) for item in items]
