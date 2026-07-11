from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app


def _configure(monkeypatch, tmp_path: Path, rate_limit: int = 120) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", str(rate_limit))
    get_settings.cache_clear()


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin12345!"},
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_security_headers_monitoring_and_prometheus(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        health = client.get("/api/v1/health")
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "SAMEORIGIN"
        assert "x-process-time-ms" in health.headers
        headers = _admin_headers(client)
        status = client.get("/api/v1/monitoring/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["data"]["metrics"]["requests_total"] >= 1
        metrics = client.get("/api/v1/monitoring/metrics")
        assert metrics.status_code == 200
        assert "contract_review_requests_total" in metrics.text


def test_rate_limit_returns_unified_error(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path, rate_limit=1)
    with TestClient(create_app()) as client:
        first = client.get("/legacy")
        second = client.get("/legacy")
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["code"] == 42900
