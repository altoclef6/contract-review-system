
from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.services.knowledge_center_service import KnowledgeCenterService
from contract_review.services.rule_center_service import RuleCenterService


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("RULE_CENTER_DATA_DIR", str(tmp_path / "rules"))
    monkeypatch.setenv("KNOWLEDGE_CENTER_DATA_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_rule_permissions_updates_and_runtime_application(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin = _headers(_login(client, "admin@example.com", "Admin12345!"))
        created = client.post(
            "/api/v1/auth/register",
            json={
                "email": "employee@example.com",
                "password": "Employee12345!",
                "full_name": "Employee",
            },
        )
        employee = _headers(_login(client, "employee@example.com", "Employee12345!"))
        assert client.get("/api/v1/rules", headers=employee).status_code == 200
        assert (
            client.patch(
                "/api/v1/rules/R001", headers=employee, json={"enabled": False}
            ).status_code
            == 403
        )

        response = client.patch(
            "/api/v1/rules/R001",
            headers=admin,
            json={"enabled": False, "severity": "critical", "display_name": "主体核验"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["version"] == 2

    service = RuleCenterService(get_settings().rule_center_data_dir)
    registry = {item.rule_id: item for item in service.configured_registry("all")}
    assert registry["R001"].enabled is False
    assert registry["R001"].severity.value == "critical"
    assert registry["R002"].enabled is True
    assert created.status_code == 201


def test_knowledge_versions_effectivity_and_historical_access(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin = _headers(_login(client, "admin@example.com", "Admin12345!"))
        create_response = client.post(
            "/api/v1/knowledge",
            headers=admin,
            json={
                "document_id": "test-guidance-001",
                "title": "虚构测试审查指引",
                "article_number": "T-1",
                "content": "这是专用于自动化测试的合同付款风险资料。",
                "source_type": "test_data",
                "status": "effective",
                "issuing_authority": "测试夹具",
                "contract_types": ["technical_service"],
                "related_rule_ids": ["R008"],
            },
        )
        assert create_response.status_code == 201
        first = create_response.json()["data"]
        update_response = client.patch(
            f"/api/v1/knowledge/{first['id']}",
            headers=admin,
            json={"status": "expired", "content": "这是已失效的测试资料。"},
        )
        assert update_response.status_code == 200
        second = update_response.json()["data"]
        assert second["version"] == 2
        history = client.get(f"/api/v1/knowledge/{second['id']}/history", headers=admin)
        assert history.status_code == 200
        assert [item["version"] for item in history.json()["data"]] == [2, 1]
        assert client.get(f"/api/v1/knowledge/{first['id']}", headers=admin).status_code == 200

    service = KnowledgeCenterService(get_settings().knowledge_center_data_dir)
    assert all(
        item.document_id != "test-guidance-001" for item in service.retrieve({"付款"})
    )


def test_knowledge_roles_validation_and_xss_is_plain_data(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin = _headers(_login(client, "admin@example.com", "Admin12345!"))
        register = client.post(
            "/api/v1/auth/register",
            json={"email": "legal@example.com", "password": "Legal12345!", "full_name": "Legal"},
        )
        user_id = register.json()["data"]["id"]
        assert (
            client.patch(
                f"/api/v1/admin/users/{user_id}/role", headers=admin, json={"role": "legal"}
            ).status_code
            == 200
        )
        legal = _headers(_login(client, "legal@example.com", "Legal12345!"))
        xss = "<script>alert('x')</script>测试内容"
        created = client.post(
            "/api/v1/knowledge",
            headers=legal,
            json={
                "document_id": "test-xss-001",
                "title": "XSS 测试",
                "content": xss,
                "source_type": "test_data",
                "status": "draft",
            },
        )
        assert created.status_code == 201
        assert created.json()["data"]["content"] == xss
        invalid = client.post(
            "/api/v1/knowledge",
            headers=legal,
            json={
                "document_id": "bad-source",
                "title": "非法类型",
                "content": "测试",
                "source_type": "unknown",
            },
        )
        assert invalid.status_code == 422

        client.post(
            "/api/v1/auth/register",
            json={
                "email": "employee@example.com",
                "password": "Employee12345!",
                "full_name": "Employee",
            },
        )
        employee = _headers(_login(client, "employee@example.com", "Employee12345!"))
        assert client.get("/api/v1/knowledge", headers=employee).status_code == 200
        assert (
            client.post(
                "/api/v1/knowledge",
                headers=employee,
                json={
                    "document_id": "test-denied",
                    "title": "Denied",
                    "content": "Denied",
                    "source_type": "test_data",
                },
            ).status_code
            == 403
        )
