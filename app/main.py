"""ContentOS V0 executable smoke test."""

from app.ideas.generator import build_ideas
from app.ideas.scorer import rank_ideas


SAMPLE_OPPORTUNITIES = [
    {
        "title": "The hidden reason this everyday technology is changing",
        "topic": "Emerging technology",
        "audience": "Curious technology viewers",
        "hook": "Most people are watching the visible change, but the real story is underneath.",
        "why_now": "The topic is actively evolving.",
        "monetization_angle": "Technology tools and software sponsorships.",
        "demand": 8,
        "curiosity": 9,
        "competition": 6,
        "monetization": 8,
        "production": 7,
    },
    {
        "title": "A simple system that saves hours every week",
        "topic": "Productivity systems",
        "audience": "People looking for practical productivity improvements",
        "hook": "You do not need more motivation; you need a better system.",
        "why_now": "Automation tools are changing how people work.",
        "monetization_angle": "Productivity software and tool affiliates.",
        "demand": 8,
        "curiosity": 7,
        "competition": 5,
        "monetization": 9,
        "production": 9,
    },
    {
        "title": "What actually happens when you press this button",
        "topic": "Explainer content",
        "audience": "General knowledge viewers",
        "hook": "The process starts long before you see the result.",
        "demand": 6,
        "curiosity": 9,
        "competition": 7,
        "monetization": 5,
        "production": 8,
    },
]


def main() -> None:
    ideas = rank_ideas(build_ideas(SAMPLE_OPPORTUNITIES))

    print("ContentOS V0 — Idea Engine smoke test")
    print(f"Generated: {len(ideas)} ideas")
    print("\nRanked opportunities:")
    for position, idea in enumerate(ideas, start=1):
        print(f"{position}. {idea.title} — {idea.overall_score}/10")


if __name__ == "__main__":
    main()
