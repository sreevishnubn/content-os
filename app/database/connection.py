"""Database connection boundary.

SQLite remains the local development default. Production uses PostgreSQL via
DATABASE_URL, keeping the rest of the application independent of the driver.
"""

import sqlite3
from pathlib import Path

from app.config.settings import get_settings


def get_connection():
    settings = get_settings()
    if settings.database_url:
        from sqlalchemy import create_engine
        return create_engine(settings.database_url, pool_pre_ping=True).connect()

    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection
