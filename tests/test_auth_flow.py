from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app


def _configure_security_store(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def test_register_login_refresh_and_change_password(tmp_path: Path, monkeypatch) -> None:
    _configure_security_store(monkeypatch, tmp_path)

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
        assert register_response.json()["code"] == 0
        assert register_response.json()["data"]["role"] == "employee"

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "employee@example.com", "password": "Employee12345!"},
        )
        assert login_response.status_code == 200
        token_payload = login_response.json()["data"]
        access_token = token_payload["access_token"]
        refresh_token = token_payload["refresh_token"]

        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["data"]["email"] == "employee@example.com"

        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 200
        assert refresh_response.json()["data"]["access_token"]

        change_response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"old_password": "Employee12345!", "new_password": "Employee67890!"},
        )
        assert change_response.status_code == 200

        revoked_access = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert revoked_access.status_code == 401
        revoked_refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert revoked_refresh.status_code == 401

        old_login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "employee@example.com", "password": "Employee12345!"},
        )
        assert old_login_response.status_code == 401
        assert old_login_response.json()["code"] == 40100


def test_admin_rbac_user_management(tmp_path: Path, monkeypatch) -> None:
    _configure_security_store(monkeypatch, tmp_path)

    with TestClient(create_app()) as client:
        employee_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "viewer@example.com",
                "password": "Employee12345!",
                "full_name": "Viewer User",
            },
        )
        employee_id = employee_response.json()["data"]["id"]
        employee_login = client.post(
            "/api/v1/auth/login",
            json={"email": "viewer@example.com", "password": "Employee12345!"},
        )
        employee_token = employee_login.json()["data"]["access_token"]

        denied_response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert denied_response.status_code == 403
        assert denied_response.json()["code"] == 40300

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "Admin12345!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["data"]["access_token"]

        users_response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert users_response.status_code == 200
        assert len(users_response.json()["data"]) == 2

        audit_response = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert audit_response.status_code == 200
        assert any(item["action"] == "auth.login" for item in audit_response.json()["data"])

        denied_audit_response = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert denied_audit_response.status_code == 403

        disabled_response = client.patch(
            f"/api/v1/admin/users/{employee_id}/disabled",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"disabled": True},
        )
        assert disabled_response.status_code == 200
        assert disabled_response.json()["data"]["is_active"] is False

        reset_response = client.post(
            f"/api/v1/admin/users/{employee_id}/reset-password",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert reset_response.status_code == 200
        assert reset_response.json()["data"]["temporary_password"].startswith("Temp-")
