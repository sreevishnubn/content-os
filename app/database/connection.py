"""Database connection boundary for ContentOS."""

import sqlite3
from pathlib import Path

from app.config.settings import get_settings


def _postgres_url(url: str) -> str:
    """Normalize common PostgreSQL URLs to SQLAlchemy's psycopg v3 driver."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def get_connection():
    """Return a local SQLite connection or a PostgreSQL SQLAlchemy connection."""
    settings = get_settings()
    if settings.database_url:
        from sqlalchemy import create_engine

        return create_engine(
            _postgres_url(settings.database_url),
            pool_pre_ping=True,
        ).connect()

    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def using_postgres() -> bool:
    return bool(get_settings().database_url)
