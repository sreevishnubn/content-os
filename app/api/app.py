"""Production HTTP API for the ContentOS operator dashboard."""

import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.database.models import ContentIdea
from app.database.schema import initialize_postgres_schema, initialize_schema
from app.ideas.from_research import research_items_to_ideas
from app.ideas.scorer import score_idea
from app.research.engine import normalize_items
from app.research.models import ResearchItem
from app.research.providers.youtube_rss import YouTubeRSSProvider
from app.research.repository import ResearchRepository

app = FastAPI(title="ContentOS API", version="1.0.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://([a-zA-Z0-9-]+\.)?github\.io$|https://dashboard\.youtube\.analysis\.com$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


class YouTubeResearchRequest(BaseModel):
    channel_ids: list[str] = Field(min_length=1, max_length=20)
    query: str = ""
    limit: int = Field(default=20, ge=1, le=100)
    generate_ideas: bool = True


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.api_token:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def _prepare(connection, *, bootstrap: bool = False) -> None:
    """Ensure the configured database has the ContentOS tables."""
    if using_postgres():
        initialize_postgres_schema(connection)
    else:
        initialize_schema(connection)


def _fetch_one(connection, sql: str):
    if using_postgres():
        return connection.execute(text(sql)).mappings().one()
    return connection.execute(sql).fetchone()


def _save_ideas(connection, ideas: list[ContentIdea]) -> None:
    """Persist scored ideas using the active database dialect."""
    if using_postgres():
        statement = text(
            """INSERT INTO content_ideas
            (idea_id,title,topic,audience,hook,source,why_now,monetization_angle,
             demand,curiosity,competition,monetization,production,overall_score,status,
             metadata_json,created_at)
            VALUES (:id,:title,:topic,:audience,:hook,:source,:why_now,:monetization,
                    :demand,:curiosity,:competition,:monetization_score,:production,
                    :overall,:status,:metadata,:created)"""
        )
        for idea in ideas:
            connection.execute(statement, {
                "id": idea.idea_id, "title": idea.title, "topic": idea.topic,
                "audience": idea.audience, "hook": idea.hook, "source": idea.source,
                "why_now": idea.why_now, "monetization": idea.monetization_angle,
                "demand": idea.scores.demand, "curiosity": idea.scores.curiosity,
                "competition": idea.scores.competition, "monetization_score": idea.scores.monetization,
                "production": idea.scores.production, "overall": idea.overall_score,
                "status": idea.status.value, "metadata": json.dumps(idea.metadata, sort_keys=True),
                "created": idea.created_at,
            })
    else:
        for idea in ideas:
            connection.execute(
                """INSERT OR REPLACE INTO content_ideas
                (idea_id,title,topic,audience,hook,source,why_now,monetization_angle,
                 demand,curiosity,competition,monetization,production,overall_score,status,
                 metadata_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (idea.idea_id, idea.title, idea.topic, idea.audience, idea.hook,
                 idea.source, idea.why_now, idea.monetization_angle,
                 idea.scores.demand, idea.scores.curiosity, idea.scores.competition,
                 idea.scores.monetization, idea.scores.production, idea.overall_score,
                 idea.status.value, json.dumps(idea.metadata, sort_keys=True),
                 idea.created_at.isoformat()),
            )
    connection.commit()


@app.get("/", include_in_schema=False)
def root():
    """Serve the operator dashboard at the Vercel project root."""
    dashboard = Path(__file__).resolve().parents[2] / "dashboard" / "index.html"
    if not dashboard.exists():
        raise HTTPException(status_code=500, detail="Dashboard frontend not found")
    return FileResponse(dashboard, media_type="text/html")


@app.get("/health")
def health() -> dict[str, object]:
    """Verify that the API can reach its configured database."""
    connection = None
    try:
        connection = get_connection()
        if using_postgres():
            connection.execute(text("SELECT 1"))
        else:
            _prepare(connection)
            connection.execute("SELECT 1")
        return {
            "status": "ok",
            "service": "contentos-api",
            "database": "postgres" if using_postgres() else "sqlite",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database health check failed: {type(exc).__name__}: {exc}",
        ) from exc
    finally:
        if connection is not None:
            connection.close()


@app.post("/api/research/youtube", dependencies=[Depends(require_api_token)])
def research_youtube(request: YouTubeResearchRequest) -> dict[str, object]:
    """Fetch public YouTube uploads, persist evidence, and optionally create ideas."""
    provider = YouTubeRSSProvider(request.channel_ids)
    try:
        items = normalize_items(provider.search(request.query, limit=request.limit))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"YouTube research failed: {type(exc).__name__}: {exc}") from exc

    connection = get_connection()
    try:
        _prepare(connection)
        ResearchRepository(connection, postgres=using_postgres()).save_many(items)
        ideas: list[ContentIdea] = []
        if request.generate_ideas and items:
            ideas = [score_idea(idea) for idea in research_items_to_ideas(items)]
            _save_ideas(connection, ideas)
        return {
            "provider": provider.name,
            "research_items_found": len(items),
            "ideas_created": len(ideas),
            "research": [item.model_dump(mode="json") for item in items],
            "ideas": [idea.model_dump(mode="json") for idea in ideas],
        }
    finally:
        connection.close()


@app.get("/api/dashboard/overview")
def dashboard_overview() -> dict[str, object]:
    """Return live counts across the complete content lifecycle."""
    connection = get_connection()
    try:
        _prepare(connection)
        counts = _fetch_one(
            connection,
            """
            SELECT
                (SELECT COUNT(*) FROM research_items) AS research_items,
                (SELECT COUNT(*) FROM content_ideas) AS ideas,
                (SELECT COUNT(*) FROM content_ideas WHERE status = 'APPROVED') AS approved,
                (SELECT COUNT(*) FROM content_ideas WHERE status IN ('SHORTLISTED','REVIEW')) AS review,
                (SELECT COUNT(*) FROM content_scripts) AS scripts,
                (SELECT COUNT(*) FROM production_jobs WHERE status != 'FAILED') AS production,
                (SELECT COUNT(*) FROM publish_requests WHERE status = 'PUBLISHED') AS published,
                (SELECT COUNT(*) FROM video_metrics) AS analytics,
                (SELECT COUNT(*) FROM learning_signals) AS learning,
                (SELECT COUNT(*) FROM automation_jobs WHERE status IN ('QUEUED','RUNNING')) AS automation
            """,
        )
        return {key: counts[key] or 0 for key in counts.keys()}
    finally:
        connection.close()


@app.get("/api/dashboard/ideas")
def dashboard_ideas(limit: int = 20) -> list[dict[str, object]]:
    """Return ranked ideas for the dashboard."""
    limit = max(1, min(limit, 100))
    connection = get_connection()
    try:
        _prepare(connection)
        sql = "SELECT idea_id,title,topic,overall_score,status FROM content_ideas ORDER BY overall_score DESC,created_at ASC LIMIT :limit"
        if using_postgres():
            rows = connection.execute(text(sql), {"limit": limit}).mappings().all()
        else:
            rows = connection.execute(sql.replace(":limit", "?"), (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.post("/api/admin/bootstrap", dependencies=[Depends(require_api_token)])
def bootstrap_database() -> dict[str, str]:
    """Explicitly initialize the configured database schema."""
    connection = get_connection()
    try:
        _prepare(connection, bootstrap=True)
        return {"status": "initialized"}
    finally:
        connection.close()
