from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.services.prompt_template_service import PromptTemplateService


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("PROMPT_TEMPLATE_DATA_DIR", str(tmp_path / "prompts"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_legal_user_manages_and_resolves_prompt(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin_token = _login(client, "admin@example.com", "Admin12345!")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        create_user = client.post(
            "/api/v1/auth/register",
            json={"email": "legal@example.com", "password": "Legal12345!", "full_name": "法务用户"},
        )
        user_id = create_user.json()["data"]["id"]
        role_response = client.patch(
            f"/api/v1/admin/users/{user_id}/role",
            headers=admin_headers,
            json={"role": "legal"},
        )
        assert role_response.status_code == 200
        legal_token = _login(client, "legal@example.com", "Legal12345!")
        headers = {"Authorization": f"Bearer {legal_token}"}

        response = client.post(
            "/api/v1/prompt-templates",
            headers=headers,
            json={
                "name": "采购合同合规模板",
                "contract_type": "purchase",
                "stage": "compliance",
                "system_prompt": "你是采购合同合规审查专家，请识别采购、验收、付款和供应商责任风险，并只输出 JSON。",
            },
        )
        assert response.status_code == 201
        template = response.json()["data"]
        template_id = template["id"]

        default_response = client.post(
            f"/api/v1/prompt-templates/{template_id}/default", headers=headers
        )
        assert default_response.status_code == 200
        assert default_response.json()["data"]["is_default"] is True

        update_response = client.patch(
            f"/api/v1/prompt-templates/{template_id}",
            headers=headers,
            json={"description": "采购合同专用", "system_prompt": template["system_prompt"] + " 严格核验。"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["data"]["version"] == 2

        list_response = client.get(
            "/api/v1/prompt-templates?contract_type=purchase&stage=compliance",
            headers=headers,
        )
        assert list_response.status_code == 200
        assert len(list_response.json()["data"]) == 1

    settings = get_settings()
    resolved = PromptTemplateService(settings.prompt_template_data_dir).resolve("purchase")
    assert "采购合同合规审查专家" in resolved["compliance"]
    assert resolved["extraction"]
    assert resolved["refinement"]


def test_employee_cannot_manage_prompts(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        client.post(
            "/api/v1/auth/register",
            json={"email": "employee@example.com", "password": "Employee12345!", "full_name": "普通员工"},
        )
        token = _login(client, "employee@example.com", "Employee12345!")
        response = client.get(
            "/api/v1/prompt-templates",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == 40300
