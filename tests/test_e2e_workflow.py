import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.database.schema import initialize_schema
from app.research.models import ResearchItem


@pytest.fixture
def e2e_client(tmp_path, monkeypatch):
    db_path = tmp_path / "e2e.db"
    monkeypatch.setenv("CONTENTOS_DATABASE_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CONTENTOS_API_TOKEN", raising=False)
    get_settings.cache_clear()

    from app.api.app import app

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    connection.commit()
    connection.close()
    yield TestClient(app), db_path
    get_settings.cache_clear()


def _seed_research(client, db_path, monkeypatch):
    item = ResearchItem(
        title="Test research opportunity",
        summary="Evidence-backed test research for the end-to-end workflow.",
        url="https://example.com/research",
        source_name="Test Source",
        published_at=datetime.now(timezone.utc),
        tags=["testing"],
    )

    from app.api import app as api_module

    class FakeProvider:
        name = "fake"

        def __init__(self, channel_ids):
            self.channel_ids = channel_ids

        def search(self, query, limit=20):
            return [item]

    monkeypatch.setattr(api_module, "resolve_channel_ids", lambda sources: ["UC12345678901234567890"])
    monkeypatch.setattr(api_module, "YouTubeRSSProvider", FakeProvider)

    response = client.post(
        "/api/research/youtube",
        json={
            "channel_ids": ["@test"],
            "query": "test",
            "limit": 10,
            "generate_ideas": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["research_items_found"] == 1
    assert body["ideas_created"] == 3
    assert body["ideas"][0]["overall_score"] == 0
    return body["ideas"][0]["idea_id"]


def _set_idea_status(client, idea_id, status):
    response = client.patch(
        f"/api/dashboard/ideas/{idea_id}/status",
        json={"status": status},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == status


def test_complete_content_workflow(e2e_client, monkeypatch):
    client, db_path = e2e_client
    idea_id = _seed_research(client, db_path, monkeypatch)

    _set_idea_status(client, idea_id, "SHORTLISTED")
    _set_idea_status(client, idea_id, "REVIEW")
    _set_idea_status(client, idea_id, "APPROVED")

    script_response = client.post(
        "/api/dashboard/scripts/draft", json={"idea_id": idea_id}
    )
    assert script_response.status_code == 200, script_response.text
    script = script_response.json()
    assert script["version"] == 1
    assert len(script["sections"]) == 4

    _set_idea_status(client, idea_id, "PRODUCTION")

    production_response = client.post(
        "/api/dashboard/production", json={"script_id": script["script_id"]}
    )
    assert production_response.status_code == 200, production_response.text
    production_id = production_response.json()["production_id"]
    assert production_response.json()["status"] == "QUEUED"

    for status in ("ASSETS", "RENDERING", "READY"):
        response = client.patch(
            f"/api/dashboard/production/{production_id}/status",
            json={"status": status},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    publish_response = client.post(
        "/api/dashboard/publishing",
        json={
            "production_id": production_id,
            "title": "Test publication",
            "description": "End-to-end test",
            "tags": ["testing", "contentos"],
        },
    )
    assert publish_response.status_code == 200, publish_response.text
    publish_id = publish_response.json()["publish_id"]

    response = client.patch(
        f"/api/dashboard/publishing/{publish_id}/status",
        json={"status": "SCHEDULED"},
    )
    assert response.status_code == 200
    response = client.patch(
        f"/api/dashboard/publishing/{publish_id}/status",
        json={"status": "PUBLISHED"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"

    metrics_response = client.post(
        "/api/dashboard/analytics",
        json={
            "external_video_id": "video-e2e-1",
            "views": 1000,
            "watch_time_minutes": 250,
            "average_view_duration_seconds": 15,
            "impressions": 5000,
            "click_through_rate": 8.5,
            "likes": 80,
            "comments": 12,
            "subscribers_gained": 25,
            "revenue": 4.25,
        },
    )
    assert metrics_response.status_code == 200, metrics_response.text
    metric_id = metrics_response.json()["metric_id"]

    learning_response = client.post(
        f"/api/dashboard/analytics/analyze/{metric_id}"
    )
    assert learning_response.status_code == 200, learning_response.text
    signals = learning_response.json()["signals"]
    assert signals
    assert all(0 <= signal["confidence"] <= 1 for signal in signals)

    learning_list = client.get("/api/dashboard/learning")
    assert learning_list.status_code == 200
    assert len(learning_list.json()) >= len(signals)

    overview = client.get("/api/dashboard/overview")
    assert overview.status_code == 200
    counts = overview.json()
    assert counts["research_items"] == 1
    assert counts["ideas"] == 3
    assert counts["scripts"] == 1
    assert counts["production"] == 1
    assert counts["published"] == 1
    assert counts["analytics"] == 1
    assert counts["learning"] >= len(signals)

    connection = sqlite3.connect(db_path)
    status = connection.execute(
        "SELECT status FROM content_ideas WHERE idea_id=?", (idea_id,)
    ).fetchone()[0]
    connection.close()
    assert status == "PRODUCTION"


def test_workflow_rejects_invalid_transitions_and_missing_records(e2e_client, monkeypatch):
    client, db_path = e2e_client
    idea_id = _seed_research(client, db_path, monkeypatch)

    response = client.patch(
        f"/api/dashboard/ideas/{idea_id}/status", json={"status": "PUBLISHED"}
    )
    assert response.status_code == 409

    response = client.patch(
        "/api/dashboard/production/missing/status", json={"status": "READY"}
    )
    assert response.status_code == 404

    response = client.patch(
        "/api/dashboard/publishing/missing/status", json={"status": "PUBLISHED"}
    )
    assert response.status_code == 404

    response = client.patch(
        "/api/dashboard/automation/missing/status", json={"status": "SUCCEEDED"}
    )
    assert response.status_code == 404

    response = client.post(
        "/api/dashboard/analytics",
        json={"external_video_id": "bad", "views": -1},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/dashboard/analytics",
        json={"external_video_id": "bad", "click_through_rate": 101},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/dashboard/analytics/analyze/missing"
    )
    assert response.status_code == 404

    response = client.post(
        "/api/dashboard/scripts/draft", json={"idea_id": str(uuid4())}
    )
    assert response.status_code == 404

    response = client.post(
        "/api/dashboard/production", json={"script_id": str(uuid4())}
    )
    assert response.status_code == 404

    response = client.post(
        "/api/dashboard/publishing",
        json={
            "production_id": str(uuid4()),
            "title": "Missing production",
        },
    )
    assert response.status_code == 404

    connection = sqlite3.connect(db_path)
    assert connection.execute("SELECT COUNT(*) FROM research_items").fetchone()[0] == 1
    connection.close()
