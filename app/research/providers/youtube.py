"""Resilient YouTube research provider.

Provider order:
1. Official YouTube Data API when YOUTUBE_API_KEY is configured.
2. yt-dlp keyless collection.
3. Existing public RSS/Atom collector as the final fallback.

The output remains ResearchItem-compatible so the existing normalization,
deduplication, persistence, idea generation, and scoring pipeline is unchanged.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from app.research.interface import ResearchProvider
from app.research.models import ResearchItem
from app.research.providers.youtube_api import YouTubeAPIProvider
from app.research.providers.youtube_rss import YouTubeRSSProvider
from app.research.providers.youtube_ytdlp import YouTubeYTDLPProvider


class YouTubeResilientProvider(ResearchProvider):
    """Collect YouTube research evidence with graceful provider fallback."""

    name = "youtube"

    def __init__(self, channel_ids: list[str], *, timeout: int = 15) -> None:
        self.channel_ids = [value.strip() for value in channel_ids if value.strip()]
        self.timeout = timeout
        self.last_provider = ""

    def _providers(self) -> list[tuple[str, Callable[[], ResearchProvider]]]:
        providers: list[tuple[str, Callable[[], ResearchProvider]]] = []

        api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        if api_key:
            providers.append(
                (
                    "youtube_api",
                    lambda: YouTubeAPIProvider(
                        api_key,
                        self.channel_ids,
                        timeout=self.timeout,
                    ),
                )
            )

        providers.append(
            (
                "youtube_ytdlp",
                lambda: YouTubeYTDLPProvider(
                    self.channel_ids,
                    timeout=self.timeout,
                ),
            )
        )
        providers.append(
            (
                "youtube_rss",
                lambda: YouTubeRSSProvider(
                    self.channel_ids,
                    timeout=self.timeout,
                ),
            )
        )
        return providers

    def search(self, query: str = "", *, limit: int = 10) -> list[ResearchItem]:
        errors: list[str] = []

        for provider_name, factory in self._providers():
            try:
                provider = factory()
                results = provider.search(query, limit=limit)
                self.last_provider = provider_name
                return results
            except Exception as exc:
                errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")

        raise RuntimeError(
            "All YouTube research providers failed. " + " | ".join(errors)
        )
