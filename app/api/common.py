"""Shared API helpers that must not depend on route modules."""
import re

from fastapi import Header, HTTPException
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.database.schema import initialize_postgres_schema, initialize_schema


_NAMED_PARAMETER = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if settings.api_token and authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def prepare_database(connection) -> None:
    if using_postgres():
        initialize_postgres_schema(connection)
    else:
        initialize_schema(connection)


def execute(connection, sql: str, params: dict | None = None):
    """Execute SQL consistently across PostgreSQL and SQLite.

    SQLite does not understand SQLAlchemy-style named parameters in raw
    sqlite3 connections. Convert them in SQL occurrence order so repeated
    parameters and names that share prefixes remain correct.
    """
    params = params or {}
    if using_postgres():
        return connection.execute(text(sql), params)

    values = []

    def replace_parameter(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in params:
            raise ValueError(f"Missing SQL parameter: {key}")
        values.append(params[key])
        return "?"

    converted = _NAMED_PARAMETER.sub(replace_parameter, sql)
    return connection.execute(converted, tuple(values))


def rows(connection, sql: str, params: dict | None = None):
    result = execute(connection, sql, params)
    return result.mappings().all() if using_postgres() else result.fetchall()


def one(connection, sql: str, params: dict | None = None):
    result = execute(connection, sql, params)
    return result.mappings().one() if using_postgres() else result.fetchone()
