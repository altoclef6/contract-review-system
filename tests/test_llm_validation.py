from fastapi.testclient import TestClient

from pathlib import Path

from contract_review.core.config import get_settings
from contract_review.main import create_app


def test_llm_validate_requires_valid_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    monkeypatch.setenv("ENABLE_LLM", "true")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "Admin12345!"},
        )
        token = login_response.json()["data"]["access_token"]
        response = client.post(
            "/api/v1/llm/validate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "deepseek",
                "api_key": "invalid-key",
                "model_name": "deepseek-chat",
                "base_url": "https://api.deepseek.com/v1",
            },
        )

    assert response.status_code == 400
    assert "验证失败" in response.json()["detail"]
