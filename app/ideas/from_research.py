"""Convert research evidence into reviewable content ideas and angles."""

from collections.abc import Iterable

from app.database.models import ContentIdea
from app.research.models import ResearchItem


ANGLE_TEMPLATES = (
    (
        "explainer",
        "{title}: What is really happening?",
        "Understand the story behind {title}.",
    ),
    (
        "how_it_works",
        "How {title} actually works",
        "Most people see the result; this explains the process behind {title}.",
    ),
    (
        "why_it_matters",
        "Why {title} matters more than you think",
        "The important part of {title} is what it could change next.",
    ),
)


def _build_idea(
    item: ResearchItem,
    *,
    title: str,
    hook: str,
    angle: str | None = None,
) -> ContentIdea:
    """Build one candidate while preserving its research evidence."""
    return ContentIdea(
        title=title,
        topic=item.tags[0] if item.tags else "General",
        audience="Viewers interested in this topic",
        hook=hook,
        source=item.source_name,
        why_now=None,
        metadata={
            "research_key": item.normalized_key(),
            "research_summary": item.summary,
            "research_url": str(item.url) if item.url else None,
            "research_source_name": item.source_name,
            "research_tags": item.tags,
            **({"angle": angle} if angle else {}),
        },
        scores={
            "demand": 0,
            "curiosity": 0,
            "competition": 0,
            "monetization": 0,
            "production": 0,
        },
    )


def research_to_idea(item: ResearchItem) -> ContentIdea:
    """Create the original single candidate for backward compatibility."""
    return _build_idea(
        item,
        title=item.title.strip(),
        hook=f"What you need to know about {item.title.strip()}",
    )


def research_to_ideas(items: Iterable[ResearchItem]) -> list[ContentIdea]:
    """Convert multiple research items using one-to-one behavior."""
    return [research_to_idea(item) for item in items]


def research_to_angles(
    item: ResearchItem,
    *,
    angles: Iterable[str] | None = None,
) -> list[ContentIdea]:
    """Create several deterministic editorial angles from one research item."""
    requested = (
        set(angles)
        if angles is not None
        else {name for name, _, _ in ANGLE_TEMPLATES}
    )
    title = item.title.strip()
    ideas: list[ContentIdea] = []

    for angle_name, title_template, hook_template in ANGLE_TEMPLATES:
        if angle_name not in requested:
            continue
        ideas.append(
            _build_idea(
                item,
                title=title_template.format(title=title),
                hook=hook_template.format(title=title),
                angle=angle_name,
            )
        )

    return ideas


def research_items_to_ideas(items: Iterable[ResearchItem]) -> list[ContentIdea]:
    """Convert multiple research items into multiple candidate angles."""
    ideas: list[ContentIdea] = []
    for item in items:
        ideas.extend(research_to_angles(item))
    return ideas
