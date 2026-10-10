"""Phase 0.2: the backend starts and answers the documented health check."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_per_contract() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ok"}


def test_health_is_only_served_under_api_prefix() -> None:
    assert client.get("/health").status_code == 404
