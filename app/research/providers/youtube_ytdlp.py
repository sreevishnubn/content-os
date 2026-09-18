"""Keyless YouTube research collection through yt-dlp."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.research.interface import ResearchProvider
from app.research.models import ResearchItem


class YouTubeYTDLPProvider(ResearchProvider):
    """Fetch recent public channel uploads without a YouTube API key."""

    name = "youtube_ytdlp"

    def __init__(self, channel_ids: list[str], *, timeout: int = 15) -> None:
        self.channel_ids = [value.strip() for value in channel_ids if value.strip()]
        self.timeout = timeout

    @staticmethod
    def _published(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            result = value
        else:
            try:
                result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result

    @staticmethod
    def _clean_text(value: Any) -> str:
        return " ".join(str(value or "").split())

    def _extract(self, channel_id: str, limit: int) -> list[dict[str, Any]]:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError(
                "yt-dlp is not installed; add yt-dlp to requirements.txt"
            ) from exc

        url = f"https://www.youtube.com/channel/{channel_id}/videos"
        options = {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "extract_flat": True,
            "skip_download": True,
            "playlistend": min(max(limit, 1), 100),
            "socket_timeout": self.timeout,
            "retries": 2,
            "fragment_retries": 2,
            "noplaylist": False,
        }

        with YoutubeDL(options) as ydl:
            data = ydl.extract_info(url, download=False)

        if not data:
            raise RuntimeError(f"yt-dlp returned no channel data for {channel_id}")

        entries = data.get("entries") or []
        return [entry for entry in entries if entry][: min(max(limit, 1), 100)]

    def search(self, query: str = "", *, limit: int = 10) -> list[ResearchItem]:
        results: list[ResearchItem] = []

        for channel_id in self.channel_ids:
            entries = self._extract(channel_id, limit)

            for entry in entries:
                video_id = entry.get("id") or entry.get("url")
                title = self._clean_text(entry.get("title"))
                if not video_id or not title:
                    continue

                video_id = str(video_id).split("?", 1)[0].rstrip("/").split("/")[-1]
                if not video_id:
                    continue

                description = self._clean_text(
                    entry.get("description") or entry.get("channel") or ""
                )
                channel_title = self._clean_text(
                    entry.get("channel") or entry.get("uploader") or channel_id
                )

                results.append(
                    ResearchItem(
                        title=title,
                        summary=description or f"Published by {channel_title}.",
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        source_name=f"YouTube — {channel_title}",
                        published_at=self._published(
                            entry.get("timestamp") or entry.get("upload_date")
                        ),
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
