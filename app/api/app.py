"""Production HTTP API for the ContentOS operator dashboard."""

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.database.schema import initialize_postgres_schema, initialize_schema

app = FastAPI(title="ContentOS API", version="1.0.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.api_token:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def _prepare(connection, *, bootstrap: bool = False) -> None:
    """Prepare a local DB automatically; require explicit bootstrap for Postgres."""
    if not bootstrap and using_postgres():
        return
    if using_postgres():
        initialize_postgres_schema(connection)
    else:
        initialize_schema(connection)


def _fetch_one(connection, sql: str):
    if using_postgres():
        return connection.execute(text(sql)).mappings().one()
    return connection.execute(sql).fetchone()


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "ContentOS API", "status": "online", "health": "/health"}


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
    """Explicitly initialize the configured production database schema."""
    connection = get_connection()
    try:
        _prepare(connection, bootstrap=True)
        return {"status": "initialized"}
    finally:
        connection.close()
