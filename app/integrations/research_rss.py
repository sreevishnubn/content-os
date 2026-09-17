"""RSS/Atom research provider.

RSS is intentionally the first production research adapter because it is
simple, auditable and does not require a provider-specific search API key.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx

from app.research.models import ResearchItem


class RSSResearchProvider:
    name = "rss"

    def search(self, query: str, *, limit: int = 20) -> list[ResearchItem]:
        """Search a configured feed URL or feed list.

        `query` is interpreted as a comma-separated list of RSS/Atom URLs.
        ContentOS filters matching entries locally by title/summary.
        """
        feeds = [item.strip() for item in query.split(",") if item.strip()]
        results: list[ResearchItem] = []
        for feed_url in feeds:
            response = httpx.get(feed_url, timeout=20, follow_redirects=True)
            response.raise_for_status()
            results.extend(self._parse(response.text, feed_url))
        terms = [term.lower() for term in query.split() if "://" not in term]
        if terms:
            results = [
                item for item in results
                if any(term in f"{item.title} {item.summary}".lower() for term in terms)
            ]
        return results[:limit]

    @staticmethod
    def _parse(xml_text: str, feed_url: str) -> list[ResearchItem]:
        root = ET.fromstring(xml_text)
        items: list[ResearchItem] = []
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
                continue
            values = {
                child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
                for child in list(element)
            }
            title = values.get("title", "").strip()
            summary = values.get("description") or values.get("summary") or values.get("content") or title
            link = values.get("link")
            published = values.get("pubDate") or values.get("published") or values.get("updated")
            published_at = None
            if published:
                try:
                    published_at = parsedate_to_datetime(published)
                except (TypeError, ValueError):
                    try:
                        published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    except ValueError:
                        published_at = None
            items.append(
                ResearchItem(
                    title=title or "Untitled research item",
                    summary=summary[:10000],
                    url=link or feed_url,
                    source_name=feed_url,
                    published_at=published_at,
                    discovered_at=datetime.now(timezone.utc),
                )
            )
        return items
