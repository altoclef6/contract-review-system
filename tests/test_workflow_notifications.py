from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path / "workflows"))
    monkeypatch.setenv("NOTIFICATION_DATA_DIR", str(tmp_path / "notifications"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["access_token"]


def test_contract_approval_workflow_and_notifications(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin_token = _login(client, "admin@example.com", "Admin12345!")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "employee@example.com",
                "password": "Employee12345!",
                "full_name": "业务员工",
            },
        )
        legal = client.post(
            "/api/v1/auth/register",
            json={
                "email": "legal@example.com",
                "password": "Legal12345!",
                "full_name": "法务人员",
            },
        ).json()["data"]
        client.patch(
            f"/api/v1/admin/users/{legal['id']}/role",
            headers=admin_headers,
            json={"role": "legal"},
        )
        employee_headers = {
            "Authorization": f"Bearer {_login(client, 'employee@example.com', 'Employee12345!')}"
        }
        legal_headers = {
            "Authorization": f"Bearer {_login(client, 'legal@example.com', 'Legal12345!')}"
        }

        created = client.post(
            "/api/v1/workflows",
            headers=employee_headers,
            json={"contract_id": "contract_demo", "review_id": "review_demo"},
        )
        assert created.status_code == 201
        workflow_id = created.json()["data"]["id"]

        def act(headers, action):
            return client.post(
                f"/api/v1/workflows/{workflow_id}/actions",
                headers=headers,
                json={"action": action},
            )

        assert (
            act(employee_headers, "start_ai_review").json()["data"]["current_step"] == "ai_review"
        )
        denied = act(employee_headers, "ai_completed")
        assert denied.status_code == 409
        assert act(legal_headers, "ai_completed").json()["data"]["current_step"] == "legal_review"
        assert act(legal_headers, "approve").json()["data"]["current_step"] == "manager_review"
        completed = act(admin_headers, "approve")
        assert completed.json()["data"]["current_step"] == "archived"
        assert completed.json()["data"]["status"] == "completed"

        notifications = client.get("/api/v1/notifications", headers=employee_headers)
        assert notifications.status_code == 200
        assert notifications.json()["data"]["unread_count"] == 4
        assert notifications.json()["data"]["total"] == 4

        read_all = client.post("/api/v1/notifications/read-all", headers=employee_headers)
        assert read_all.status_code == 200
        after = client.get("/api/v1/notifications", headers=employee_headers)
        assert after.json()["data"]["unread_count"] == 0


def test_employee_cannot_access_another_workflow(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        headers = []
        for index in range(2):
            email = f"employee{index}@example.com"
            client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Employee12345!", "full_name": email},
            )
            headers.append({"Authorization": f"Bearer {_login(client, email, 'Employee12345!')}"})
        created = client.post(
            "/api/v1/workflows", headers=headers[0], json={"contract_id": "contract_private"}
        )
        workflow_id = created.json()["data"]["id"]
        assert client.get(f"/api/v1/workflows/{workflow_id}", headers=headers[1]).status_code == 404
        assert (
            client.post(
                f"/api/v1/workflows/{workflow_id}/actions",
                headers=headers[1],
                json={"action": "start_ai_review"},
            ).status_code
            == 409
        )
