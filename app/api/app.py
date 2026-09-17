"""FastAPI application for the ContentOS operator dashboard."""

import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.database.schema import initialize_schema

app = FastAPI(title="ContentOS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sreevishnubn.github.io",
        "https://dashboard.youtube.analysis.com",
        "http://localhost:3000",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _connection() -> sqlite3.Connection:
    settings = get_settings()
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return connection


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "contentos-api"}


@app.get("/api/dashboard/overview")
def dashboard_overview() -> dict[str, object]:
    """Return live counts from the ContentOS database.

    This endpoint deliberately reads through the current V0 SQLite schema.
    Persistence can later move to PostgreSQL without changing the dashboard
    contract.
    """
    connection = _connection()
    try:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS ideas,
                SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'PUBLISHED' THEN 1 ELSE 0 END) AS published,
                SUM(CASE WHEN status IN ('SHORTLISTED', 'REVIEW') THEN 1 ELSE 0 END) AS review
            FROM content_ideas
            """
        ).fetchone()
        return {
            "research_items": 0,
            "ideas": row["ideas"] or 0,
            "approved": row["approved"] or 0,
            "published": row["published"] or 0,
            "review": row["review"] or 0,
        }
    finally:
        connection.close()
