"""RSS/Atom research provider."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx

from app.research.models import ResearchItem


class RSSResearchProvider:
    name = "rss"

    def fetch(self, feed_urls: list[str], *, limit: int = 20) -> list[ResearchItem]:
        results: list[ResearchItem] = []
        for feed_url in feed_urls:
            response = httpx.get(feed_url, timeout=20, follow_redirects=True)
            response.raise_for_status()
            results.extend(self._parse(response.text, feed_url))
        return results[:limit]

    def search(self, query: str, *, limit: int = 20) -> list[ResearchItem]:
        """Treat query as comma-separated feed URLs for the V1 RSS provider."""
        feeds = [item.strip() for item in query.split(",") if item.strip()]
        return self.fetch(feeds, limit=limit)

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
            link = values.get("link") or feed_url
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
                    url=link,
                    source_name=feed_url,
                    published_at=published_at,
                    discovered_at=datetime.now(timezone.utc),
                )
            )
        return items
