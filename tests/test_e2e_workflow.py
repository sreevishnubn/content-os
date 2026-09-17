from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4


def _seed_research(client, db_path, monkeypatch):
    from app.research.models import ResearchItem

    monkeypatch.setattr(
        "app.api.app.YouTubeRSSProvider.search",
        lambda self, query, limit=20: [
            ResearchItem(
                title="Test research story",
                summary="Evidence for the end-to-end workflow.",
                url="https://example.com/story",
                source_name="Test Source",
                published_at=datetime.now(timezone.utc),
                tags=["testing"],
            )
        ],
    )
    response = client.post(
        "/api/research/youtube",
        json={"channel_ids": ["UC-test"], "query": "testing", "limit": 1, "generate_ideas": True},
    )
    assert response.status_code == 200, response.text
    idea_id = response.json()["ideas"][0]["idea_id"]
    return idea_id


def _set_idea_status(client, idea_id, status):
    response = client.patch(
        f"/api/dashboard/ideas/{idea_id}/status", json={"status": status}
    )
    assert response.status_code == 200, response.text


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

    for status in ("ASSETS", "RENDERING"):
        response = client.patch(
            f"/api/dashboard/production/{production_id}/status",
            json={"status": status},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    artifact_response = client.post(
        f"/api/dashboard/production/{production_id}/artifact",
        json={"artifact_uri": "s3://contentos-test/rendered/test.mp4"},
    )
    assert artifact_response.status_code == 200, artifact_response.text

    response = client.patch(
        f"/api/dashboard/production/{production_id}/status",
        json={"status": "READY"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "READY"

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
        json={"status": "PUBLISHED", "external_id": "youtube-test-001"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"
    assert response.json()["external_id"] == "youtube-test-001"

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

    learning_response = client.post(f"/api/dashboard/analytics/analyze/{metric_id}")
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
        "/api/dashboard/publishing/missing/status", json={"status": "PUBLISHED", "external_id": "x"}
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

    response = client.post("/api/dashboard/analytics/analyze/missing")
    assert response.status_code == 404
