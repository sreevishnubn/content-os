"""Concrete automation handlers for production-safe ContentOS jobs.

Handlers deliberately preserve the human-review boundary: research and script
jobs can run automatically, while publishing requires an explicit job payload
and server-side YouTube OAuth credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

from app.analytics.models import VideoMetrics
from app.database.connection import get_connection, using_postgres
from app.api.common import execute, prepare_database, one
from app.integrations.youtube import YouTubeProvider
from app.integrations.youtube_oauth import load_server_credentials


def research_youtube(payload: dict) -> dict:
    from app.api.app import YouTubeResearchRequest, research_youtube as run_research

    request = YouTubeResearchRequest(
        channel_ids=payload["channel_ids"],
        query=payload.get("query", ""),
        limit=payload.get("limit", 20),
        generate_ideas=payload.get("generate_ideas", True),
    )
    return run_research(request)


def generate_script(payload: dict) -> dict:
    from app.api.workflow import ScriptDraftRequest, create_script

    return create_script(ScriptDraftRequest(idea_id=payload["idea_id"]))


def publish_youtube(payload: dict) -> dict:
    from app.api.workflow import YouTubePublishRequest, publish_to_youtube

    request = YouTubePublishRequest(
        privacy_status=payload.get("privacy_status", "private"),
        category_id=payload.get("category_id", "22"),
    )
    return publish_to_youtube(payload["publish_id"], request)


def sync_youtube_analytics(payload: dict) -> dict:
    credentials = load_server_credentials()
    if credentials is None:
        raise RuntimeError(
            "YouTube analytics is not configured. Set YOUTUBE_CLIENT_ID, "
            "YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN."
        )

    start_date = str(payload["start_date"])
    end_date = str(payload["end_date"])
    report = YouTubeProvider(credentials).channel_report(start_date, end_date)
    rows = report.get("rows", [])
    connection = get_connection()
    inserted = 0
    try:
        prepare_database(connection)
        for values in rows:
            if len(values) < 9:
                continue
            captured_at = datetime.fromisoformat(str(values[0]).replace("Z", "+00:00"))
            if captured_at.tzinfo is None:
                captured_at = captured_at.replace(tzinfo=timezone.utc)
            metric = VideoMetrics(
                external_video_id=str(payload.get("external_video_id", "channel")),
                captured_at=captured_at,
                views=int(values[1] or 0),
                watch_time_minutes=float(values[2] or 0),
                average_view_duration_seconds=float(values[3] or 0),
                likes=int(values[4] or 0),
                comments=int(values[5] or 0),
                subscribers_gained=int(values[6] or 0),
                impressions=int(values[7] or 0),
                click_through_rate=float(values[8] or 0),
            )
            execute(
                connection,
                """INSERT INTO video_metrics
                (metric_id,external_video_id,captured_at,views,watch_time_minutes,
                 average_view_duration_seconds,impressions,click_through_rate,
                 likes,comments,subscribers_gained,revenue)
                VALUES (:id,:video,:captured,:views,:watch,:avd,:impressions,:ctr,
                        :likes,:comments,:subs,:revenue)""",
                {
                    "id": metric.metric_id, "video": metric.external_video_id,
                    "captured": metric.captured_at, "views": metric.views,
                    "watch": metric.watch_time_minutes,
                    "avd": metric.average_view_duration_seconds,
                    "impressions": metric.impressions,
                    "ctr": metric.click_through_rate, "likes": metric.likes,
                    "comments": metric.comments, "subs": metric.subscribers_gained,
                    "revenue": metric.revenue,
                },
            )
            inserted += 1
        connection.commit()
        return {"rows": len(rows), "metrics_recorded": inserted}
    finally:
        connection.close()


def unsupported_production(payload: dict) -> None:
    raise RuntimeError(
        "Automatic production rendering is not configured. Run TTS/FFmpeg "
        "on worker infrastructure, upload the MP4 to HTTPS or S3, then "
        "register the artifact before marking production READY."
    )


HANDLERS = {
    "research_youtube": research_youtube,
    "generate_script": generate_script,
    "publish_youtube": publish_youtube,
    "sync_youtube_analytics": sync_youtube_analytics,
    "production_render": unsupported_production,
}
