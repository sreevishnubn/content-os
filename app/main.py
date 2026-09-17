"""ContentOS V0 end-to-end pipeline smoke test."""

from app.ideas.from_research import research_items_to_ideas
from app.ideas.scorer import rank_ideas
from app.research.engine import normalize_items
from app.research.models import ResearchItem


SAMPLE_RESEARCH = [
    ResearchItem(
        title="AI workflow automation is changing team productivity",
        summary="Teams are adopting AI tools to automate repetitive workflows.",
        url="https://example.com/ai-workflows",
        source_name="Example Research Source",
        tags=["AI", "productivity"],
    ),
    ResearchItem(
        title="New battery technology improves energy storage",
        summary="A new battery approach is being developed to improve storage performance.",
        url="https://example.com/battery-technology",
        source_name="Example Research Source",
        tags=["technology", "energy"],
    ),
]


def run_pipeline(research_items: list[ResearchItem]):
    """Run the complete V0 path from research evidence to ranked ideas."""
    normalized = normalize_items(research_items)
    candidates = research_items_to_ideas(normalized)
    ranked = rank_ideas(candidates)
    return normalized, ranked


def main() -> None:
    normalized, ideas = run_pipeline(SAMPLE_RESEARCH)

    print("ContentOS V0 — End-to-end pipeline smoke test")
    print(f"Research items: {len(normalized)}")
    print(f"Candidate ideas: {len(ideas)}")
    print("\nRanked candidates:")
    for position, idea in enumerate(ideas, start=1):
        print(
            f"{position}. {idea.title} — {idea.overall_score}/10 "
            f"[source: {idea.source}]"
        )


if __name__ == "__main__":
    main()
