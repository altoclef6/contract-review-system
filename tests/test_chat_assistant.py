from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("CHAT_DATA_DIR", str(tmp_path / "chats"))
    monkeypatch.setenv("REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _register_and_login(client: TestClient, email: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Employee12345!", "full_name": email},
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Employee12345!"}
    )
    return response.json()["data"]["access_token"]


def test_chat_keeps_context_and_enforces_ownership(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)

    async def fake_call(system_prompt, messages, **kwargs):
        _ = system_prompt, kwargs
        return f"已结合上下文回答：{messages[-1][1]}"

    monkeypatch.setattr("contract_review.services.chat_service.call_llm_text", fake_call)
    with TestClient(create_app()) as client:
        first_token = _register_and_login(client, "first@example.com")
        second_token = _register_and_login(client, "second@example.com")
        first_headers = {"Authorization": f"Bearer {first_token}"}
        second_headers = {"Authorization": f"Bearer {second_token}"}

        created = client.post(
            "/api/v1/chats", headers=first_headers, json={"title": "采购合同追问"}
        )
        assert created.status_code == 201
        session_id = created.json()["data"]["id"]
        asked = client.post(
            f"/api/v1/chats/{session_id}/messages",
            headers=first_headers,
            json={"message": "解释违约责任"},
        )
        assert asked.status_code == 200
        data = asked.json()["data"]
        assert data["ai_available"] is True
        assert len(data["session"]["messages"]) == 2
        assert "解释违约责任" in data["answer"]["content"]

        forbidden = client.get(f"/api/v1/chats/{session_id}", headers=second_headers)
        assert forbidden.status_code == 404


def test_chat_reports_missing_model(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("ENABLE_LLM", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        token = _register_and_login(client, "employee@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/v1/chats", headers=headers, json={})
        session_id = created.json()["data"]["id"]
        asked = client.post(
            f"/api/v1/chats/{session_id}/messages",
            headers=headers,
            json={"message": "生成补充条款"},
        )
        assert asked.status_code == 200
        assert asked.json()["data"]["ai_available"] is False
        assert "模型配置中心" in asked.json()["data"]["answer"]["content"]
