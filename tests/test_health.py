from fastapi.testclient import TestClient

from contract_review.main import create_app


def test_health_check() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "正常"}


def test_liveness_readiness_and_request_id() -> None:
    with TestClient(create_app()) as client:
        live = client.get("/api/v1/health/live", headers={"X-Request-ID": "release-check-1"})
        ready = client.get("/api/v1/health/ready")
    assert live.status_code == 200
    assert live.headers["X-Request-ID"] == "release-check-1"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
