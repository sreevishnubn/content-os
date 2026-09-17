"""Normalize video performance against a channel's own baseline."""

from statistics import median


def channel_median_views(views: list[int]) -> float:
    values = [max(0, int(v)) for v in views]
    if not values:
        raise ValueError("At least one view count is required")
    return float(median(values))


def performance_multiple(views: int, baseline_views: float) -> float:
    if baseline_views <= 0:
        raise ValueError("baseline_views must be greater than zero")
    return round(max(0, views) / baseline_views, 2)


def rank_outliers(videos: list[dict], minimum_multiple: float = 1.5) -> list[dict]:
    """Return public video records whose views exceed their channel baseline.

    Input records require: channel, views. If a record contains
    channel_views, that list is used as the channel baseline.
    """
    result = []
    for video in videos:
        baseline_values = video.get("channel_views")
        if not baseline_values:
            continue
        baseline = channel_median_views(baseline_values)
        multiple = performance_multiple(int(video.get("views", 0)), baseline)
        if multiple >= minimum_multiple:
            result.append({**video, "channel_median_views": baseline, "performance_multiple": multiple})
    return sorted(result, key=lambda x: x["performance_multiple"], reverse=True)
