"""Keyless YouTube channel-page research fallback.

This adapter reads the public /videos page and extracts the video cards that
YouTube embeds in the page. It is intentionally metadata-only and does not
download media or require an API key.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.request import Request, urlopen

from app.research.interface import ResearchProvider
from app.research.models import ResearchItem


class YouTubeHTMLProvider(ResearchProvider):
    name = "youtube_html"

    def __init__(self, channel_ids: list[str], *, timeout: int = 15) -> None:
        self.channel_ids = [value.strip() for value in channel_ids if value.strip()]
        self.timeout = timeout

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, dict):
            if value.get("simpleText"):
                return " ".join(str(value["simpleText"]).split())
            runs = value.get("runs") or []
            return " ".join(str(run.get("text", "")) for run in runs).strip()
        return " ".join(str(value or "").split())

    @staticmethod
    def _published(value: Any) -> datetime | None:
        text = YouTubeHTMLProvider._text(value)
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _objects(html: str) -> list[dict[str, Any]]:
        marker = '"videoRenderer":'
        results: list[dict[str, Any]] = []
        start = 0
        while True:
            index = html.find(marker, start)
            if index < 0:
                break
            pos = index + len(marker)
            while pos < len(html) and html[pos].isspace():
                pos += 1
            if pos >= len(html) or html[pos] != "{":
                start = pos
                continue

            depth = 0
            in_string = False
            escaped = False
            end = None
            for cursor in range(pos, len(html)):
                char = html[cursor]
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        in_string = False
                    continue
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        end = cursor + 1
                        break

            if end:
                try:
                    results.append(json.loads(html[pos:end]))
                except json.JSONDecodeError:
                    pass
                start = end
            else:
                break
        return results

    def _extract(self, channel_id: str, limit: int) -> list[ResearchItem]:
        url = f"https://www.youtube.com/channel/{channel_id}/videos"
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            html = response.read().decode("utf-8", errors="replace")

        items: list[ResearchItem] = []
        seen: set[str] = set()
        for renderer in self._objects(html):
            video_id = str(renderer.get("videoId") or "").strip()
            title = self._text(renderer.get("title"))
            if not video_id or not title or video_id in seen:
                continue

            seen.add(video_id)
            description = self._text(renderer.get("descriptionSnippet"))
            published = self._published(renderer.get("publishedTimeText"))
            items.append(
                ResearchItem(
                    title=unescape(title),
                    summary=unescape(description) or "Public YouTube video.",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    source_name="YouTube",
                    published_at=published,
                    tags=["youtube", "video", "research"],
                )
            )
            if len(items) >= min(max(limit, 1), 100):
                break

        if not items:
            raise RuntimeError(
                f"YouTube channel page returned no video cards for {channel_id}"
            )
        return items

    def search(self, query: str = "", *, limit: int = 10) -> list[ResearchItem]:
        results: list[ResearchItem] = []
        for channel_id in self.channel_ids:
            results.extend(self._extract(channel_id, limit))

        normalized_query = query.strip().lower()
        if normalized_query:
            terms = [term for term in normalized_query.split() if term]
            results = [
                item
                for item in results
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
