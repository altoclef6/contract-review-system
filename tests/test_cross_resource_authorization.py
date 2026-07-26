from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.services.history_service import HistoryService, build_history_item


def _register_and_login(client: TestClient, email: str) -> tuple[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Employee12345!", "full_name": email},
    ).json()["data"]
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Employee12345!"},
    ).json()["data"]["access_token"]
    return registered["id"], token


def test_employee_cannot_bind_another_users_review_or_start_their_workflow() -> None:
    with TestClient(create_app()) as client:
        owner_id, owner_token = _register_and_login(client, "owner@example.com")
        _, attacker_token = _register_and_login(client, "attacker@example.com")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

        contract = client.post(
            "/api/v1/contracts",
            headers=owner_headers,
            json={"title": "Owner contract", "category": "other"},
        ).json()["data"]
        HistoryService(get_settings().report_dir.parent).append(
            build_history_item(
                review_id="review_owner_only",
                file_name="owner.pdf",
                final_report={},
                report_path=None,
                exports={},
                created_by=owner_id,
                contract_id=contract["id"],
            )
        )

        chat = client.post(
            "/api/v1/chats",
            headers=attacker_headers,
            json={"review_id": "review_owner_only"},
        )
        assert chat.status_code == 404

        workflow = client.post(
            "/api/v1/workflows",
            headers=attacker_headers,
            json={"contract_id": contract["id"], "review_id": "review_owner_only"},
        )
        assert workflow.status_code == 404

        owner_workflow = client.post(
            "/api/v1/workflows",
            headers=owner_headers,
            json={"contract_id": contract["id"], "review_id": "review_owner_only"},
        )
        assert owner_workflow.status_code == 201
