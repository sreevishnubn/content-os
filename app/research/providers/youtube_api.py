"""YouTube Data API v3 research provider.

Uses the official YouTube Data API instead of the public RSS feed. A channel's
uploads playlist is resolved through channels.list and recent uploads are read
with playlistItems.list.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from app.research.interface import ResearchProvider
from app.research.models import ResearchItem


class YouTubeAPIProvider(ResearchProvider):
    """Fetch recent public uploads for YouTube channel IDs."""

    name = "youtube_api"
    base_url = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, channel_ids: list[str], *, timeout: int = 15) -> None:
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is required for YouTube research")
        self.api_key = api_key
        self.channel_ids = [value.strip() for value in channel_ids if value.strip()]
        self.timeout = timeout

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/{endpoint}",
            params={"key": self.api_key, **params},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            try:
                detail = response.json().get("error", {}).get("message", response.text)
            except ValueError:
                detail = response.text
            raise RuntimeError(
                f"YouTube Data API {endpoint} failed ({response.status_code}): {detail}"
            )
        return response.json()

    @staticmethod
    def _published(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _uploads_playlist(self, channel_id: str) -> str:
        data = self._get(
            "channels",
            {"part": "snippet,contentDetails", "id": channel_id},
        )
        items = data.get("items", [])
        if not items:
            raise RuntimeError(f"YouTube channel not found: {channel_id}")
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def search(self, query: str = "", *, limit: int = 10) -> list[ResearchItem]:
        results: list[ResearchItem] = []
        per_channel = min(max(limit, 1), 50)

        for channel_id in self.channel_ids:
            playlist_id = self._uploads_playlist(channel_id)
            data = self._get(
                "playlistItems",
                {
                    "part": "snippet,contentDetails",
                    "playlistId": playlist_id,
                    "maxResults": per_channel,
                },
            )

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                content = item.get("contentDetails", {})
                video_id = content.get("videoId")
                title = (snippet.get("title") or "").strip()
                if not video_id or not title:
                    continue

                description = " ".join((snippet.get("description") or "").split())
                channel_title = snippet.get("channelTitle") or channel_id
                results.append(
                    ResearchItem(
                        title=title,
                        summary=description or f"Published by {channel_title}.",
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        source_name=f"YouTube — {channel_title}",
                        published_at=self._published(snippet.get("publishedAt")),
                        tags=["youtube", "video", "research"],
                    )
                )

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
