"""Resolve public YouTube handles and URLs to stable channel IDs."""

import re
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

CHANNEL_ID_RE = re.compile(r"(?:channelId|externalId)\"\s*[:=]\s*\"(UC[a-zA-Z0-9_-]{20,})\"")
PLAIN_CHANNEL_ID_RE = re.compile(r"\b(UC[a-zA-Z0-9_-]{20,})\b")


def _normalize_source(source: str) -> str:
    value = source.strip()
    if not value:
        raise ValueError("YouTube channel cannot be empty")
    if value.startswith("UC") and PLAIN_CHANNEL_ID_RE.fullmatch(value):
        return value
    if value.startswith("@"):
        return f"https://www.youtube.com/{quote(value, safe='@')}/about"
    if not value.startswith(("http://", "https://")):
        return f"https://www.youtube.com/@{quote(value.lstrip('@'), safe='')}/about"
    return value.rstrip("/") + ("/about" if "/about" not in value else "")


def resolve_channel_id(source: str, *, timeout: int = 10) -> str:
    """Resolve a channel ID, @handle, or public YouTube channel URL."""
    normalized = _normalize_source(source)
    if normalized.startswith("UC") and PLAIN_CHANNEL_ID_RE.fullmatch(normalized):
        return normalized

    request = Request(normalized, headers={"User-Agent": "ContentOS/1.0"})
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")

    match = CHANNEL_ID_RE.search(html) or PLAIN_CHANNEL_ID_RE.search(html)
    if not match:
        raise ValueError(f"Could not resolve a YouTube channel ID from: {source}")
    return match.group(1)


def resolve_channel_ids(sources: list[str], *, timeout: int = 10) -> list[str]:
    """Resolve and deduplicate channel sources while preserving input order."""
    resolved: list[str] = []
    seen: set[str] = set()
    for source in sources:
        channel_id = resolve_channel_id(source, timeout=timeout)
        if channel_id not in seen:
            seen.add(channel_id)
            resolved.append(channel_id)
    return resolved
