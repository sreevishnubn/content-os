"""Keyless YouTube channel-page research provider.

Uses the public channel /videos page rather than the deprecated RSS endpoint.
This is intentionally metadata-only: no video download or login is required.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.research.interface import ResearchProvider
from app.research.models import ResearchItem


_INITIAL_DATA_RE = re.compile(
    rb'<script[^>]+id=["\']ytInitialData["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _walk_video_renderers(value: Any):
    if isinstance(value, dict):
        renderer = value.get("videoRenderer")
        if isinstance(renderer, dict) and renderer.get("videoId"):
            yield renderer
        for child in value.values():
            yield from _walk_video_renderers(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_video_renderers(child)


def _title(renderer: dict[str, Any]) -> str:
    title = renderer.get("title") or {}
    runs = title.get("runs") or []
    if runs:
        return _clean("".join(str(run.get("text", "")) for run in runs))
    return _clean(title.get("simpleText"))


def _description(renderer: dict[str, Any]) -> str:
    snippet = renderer.get("detailedMetadataSnippets") or []
    if snippet:
        return _clean(
            " ".join(
                str(run.get("text", ""))
                for run in (snippet[0].get("snippetText", {}).get("runs") or [])
            )
        )
    return ""


def _published(renderer: dict[str, Any]) -> datetime | None:
    text = _clean((renderer.get("publishedTimeText") or {}).get("simpleText"))
    # Relative YouTube timestamps are intentionally not converted to a
    # fabricated date. The channel page remains valid evidence even when the
    # exact timestamp is unavailable.
    if not text:
        return None
    return None


def parse_channel_page(html: bytes, *, limit: int = 20) -> list[ResearchItem]:
    match = _INITIAL_DATA_RE.search(html)
    if not match:
        raise RuntimeError("YouTube channel page did not contain ytInitialData")

    try:
        data = json.loads(match.group(1).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not parse YouTube channel metadata") from exc

    items: list[ResearchItem] = []
    seen: set[str] = set()
    for renderer in _walk_video_renderers(data):
        video_id = str(renderer.get("videoId", "")).strip()
        title = _title(renderer)
        if not video_id or not title or video_id in seen:
            continue
        seen.add(video_id)
        owner = _clean(
            (renderer.get("ownerText") or {}).get("runs", [{}])[0].get("text")
        )
        items.append(
            ResearchItem(
                title=title,
                summary=_description(renderer) or f"Published by {owner or 'YouTube channel'}.",
                url=f"https://www.youtube.com/watch?v={quote(video_id, safe='')}",
                source_name=f"YouTube — {owner or 'Channel'}",
                published_at=_published(renderer),
                tags=["youtube", "video", "research"],
            )
        )
        if len(items) >= max(1, min(limit, 100)):
            break
    return items


class YouTubeWebProvider(ResearchProvider):
    """Collect recent public uploads from the YouTube channel page."""

    name = "youtube_web"

    def __init__(self, channel_ids: list[str], *, timeout: int = 15) -> None:
        self.channel_ids = [value.strip() for value in channel_ids if value.strip()]
        self.timeout = timeout

    def search(self, query: str = "", *, limit: int = 10) -> list[ResearchItem]:
        results: list[ResearchItem] = []
        for channel_id in self.channel_ids:
            url = f"https://www.youtube.com/channel/{quote(channel_id, safe='')}/videos"
            request = Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urlopen(request, timeout=self.timeout) as response:
                html = response.read()
            results.extend(parse_channel_page(html, limit=limit))

        terms = [term for term in query.strip().lower().split() if term]
        if terms:
            results = [
                item
                for item in results
                if all(term in f"{item.title} {item.summary}".lower() for term in terms)
            ]

        return results[: max(1, min(limit, 100))]
