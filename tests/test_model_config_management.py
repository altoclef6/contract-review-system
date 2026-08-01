from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.llm.json_client import call_llm_json
from contract_review.main import create_app
from contract_review.schemas.model_config import ModelConfigCreate
from contract_review.services.model_config_service import ModelConfigService


def _configure_stores(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("MODEL_CONFIG_DATA_DIR", str(tmp_path / "model-configs"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("MODEL_CREDENTIAL_ENCRYPTION_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_admin_model_config_lifecycle(tmp_path: Path, monkeypatch) -> None:
    _configure_stores(monkeypatch, tmp_path)

    with TestClient(create_app()) as client:
        token = _login(client, "admin@example.com", "Admin12345!")
        headers = {"Authorization": f"Bearer {token}"}

        providers_response = client.get("/api/v1/model-configs/providers", headers=headers)
        assert providers_response.status_code == 200
        providers = providers_response.json()["data"]
        assert {"openai", "deepseek", "claude", "gemini", "qwen"}.issubset(
            {item["provider"] for item in providers}
        )

        create_response = client.post(
            "/api/v1/model-configs",
            headers=headers,
            json={
                "name": "DeepSeek 主模型",
                "provider": "deepseek",
                "api_key": "sk-test-secret-value",
                "base_url": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat",
                "temperature": 0.2,
                "max_tokens": 4096,
            },
        )
        assert create_response.status_code == 201
        config = create_response.json()["data"]
        config_id = config["id"]
        assert config["api_key_masked"] == "sk-t...alue"
        assert "api_key" not in config
        assert config["is_active"] is True

        update_response = client.patch(
            f"/api/v1/model-configs/{config_id}",
            headers=headers,
            json={"model_name": "deepseek-reasoner", "temperature": 0.1},
        )
        assert update_response.status_code == 200
        assert update_response.json()["data"]["model_name"] == "deepseek-reasoner"

        active_response = client.get("/api/v1/model-configs/active", headers=headers)
        assert active_response.status_code == 200
        assert active_response.json()["data"]["config"]["id"] == config_id

        settings = get_settings()
        service = ModelConfigService(settings.model_config_data_dir, "test-secret")
        stored = service.path.read_text(encoding="utf-8")
        assert "sk-test-secret-value" not in stored
        assert "fernet:" in stored
        runtime = service.resolve_active_runtime_config()
        assert runtime is not None
        assert runtime.api_key == "sk-test-secret-value"
        assert runtime.model_name == "deepseek-reasoner"

        delete_response = client.delete(f"/api/v1/model-configs/{config_id}", headers=headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["data"]["id"] == config_id


def test_employee_cannot_manage_model_configs(tmp_path: Path, monkeypatch) -> None:
    _configure_stores(monkeypatch, tmp_path)

    with TestClient(create_app()) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "employee@example.com",
                "password": "Employee12345!",
                "full_name": "Employee User",
            },
        )
        assert register_response.status_code == 201
        token = _login(client, "employee@example.com", "Employee12345!")
        response = client.get(
            "/api/v1/model-configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == 40300


async def test_active_model_config_is_used_for_llm_calls(tmp_path: Path, monkeypatch) -> None:
    _configure_stores(monkeypatch, tmp_path)
    monkeypatch.setenv("ENABLE_LLM", "true")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    service = ModelConfigService(settings.model_config_data_dir, "test-secret")
    service.create(
        payload=ModelConfigCreate(
            name="DeepSeek 主模型",
            provider="deepseek",
            api_key="sk-active-config",
            base_url="https://api.deepseek.com/v1",
            model_name="deepseek-chat",
            temperature=0.2,
            max_tokens=2048,
            timeout_seconds=45,
        ),
        actor_id="user_admin",
    )

    captured: dict[str, object] = {}

    class FakeModel:
        async def ainvoke(self, messages):
            _ = messages
            return type("FakeResponse", (), {"content": '{"ok": true}'})()

    def fake_create_chat_model(settings_arg, llm_config):
        _ = settings_arg
        captured.update(llm_config)
        return FakeModel()

    monkeypatch.setattr("contract_review.llm.json_client.create_chat_model", fake_create_chat_model)

    result = await call_llm_json("system", "user")

    assert result == {"ok": True}
    assert captured["api_key"] == "sk-active-config"
    assert captured["model_name"] == "deepseek-chat"
    assert captured["max_tokens"] == 2048
    assert captured["timeout_seconds"] == 45
