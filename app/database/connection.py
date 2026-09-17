import sqlite3
from pathlib import Path

from app.config.settings import get_settings


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection and create the data directory if needed."""
    settings = get_settings()
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection
