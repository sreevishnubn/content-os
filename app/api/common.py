"""Shared API helpers that must not depend on route modules."""
from fastapi import Header, HTTPException
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.database.schema import initialize_postgres_schema, initialize_schema


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
    params = params or {}
    if using_postgres():
        return connection.execute(text(sql), params)
    converted = sql
    values = []
    for key, value in params.items():
        converted = converted.replace(f":{key}", "?")
        values.append(value)
    return connection.execute(converted, tuple(values))


def rows(connection, sql: str, params: dict | None = None):
    result = execute(connection, sql, params)
    return result.mappings().all() if using_postgres() else result.fetchall()


def one(connection, sql: str, params: dict | None = None):
    result = execute(connection, sql, params)
    return result.mappings().one() if using_postgres() else result.fetchone()
