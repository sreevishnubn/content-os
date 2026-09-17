"""Operational pipeline entrypoint.

The command is intentionally explicit: research -> normalize -> generate ->
review -> script. Publishing remains a separate command so a human can gate
production until the channel is proven.
"""

import argparse
import json

from app.ideas.generator import build_ideas
from app.ideas.scorer import rank_ideas
from app.integrations.provider_factory import build_llm_provider
from app.integrations.research_rss import RSSResearchProvider
from app.research.engine import normalize_items
from app.scripts.generator import ScriptGenerator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feeds", required=True, help="Comma-separated RSS/Atom feed URLs")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--generate-script", action="store_true")
    args = parser.parse_args()

    provider = RSSResearchProvider()
    raw = []
    for url in [item.strip() for item in args.feeds.split(",") if item.strip()]:
        raw.extend(provider._parse(__import__("httpx").get(url, timeout=20).text, url))
    research = normalize_items(raw)[: args.limit]

    candidates = []
    for item in research:
        candidates.extend(build_ideas([
            {
                "title": item.title,
                "topic": ", ".join(item.tags) or "general",
                "audience": "general audience",
                "hook": f"What changed: {item.title}",
                "source": str(item.url) if item.url else item.source_name,
                "why_now": item.summary,
                "monetization_angle": "topic-dependent sponsorship and platform monetization",
            }
        ]))
    ranked = rank_ideas(candidates)
    print(json.dumps([idea.model_dump(mode="json") for idea in ranked], indent=2))

    if args.generate_script and ranked:
        llm = build_llm_provider()
        script = ScriptGenerator(llm).generate(
            idea=ranked[0].model_dump(mode="json"),
            evidence=[item.model_dump(mode="json") for item in research],
        )
        print(json.dumps(script.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
