"""YouTube research adapter using public channel RSS feeds.

This V0 adapter does not require a YouTube API key. It reads public uploads
from configured channel IDs and converts them into normalized research
items. It deliberately does not scrape search pages or require a login.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from app.research.interface import ResearchProvider
from app.research.models import ResearchItem

YT_NS = "http://www.youtube.com/xml/schemas/2015"
MEDIA_NS = "http://search.yahoo.com/mrss/"
ATOM_NS = "http://www.w3.org/2005/Atom"


def _text(element: ET.Element | None) -> str:
    return " ".join((element.text or "").split()) if element is not None else ""


def parse_youtube_feed(xml_text: str, *, limit: int = 15) -> list[ResearchItem]:
    """Parse a public YouTube channel Atom feed into research evidence."""
    root = ET.fromstring(xml_text)
    channel_title = _text(root.find(f"{{{ATOM_NS}}}title"))
    items: list[ResearchItem] = []

    for entry in root.findall(f"{{{ATOM_NS}}}entry")[: max(1, min(limit, 50))]:
        video_id = _text(entry.find(f"{{{YT_NS}}}videoId"))
        title = _text(entry.find(f"{{{ATOM_NS}}}title"))
        published_raw = _text(entry.find(f"{{{ATOM_NS}}}published"))
        description = _text(entry.find(f"{{{MEDIA_NS}}}group/{{{MEDIA_NS}}}description"))
        author = _text(entry.find(f"{{{ATOM_NS}}}author/{{{ATOM_NS}}}name")) or channel_title

        if not video_id or not title:
            continue

        published_at: datetime | None = None
        if published_raw:
            try:
                published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            except ValueError:
                try:
                    published_at = parsedate_to_datetime(published_raw)
                except (TypeError, ValueError):
                    published_at = None

        summary = description or f"Published by {author}."
        items.append(
            ResearchItem(
                title=title,
                summary=summary,
                url=f"https://www.youtube.com/watch?v={quote(video_id)}",
                source_name=f"YouTube — {author}",
                published_at=published_at,
                tags=["youtube", "video", "research"],
            )
        )

    return items


class YouTubeRSSProvider(ResearchProvider):
    """Fetch recent uploads from configured public YouTube channels."""

    name = "youtube_rss"

    def __init__(self, channel_ids: list[str], *, timeout: int = 10) -> None:
        self.channel_ids = [channel_id.strip() for channel_id in channel_ids if channel_id.strip()]
        self.timeout = timeout

    def search(self, query: str = "", *, limit: int = 10) -> list[ResearchItem]:
        """Return recent uploads whose title/description matches query when supplied."""
        results: list[ResearchItem] = []
        for channel_id in self.channel_ids:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={quote(channel_id, safe='')}"
            request = Request(url, headers={"User-Agent": "ContentOS/1.0"})
            with urlopen(request, timeout=self.timeout) as response:
                xml_text = response.read().decode("utf-8")
            results.extend(parse_youtube_feed(xml_text, limit=50))

        normalized_query = query.strip().lower()
        if normalized_query:
            terms = [term for term in normalized_query.split() if term]
            results = [
                item for item in results
                if all(term in f"{item.title} {item.summary}".lower() for term in terms)
            ]

        def published_timestamp(item: ResearchItem) -> float:
            value = item.published_at
            if value is None:
                return float("-inf")
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.timestamp()

        results.sort(key=published_timestamp, reverse=True)
        return results[: max(1, min(limit, 100))]
