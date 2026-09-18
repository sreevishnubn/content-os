"""Concrete automation handlers for production-safe ContentOS jobs.

Handlers preserve the human-review boundary: research and script jobs can run
automatically, while publishing requires explicit payloads and server-side OAuth.
Rendering runs on worker infrastructure, never inside a Vercel request.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json, os, tempfile
from pathlib import Path

from app.analytics.models import VideoMetrics
from app.database.connection import get_connection, using_postgres
from app.api.common import execute, prepare_database, one
from app.integrations.youtube import YouTubeProvider
from app.integrations.youtube_oauth import load_server_credentials
from app.integrations.artifacts import materialize_artifact
from app.integrations.openai_tts import OpenAITTSProvider
from app.integrations.renderer import FFmpegRenderer


def research_youtube(payload: dict) -> dict:
    from app.api.app import YouTubeResearchRequest, research_youtube as run_research
    return run_research(YouTubeResearchRequest(
        channel_ids=payload["channel_ids"], query=payload.get("query", ""),
        limit=payload.get("limit", 20), generate_ideas=payload.get("generate_ideas", True)))


def generate_script(payload: dict) -> dict:
    from app.api.workflow import ScriptDraftRequest, create_script
    return create_script(ScriptDraftRequest(idea_id=payload["idea_id"]))


def publish_youtube(payload: dict) -> dict:
    from app.api.workflow import YouTubePublishRequest, publish_to_youtube
    return publish_to_youtube(payload["publish_id"], YouTubePublishRequest(
        privacy_status=payload.get("privacy_status", "private"),
        category_id=payload.get("category_id", "22")))


def sync_youtube_analytics(payload: dict) -> dict:
    credentials = load_server_credentials()
    if credentials is None:
        raise RuntimeError("YouTube analytics is not configured. Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN.")
    report = YouTubeProvider(credentials).channel_report(str(payload["start_date"]), str(payload["end_date"]))
    connection = get_connection()
    inserted = 0
    try:
        prepare_database(connection)
        for values in report.get("rows", []):
            if len(values) < 9:
                continue
            captured_at = datetime.fromisoformat(str(values[0]).replace("Z", "+00:00"))
            if captured_at.tzinfo is None:
                captured_at = captured_at.replace(tzinfo=timezone.utc)
            metric = VideoMetrics(
                external_video_id=str(payload.get("external_video_id", "channel")),
                captured_at=captured_at, views=int(values[1] or 0),
                watch_time_minutes=float(values[2] or 0),
                average_view_duration_seconds=float(values[3] or 0),
                likes=int(values[4] or 0), comments=int(values[5] or 0),
                subscribers_gained=int(values[6] or 0), impressions=int(values[7] or 0),
                click_through_rate=float(values[8] or 0))
            execute(connection, """INSERT INTO video_metrics
                (metric_id,external_video_id,captured_at,views,watch_time_minutes,
                 average_view_duration_seconds,impressions,click_through_rate,
                 likes,comments,subscribers_gained,revenue)
                VALUES (:id,:video,:captured,:views,:watch,:avd,:impressions,:ctr,
                        :likes,:comments,:subs,:revenue)""", {
                "id": metric.metric_id, "video": metric.external_video_id,
                "captured": metric.captured_at, "views": metric.views,
                "watch": metric.watch_time_minutes, "avd": metric.average_view_duration_seconds,
                "impressions": metric.impressions, "ctr": metric.click_through_rate,
                "likes": metric.likes, "comments": metric.comments,
                "subs": metric.subscribers_gained, "revenue": metric.revenue})
            inserted += 1
        connection.commit()
        return {"rows": len(report.get("rows", [])), "metrics_recorded": inserted}
    finally:
        connection.close()


def production_render(payload: dict) -> dict:
    """Render a production job on worker infrastructure and persist its artifact."""
    production_id = str(payload["production_id"])
    connection = get_connection()
    temporary_paths: list[str] = []
    try:
        prepare_database(connection)
        job = one(connection, "SELECT production_id,script_id,status,asset_paths_json FROM production_jobs WHERE production_id=:id", {"id": production_id})
        if not job:
            raise RuntimeError(f"Production job not found: {production_id}")
        if job["status"] == "READY":
            return {"production_id": production_id, "status": "READY"}
        if job["status"] not in {"QUEUED", "ASSETS", "RENDERING"}:
            raise RuntimeError(f"Production job is not renderable from status {job['status']}")
        script = one(connection, "SELECT hook,sections_json,closing FROM content_scripts WHERE script_id=:id", {"id": job["script_id"]})
        if not script:
            raise RuntimeError(f"Script not found: {job['script_id']}")
        assets = json.loads(job["asset_paths_json"] or "[]")
        if not isinstance(assets, list) or not assets:
            raise RuntimeError("Production requires at least one approved image/video asset")

        if using_postgres():
            from sqlalchemy import text
            connection.execute(text("UPDATE production_jobs SET status='ASSETS',error=NULL WHERE production_id=:id"), {"id": production_id})
        else:
            connection.execute("UPDATE production_jobs SET status='ASSETS',error=NULL WHERE production_id=?", (production_id,))
        connection.commit()

        local_assets = []
        for uri in assets:
            local, temporary = materialize_artifact(str(uri))
            local_assets.append(local)
            if temporary:
                temporary_paths.append(local)

        sections = json.loads(script["sections_json"] or "[]")
        narration = " ".join([str(script["hook"])] + [str(s.get("narration", "")) for s in sections] + [str(script["closing"] or "")]).strip()
        if not narration:
            raise RuntimeError("Script contains no narration")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required on the rendering worker")

        if using_postgres():
            from sqlalchemy import text
            connection.execute(text("UPDATE production_jobs SET status='RENDERING',error=NULL WHERE production_id=:id"), {"id": production_id})
        else:
            connection.execute("UPDATE production_jobs SET status='RENDERING',error=NULL WHERE production_id=?", (production_id,))
        connection.commit()

        with tempfile.TemporaryDirectory(prefix="contentos-render-") as tmp:
            output = Path(tmp) / f"{production_id}.mp4"
            audio = Path(tmp) / f"{production_id}.mp3"
            OpenAITTSProvider(
                api_key=api_key,
                model=os.getenv("CONTENTOS_TTS_MODEL", "gpt-4o-mini-tts"),
                voice=os.getenv("CONTENTOS_TTS_VOICE", "alloy")).synthesize(narration, str(audio))
            FFmpegRenderer().render(local_assets, str(audio), str(output),
                                    seconds_per_image=int(payload.get("seconds_per_image", 6)))

            bucket = os.getenv("CONTENTOS_ARTIFACT_BUCKET")
            prefix = os.getenv("CONTENTOS_ARTIFACT_PREFIX", "contentos/renders").strip("/")
            if bucket:
                import boto3
                key = f"{prefix}/{production_id}.mp4"
                boto3.client("s3").upload_file(str(output), bucket, key, ExtraArgs={"ContentType": "video/mp4"})
                artifact_uri = f"s3://{bucket}/{key}"
            else:
                if os.getenv("CONTENTOS_ENVIRONMENT", "development").lower() == "production":
                    raise RuntimeError("CONTENTOS_ARTIFACT_BUCKET is required in production")
                destination = Path(os.getenv("CONTENTOS_LOCAL_ARTIFACT_DIR", "data/output")) / f"{production_id}.mp4"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(output.read_bytes())
                artifact_uri = str(destination.resolve())

        if using_postgres():
            from sqlalchemy import text
            connection.execute(text("UPDATE production_jobs SET output_path=:artifact,status='READY',error=NULL WHERE production_id=:id"), {"artifact": artifact_uri, "id": production_id})
        else:
            connection.execute("UPDATE production_jobs SET output_path=?,status='READY',error=NULL WHERE production_id=?", (artifact_uri, production_id))
        connection.commit()
        return {"production_id": production_id, "status": "READY", "artifact_uri": artifact_uri}
    except Exception as exc:
        try:
            message = f"{type(exc).__name__}: {exc}"
            if using_postgres():
                from sqlalchemy import text
                connection.execute(text("UPDATE production_jobs SET status='FAILED',error=:error WHERE production_id=:id"), {"error": message, "id": production_id})
            else:
                connection.execute("UPDATE production_jobs SET status='FAILED',error=? WHERE production_id=?", (message, production_id))
            connection.commit()
        except Exception:
            connection.rollback()
        raise
    finally:
        for path in temporary_paths:
            Path(path).unlink(missing_ok=True)
        connection.close()


HANDLERS = {
    "research_youtube": research_youtube,
    "generate_script": generate_script,
    "production_render": production_render,
    "publish_youtube": publish_youtube,
    "sync_youtube_analytics": sync_youtube_analytics,
}
