"""Persistence boundary for normalized research evidence."""

import json
import sqlite3
import uuid

from app.research.models import ResearchItem


class ResearchRepository:
    """Store research items in either SQLite or SQLAlchemy-backed PostgreSQL."""

    def __init__(self, connection, *, postgres: bool = False) -> None:
        self.connection = connection
        self.postgres = postgres

    def save_many(self, items: list[ResearchItem]) -> list[ResearchItem]:
        """Insert research items, ignoring duplicate URLs."""
        if self.postgres:
            from sqlalchemy import text

            for item in items:
                self.connection.execute(
                    text(
                        """INSERT INTO research_items
                        (research_id,title,summary,url,source_name,published_at,discovered_at,tags_json)
                        VALUES (:id,:title,:summary,:url,:source,:published,:discovered,:tags)
                        ON CONFLICT (url) DO NOTHING"""
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "title": item.title,
                        "summary": item.summary,
                        "url": str(item.url) if item.url else None,
                        "source": item.source_name,
                        "published": item.published_at,
                        "discovered": item.discovered_at,
                        "tags": json.dumps(item.tags),
                    },
                )
            self.connection.commit()
            return items

        for item in items:
            self.connection.execute(
                """INSERT OR IGNORE INTO research_items
                (research_id,title,summary,url,source_name,published_at,discovered_at,tags_json)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4()), item.title, item.summary,
                    str(item.url) if item.url else None, item.source_name,
                    item.published_at.isoformat() if item.published_at else None,
                    item.discovered_at.isoformat(), json.dumps(item.tags),
                ),
            )
        self.connection.commit()
        return items
