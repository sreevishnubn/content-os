"""Retention analysis primitives for turning viewer drop-offs into signals."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionCliff:
    timestamp_seconds: float
    drop: float
    label: str


def find_cliffs(points: list[dict], threshold: float = 0.08) -> list[RetentionCliff]:
    """Find meaningful adjacent retention drops.

    Each point requires ``timestamp_seconds`` and ``retention`` (0..1).
    """
    ordered = sorted(points, key=lambda p: float(p["timestamp_seconds"]))
    cliffs: list[RetentionCliff] = []
    for previous, current in zip(ordered, ordered[1:]):
        drop = float(previous["retention"]) - float(current["retention"])
        if drop >= threshold:
            label = "hook" if float(current["timestamp_seconds"]) <= 30 else "body"
            cliffs.append(RetentionCliff(float(current["timestamp_seconds"]), round(drop, 4), label))
    return cliffs


def retention_summary(points: list[dict]) -> dict[str, object]:
    cliffs = find_cliffs(points)
    return {
        "cliffs": [c.__dict__ for c in cliffs],
        "largest_drop": max((c.drop for c in cliffs), default=0.0),
        "cliff_count": len(cliffs),
    }
