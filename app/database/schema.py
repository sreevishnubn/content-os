"""SQLite schema management for ContentOS V0.1."""

import sqlite3


SCHEMA = """
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

CREATE INDEX IF NOT EXISTS idx_content_ideas_status
    ON content_ideas(status);

CREATE INDEX IF NOT EXISTS idx_content_ideas_score
    ON content_ideas(overall_score DESC);
"""


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create the ContentOS tables and indexes if they do not exist."""
    connection.executescript(SCHEMA)
    connection.commit()
