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
    """Protect mutating/admin endpoints when a production token is configured."""
    if not settings.api_token:
        return
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def _overview_sql() -> str:
    return """
        SELECT
            COUNT(*) AS ideas,
            SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = 'PUBLISHED' THEN 1 ELSE 0 END) AS published,
            SUM(CASE WHEN status IN ('SHORTLISTED', 'REVIEW') THEN 1 ELSE 0 END) AS review
        FROM content_ideas
    """


@app.get("/health")
def health() -> dict[str, object]:
    """Liveness/readiness endpoint."""
    connection = get_connection()
    try:
        if using_postgres():
            connection.execute(text("SELECT 1"))
        else:
            initialize_schema(connection)
        return {"status": "ok", "service": "contentos-api", "database": "postgres" if using_postgres() else "sqlite"}
    finally:
        connection.close()


@app.get("/api/dashboard/overview")
def dashboard_overview() -> dict[str, object]:
    """Return live workflow counts from the configured database."""
    connection = get_connection()
    try:
        if using_postgres():
            initialize_postgres_schema(connection)
            row = connection.execute(text(_overview_sql())).mappings().one()
            return {
                "research_items": 0,
                "ideas": row["ideas"] or 0,
                "approved": row["approved"] or 0,
                "published": row["published"] or 0,
                "review": row["review"] or 0,
            }
        initialize_schema(connection)
        row = connection.execute(_overview_sql()).fetchone()
        return {
            "research_items": 0,
            "ideas": row["ideas"] or 0,
            "approved": row["approved"] or 0,
            "published": row["published"] or 0,
            "review": row["review"] or 0,
        }
    finally:
        connection.close()


@app.get("/api/dashboard/ideas")
def dashboard_ideas(limit: int = 20) -> list[dict[str, object]]:
    """Return ranked ideas for the dashboard."""
    limit = max(1, min(limit, 100))
    connection = get_connection()
    try:
        sql = "SELECT idea_id,title,topic,overall_score,status FROM content_ideas ORDER BY overall_score DESC,created_at ASC LIMIT :limit"
        if using_postgres():
            initialize_postgres_schema(connection)
            rows = connection.execute(text(sql), {"limit": limit}).mappings().all()
            return [dict(row) for row in rows]
        initialize_schema(connection)
        rows = connection.execute(sql.replace(":limit", "?"), (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.post("/api/admin/bootstrap", dependencies=[Depends(require_api_token)])
def bootstrap_database() -> dict[str, str]:
    """Explicitly initialize the production schema once credentials are configured."""
    connection = get_connection()
    try:
        if using_postgres():
            initialize_postgres_schema(connection)
        else:
            initialize_schema(connection)
        return {"status": "initialized"}
    finally:
        connection.close()
