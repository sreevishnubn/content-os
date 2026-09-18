"""YouTube research adapter using public channel RSS feeds.

This V0 adapter does not require a YouTube API key. It reads public uploads
from configured channel IDs and converts them into normalized research
items. It deliberately does not scrape search pages or require a login.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from urllib.request import HTTPError, Request, urlopen
import time
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
            channel_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={quote(channel_id, safe='')}"
            uploads_playlist_id = f"UU{channel_id[2:]}" if channel_id.startswith("UC") else ""
            playlist_url = (
                f"https://www.youtube.com/feeds/videos.xml?playlist_id={quote(uploads_playlist_id, safe='')}"
                if uploads_playlist_id else None
            )
            feed_urls = [channel_url] + ([playlist_url] if playlist_url else [])
            last_error: Exception | None = None
            xml_text: str | None = None

            # Try the channel feed first, then the uploads-playlist feed.
            for feed_url in feed_urls:
                for attempt in range(3):
                    url = f"{feed_url}&_contentos={int(time.time() * 1000)}"
                    request = Request(
                        url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (compatible; ContentOS/1.0; +https://dashboard.youtube.analysis.com)",
                            "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
                            "Cache-Control": "no-cache",
                        },
                    )
                    try:
                        with urlopen(request, timeout=self.timeout) as response:
                            xml_text = response.read().decode("utf-8")
                        break
                    except HTTPError as exc:
                        last_error = exc
                        if exc.code not in {404, 429, 500, 502, 503, 504} or attempt == 2:
                            break
                    except Exception as exc:
                        last_error = exc
                        if attempt == 2:
                            break
                    time.sleep(1.0 * (attempt + 1))
                if xml_text is not None:
                    break
            if xml_text is None:
                raise RuntimeError(
                    f"YouTube RSS temporarily unavailable for channel {channel_id} after 3 attempts: {last_error}"
                ) from last_error

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
