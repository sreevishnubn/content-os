from app.research.engine import normalize_item, normalize_items
from app.research.models import ResearchItem


def make_item(title: str, url: str | None = None) -> ResearchItem:
    return ResearchItem(
        title=title,
        summary="  A   useful summary.  ",
        url=url,
        source_name="  Example Source  ",
        tags=["AI", " ai ", "Technology", ""],
    )


def test_normalize_item_cleans_text_source_and_tags():
    item = normalize_item(make_item("  A   title  "))

    assert item.title == "A title"
    assert item.summary == "A useful summary."
    assert item.source_name == "Example Source"
    assert item.tags == ["ai", "technology"]


def test_normalized_key_prefers_url():
    item = make_item("Same story", "https://example.com/story/")
    assert item.normalized_key() == "https://example.com/story"


def test_normalize_items_removes_duplicate_urls():
    first = make_item("First title", "https://example.com/story")
    duplicate = make_item("Different title", "https://example.com/story/")

    items = normalize_items([first, duplicate])

    assert len(items) == 1
    assert items[0].title == "First title"


def test_normalize_items_keeps_distinct_items():
    items = normalize_items(
        [
            make_item("One", "https://example.com/one"),
            make_item("Two", "https://example.com/two"),
        ]
    )

    assert len(items) == 2
