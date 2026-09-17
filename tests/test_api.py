from fastapi.testclient import TestClient

from app.api.app import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_overview_shape():
    client = TestClient(app)
    response = client.get("/api/dashboard/overview")
    assert response.status_code == 200
    assert set(response.json()) == {
        "research_items",
        "ideas",
        "approved",
        "published",
        "review",
    }
