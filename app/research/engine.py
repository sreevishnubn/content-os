"""Provider-agnostic research normalization for ContentOS V0."""

from collections.abc import Iterable

from app.research.models import ResearchItem


def normalize_item(item: ResearchItem) -> ResearchItem:
    """Normalize human/adapter input without changing its meaning."""
    return item.model_copy(
        update={
            "title": " ".join(item.title.split()),
            "summary": " ".join(item.summary.split()),
            "source_name": item.source_name.strip() if item.source_name else None,
            "tags": sorted({tag.strip().lower() for tag in item.tags if tag.strip()}),
        }
    )


def normalize_items(items: Iterable[ResearchItem]) -> list[ResearchItem]:
    """Normalize items and keep the first occurrence of each evidence key."""
    unique: dict[str, ResearchItem] = {}
    for item in items:
        normalized = normalize_item(item)
        unique.setdefault(normalized.normalized_key(), normalized)
    return list(unique.values())
