"""Database schema shared by local SQLite and production PostgreSQL."""

import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS content_ideas (
    idea_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    audience TEXT NOT NULL,
    hook TEXT NOT NULL,
    source TEXT,
    why_now TEXT,
    monetization_angle TEXT,
    demand REAL NOT NULL,
    curiosity REAL NOT NULL,
    competition REAL NOT NULL,
    monetization REAL NOT NULL,
    production REAL NOT NULL,
    overall_score REAL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_content_ideas_status ON content_ideas(status);
CREATE INDEX IF NOT EXISTS idx_content_ideas_score ON content_ideas(overall_score DESC);
"""


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Initialize the local SQLite database."""
    connection.executescript(SCHEMA_SQL)
    connection.commit()


POSTGRES_SCHEMA_SQL = SCHEMA_SQL.replace(
    "metadata_json TEXT NOT NULL", "metadata_json TEXT NOT NULL"
)


def initialize_postgres_schema(connection) -> None:
    """Initialize the production PostgreSQL database."""
    from sqlalchemy import text

    statements = [statement.strip() for statement in POSTGRES_SCHEMA_SQL.split(";") if statement.strip()]
    for statement in statements:
        connection.execute(text(statement))
    connection.commit()
