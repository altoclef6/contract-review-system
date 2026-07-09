from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app


def _configure_stores(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("CONTRACT_DATA_DIR", str(tmp_path / "contracts"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login_admin(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin12345!"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_contract_lifecycle_and_versions(tmp_path: Path, monkeypatch) -> None:
    _configure_stores(monkeypatch, tmp_path)

    with TestClient(create_app()) as client:
        token = _login_admin(client)
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/api/v1/contracts",
            headers=headers,
            json={
                "title": "年度采购合同",
                "category": "procurement",
                "tags": ["重点", "采购", "采购"],
                "counterparty": "上海测试服务有限公司",
                "file_name": "purchase-v1.docx",
            },
        )
        assert create_response.status_code == 201
        assert create_response.json()["code"] == 0
        contract = create_response.json()["data"]
        contract_id = contract["id"]
        assert contract["tags"] == ["重点", "采购"]
        assert contract["status"] == "draft"
        assert contract["versions"][0]["version_no"] == 1

        list_response = client.get(
            "/api/v1/contracts?search=采购&category=procurement&page=1&page_size=5",
            headers=headers,
        )
        assert list_response.status_code == 200
        assert list_response.json()["data"]["total"] == 1

        favorite_response = client.post(
            f"/api/v1/contracts/{contract_id}/favorite?favorite=true",
            headers=headers,
        )
        assert favorite_response.status_code == 200
        assert favorite_response.json()["data"]["is_favorite"] is True

        version_response = client.post(
            f"/api/v1/contracts/{contract_id}/versions",
            headers=headers,
            json={
                "file_name": "purchase-v2.docx",
                "change_note": "补充付款节点",
                "review_id": "review_demo",
            },
        )
        assert version_response.status_code == 201
        assert version_response.json()["data"]["version_no"] == 2

        versions_response = client.get(f"/api/v1/contracts/{contract_id}/versions", headers=headers)
        assert versions_response.status_code == 200
        assert len(versions_response.json()["data"]) == 2

        archive_response = client.post(f"/api/v1/contracts/{contract_id}/archive", headers=headers)
        assert archive_response.status_code == 200
        assert archive_response.json()["data"]["status"] == "archived"

        delete_response = client.delete(f"/api/v1/contracts/{contract_id}", headers=headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["data"]["status"] == "deleted"

        hidden_response = client.get("/api/v1/contracts", headers=headers)
        assert hidden_response.status_code == 200
        assert hidden_response.json()["data"]["total"] == 0

        restore_response = client.post(f"/api/v1/contracts/{contract_id}/restore", headers=headers)
        assert restore_response.status_code == 200
        assert restore_response.json()["data"]["status"] == "draft"


def test_contracts_require_login(tmp_path: Path, monkeypatch) -> None:
    _configure_stores(monkeypatch, tmp_path)

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/contracts")
        assert response.status_code == 401
        assert response.json()["code"] == 40100
