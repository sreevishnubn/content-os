import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings


@pytest.fixture
def workflow_client(tmp_path, monkeypatch):
    db_path = tmp_path / "workflow.db"
    monkeypatch.setenv("CONTENTOS_DATABASE_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CONTENTOS_API_TOKEN", raising=False)
    get_settings.cache_clear()

    from app.api.app import app

    client = TestClient(app)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    from app.database.schema import initialize_schema
    initialize_schema(connection)
    connection.commit()
    connection.close()
    yield client
    get_settings.cache_clear()


def seed_idea(db_path, status="REVIEW"):
    idea_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(db_path)
    connection.execute(
        """INSERT INTO content_ideas
        (idea_id,title,topic,audience,hook,source,why_now,monetization_angle,
         demand,curiosity,competition,monetization,production,overall_score,status,
         metadata_json,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (idea_id, "Test opportunity", "Test topic", "Test audience", "Test hook", "https://example.com/source", "Test evidence", "Test angle", 8, 8, 7, 6, 9, 7.5, status, json.dumps({"test": True}), now),
    )
    connection.commit()
    connection.close()
    return idea_id


def test_unapproved_idea_cannot_create_script(workflow_client, tmp_path):
    idea_id = seed_idea(tmp_path / "workflow.db", status="REVIEW")
    response = workflow_client.post("/api/dashboard/scripts/draft", json={"idea_id": idea_id})
    assert response.status_code == 409
    assert "Only APPROVED ideas" in response.json()["detail"]


def test_approved_idea_can_create_script_and_enters_scripting(workflow_client, tmp_path):
    idea_id = seed_idea(tmp_path / "workflow.db", status="APPROVED")
    response = workflow_client.post("/api/dashboard/scripts/draft", json={"idea_id": idea_id})
    assert response.status_code == 200
    assert response.json()["version"] == 1
    connection = sqlite3.connect(tmp_path / "workflow.db")
    status = connection.execute("SELECT status FROM content_ideas WHERE idea_id=?", (idea_id,)).fetchone()[0]
    connection.close()
    assert status == "SCRIPTING"


def test_invalid_idea_transition_is_rejected(workflow_client, tmp_path):
    idea_id = seed_idea(tmp_path / "workflow.db", status="REVIEW")
    response = workflow_client.patch(f"/api/dashboard/ideas/{idea_id}/status", json={"status": "PUBLISHED"})
    assert response.status_code == 409
    assert "Invalid idea transition" in response.json()["detail"]


def test_nonexistent_production_status_returns_404(workflow_client):
    response = workflow_client.patch("/api/dashboard/production/not-a-real-job/status", json={"status": "READY"})
    assert response.status_code == 404
    assert "production_jobs record not found" == response.json()["detail"]


def test_production_state_machine_rejects_skipping_states(workflow_client, tmp_path):
    idea_id = seed_idea(tmp_path / "workflow.db", status="APPROVED")
    script = workflow_client.post("/api/dashboard/scripts/draft", json={"idea_id": idea_id})
    production = workflow_client.post("/api/dashboard/production", json={"script_id": script.json()["script_id"]})
    production_id = production.json()["production_id"]
    response = workflow_client.patch(f"/api/dashboard/production/{production_id}/status", json={"status": "READY"})
    assert response.status_code == 409
    assert "QUEUED -> READY" in response.json()["detail"]


def test_production_requires_artifact_before_ready(workflow_client, tmp_path):
    idea_id = seed_idea(tmp_path / "workflow.db", status="APPROVED")
    script = workflow_client.post("/api/dashboard/scripts/draft", json={"idea_id": idea_id})
    production = workflow_client.post("/api/dashboard/production", json={"script_id": script.json()["script_id"]})
    production_id = production.json()["production_id"]
    workflow_client.patch(f"/api/dashboard/production/{production_id}/status", json={"status": "ASSETS"})
    workflow_client.patch(f"/api/dashboard/production/{production_id}/status", json={"status": "RENDERING"})
    response = workflow_client.patch(f"/api/dashboard/production/{production_id}/status", json={"status": "READY"})
    assert response.status_code == 409
    assert "artifact is registered" in response.json()["detail"]
    artifact = workflow_client.post(f"/api/dashboard/production/{production_id}/artifact", json={"artifact_uri": "s3://contentos/test.mp4"})
    assert artifact.status_code == 200
    ready = workflow_client.patch(f"/api/dashboard/production/{production_id}/status", json={"status": "READY"})
    assert ready.status_code == 200


def test_publish_requires_ready_production(workflow_client, tmp_path):
    idea_id = seed_idea(tmp_path / "workflow.db", status="APPROVED")
    script = workflow_client.post("/api/dashboard/scripts/draft", json={"idea_id": idea_id})
    production = workflow_client.post("/api/dashboard/production", json={"script_id": script.json()["script_id"]})
    response = workflow_client.post("/api/dashboard/publishing", json={"production_id": production.json()["production_id"], "title": "Test publication", "description": "Test", "tags": ["test"]})
    assert response.status_code == 409
    assert "Only READY production jobs with an artifact" in response.json()["detail"]


def test_published_requires_external_video_id(workflow_client, tmp_path):
    idea_id = seed_idea(tmp_path / "workflow.db", status="APPROVED")
    script = workflow_client.post("/api/dashboard/scripts/draft", json={"idea_id": idea_id})
    production = workflow_client.post("/api/dashboard/production", json={"script_id": script.json()["script_id"]})
    production_id = production.json()["production_id"]
    for status in ("ASSETS", "RENDERING"):
        assert workflow_client.patch(f"/api/dashboard/production/{production_id}/status", json={"status": status}).status_code == 200
    assert workflow_client.post(f"/api/dashboard/production/{production_id}/artifact", json={"artifact_uri": "s3://contentos/test.mp4"}).status_code == 200
    assert workflow_client.patch(f"/api/dashboard/production/{production_id}/status", json={"status": "READY"}).status_code == 200
    publish = workflow_client.post("/api/dashboard/publishing", json={"production_id": production_id, "title": "Test publication"})
    publish_id = publish.json()["publish_id"]
    workflow_client.patch(f"/api/dashboard/publishing/{publish_id}/status", json={"status": "SCHEDULED"})
    response = workflow_client.patch(f"/api/dashboard/publishing/{publish_id}/status", json={"status": "PUBLISHED"})
    assert response.status_code == 409
    assert "external YouTube video ID" in response.json()["detail"]
