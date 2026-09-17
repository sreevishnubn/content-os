"""Identify candidate short-form segments from transcript beats."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortCandidate:
    start_seconds: float
    end_seconds: float
    hook: str
    reason: str


def find_candidates(beats: list[dict], min_seconds: float = 15, max_seconds: float = 60) -> list[ShortCandidate]:
    """Select self-contained transcript beats suitable for Shorts review."""
    candidates: list[ShortCandidate] = []
    for beat in beats:
        start = float(beat["start_seconds"])
        end = float(beat["end_seconds"])
        duration = end - start
        text = str(beat.get("text", "")).strip()
        if min_seconds <= duration <= max_seconds and len(text) >= 60:
            candidates.append(ShortCandidate(start, end, text[:140], "Self-contained beat within short-form duration"))
    return candidates
