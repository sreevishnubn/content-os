"""Persistence boundary for ContentOS content ideas."""

import json
import sqlite3
from datetime import datetime

from app.database.models import ContentIdea, IdeaScores, IdeaStatus


class IdeaRepository:
    """Store and retrieve ContentIdea objects without exposing SQL to callers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save(self, idea: ContentIdea) -> ContentIdea:
        """Insert or replace one idea using its stable idea_id."""
        self.connection.execute(
            """
            INSERT OR REPLACE INTO content_ideas (
                idea_id, title, topic, audience, hook, source, why_now,
                monetization_angle, demand, curiosity, competition,
                monetization, production, overall_score, status,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idea.idea_id,
                idea.title,
                idea.topic,
                idea.audience,
                idea.hook,
                idea.source,
                idea.why_now,
                idea.monetization_angle,
                idea.scores.demand,
                idea.scores.curiosity,
                idea.scores.competition,
                idea.scores.monetization,
                idea.scores.production,
                idea.overall_score,
                idea.status.value,
                json.dumps(idea.metadata, sort_keys=True),
                idea.created_at.isoformat(),
            ),
        )
        self.connection.commit()
        return idea

    def save_many(self, ideas: list[ContentIdea]) -> list[ContentIdea]:
        """Persist a batch atomically."""
        for idea in ideas:
            self.save(idea)
        return ideas

    def get(self, idea_id: str) -> ContentIdea | None:
        """Return one idea by ID, or None when it does not exist."""
        row = self.connection.execute(
            "SELECT * FROM content_ideas WHERE idea_id = ?", (idea_id,)
        ).fetchone()
        return self._from_row(row) if row else None

    def list(self, *, status: IdeaStatus | None = None) -> list[ContentIdea]:
        """Return ideas ordered by score, optionally filtered by status."""
        if status is None:
            rows = self.connection.execute(
                "SELECT * FROM content_ideas ORDER BY overall_score DESC, created_at DESC"
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM content_ideas
                WHERE status = ?
                ORDER BY overall_score DESC, created_at DESC
                """,
                (status.value,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_status(self, idea_id: str, status: IdeaStatus) -> ContentIdea | None:
        """Update one idea's workflow status and return the updated idea."""
        cursor = self.connection.execute(
            "UPDATE content_ideas SET status = ? WHERE idea_id = ?",
            (status.value, idea_id),
        )
        self.connection.commit()
        if cursor.rowcount == 0:
            return None
        return self.get(idea_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ContentIdea:
        """Reconstruct a validated ContentIdea from a database row."""
        return ContentIdea(
            idea_id=row["idea_id"],
            title=row["title"],
            topic=row["topic"],
            audience=row["audience"],
            hook=row["hook"],
            source=row["source"],
            why_now=row["why_now"],
            monetization_angle=row["monetization_angle"],
            scores=IdeaScores(
                demand=row["demand"],
                curiosity=row["curiosity"],
                competition=row["competition"],
                monetization=row["monetization"],
                production=row["production"],
            ),
            overall_score=row["overall_score"],
            status=IdeaStatus(row["status"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
