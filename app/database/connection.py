"""Database connection boundary for ContentOS."""

import sqlite3
from pathlib import Path

from app.config.settings import get_settings


def get_connection():
    """Return a local SQLite connection or a PostgreSQL SQLAlchemy connection."""
    settings = get_settings()
    if settings.database_url:
        from sqlalchemy import create_engine
        return create_engine(settings.database_url, pool_pre_ping=True).connect()

    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def using_postgres() -> bool:
    return bool(get_settings().database_url)
