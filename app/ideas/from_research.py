"""Convert research evidence into multiple reviewable content angles."""

from collections.abc import Iterable

from app.database.models import ContentIdea
from app.research.models import ResearchItem


ANGLE_TEMPLATES = (
    ("explainer", "{title}: What is really happening?", "Understand the story behind {title}."),
    ("how_it_works", "How {title} actually works", "Most people see the result; this explains the process behind {title}."),
    ("why_it_matters", "Why {title} matters more than you think", "The important part of {title} is what it could change next."),
)


def research_to_ideas(
    item: ResearchItem,
    *,
    angles: Iterable[str] | None = None,
) -> list[ContentIdea]:
    """Create several deterministic editorial angles from one research item.

    This V0 implementation deliberately does not call an LLM. It creates
    distinct candidate frames while preserving the same research evidence so
    a later provider can replace the angle-generation strategy without
    changing the downstream idea/scoring pipeline.
    """
    requested = set(angles) if angles is not None else {name for name, _, _ in ANGLE_TEMPLATES}
    title = item.title.strip()
    topic = item.tags[0] if item.tags else "General"

    ideas: list[ContentIdea] = []
    for angle_name, title_template, hook_template in ANGLE_TEMPLATES:
        if angle_name not in requested:
            continue

        ideas.append(
            ContentIdea(
                title=title_template.format(title=title),
                topic=topic,
                audience="Viewers interested in this topic",
                hook=hook_template.format(title=title),
                source=item.source_name,
                why_now=item.summary,
                metadata={
                    "research_key": item.normalized_key(),
                    "research_url": str(item.url) if item.url else None,
                    "research_tags": item.tags,
                    "angle": angle_name,
                },
                scores={
                    "demand": 0,
                    "curiosity": 0,
                    "competition": 0,
                    "monetization": 0,
                    "production": 0,
                },
            )
        )

    return ideas


def research_to_idea(item: ResearchItem) -> ContentIdea:
    """Backward-compatible single-angle conversion."""
    return research_to_ideas(item, angles=["explainer"])[0]


def research_items_to_ideas(items: Iterable[ResearchItem]) -> list[ContentIdea]:
    """Convert multiple research items into multiple candidate angles."""
    ideas: list[ContentIdea] = []
    for item in items:
        ideas.extend(research_to_ideas(item))
    return ideas
