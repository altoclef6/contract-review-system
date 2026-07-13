from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.schemas.auth import UserPublic, UserRole
from contract_review.services.dashboard_service import DashboardService
from contract_review.services.history_service import HistoryService
from contract_review.services.notification_service import NotificationService
from contract_review.services.workflow_service import WorkflowService


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path / "workflows"))
    monkeypatch.setenv("NOTIFICATION_DATA_DIR", str(tmp_path / "notifications"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _record(
    *,
    review_id: str,
    owner_id: str | None,
    created_at: datetime,
    risk_level: str = "低风险",
    duration_ms: int | None = 1000,
    contract_type: str = "general",
    rule_counts_complete: bool = True,
) -> dict:
    return {
        "review_id": review_id,
        "file_name": f"{review_id}.docx",
        "created_at": created_at.isoformat(),
        "contract_type": contract_type,
        "duration_ms": duration_ms,
        "created_by": owner_id,
        "overall_risk_level": risk_level,
        "risk_score": 20,
        "risk_counts": {},
        "rule_counts": [{"rule_id": "R008", "title": "缺少付款节点", "count": 1}],
        "rule_counts_complete": rule_counts_complete,
        "exports": {},
    }


def _actor(user_id: str, role: UserRole) -> UserPublic:
    now = datetime.now(timezone.utc)
    return UserPublic(
        id=user_id,
        email=f"{user_id}@example.com",
        full_name=user_id,
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _service(tmp_path: Path) -> DashboardService:
    return DashboardService(
        HistoryService(tmp_path),
        WorkflowService(tmp_path / "workflows", NotificationService(tmp_path / "notifications")),
    )


def test_dashboard_empty_data_returns_safe_nulls(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        payload = client.get(
            "/api/v1/dashboard/summary",
            headers=_login(client, "admin@example.com", "Admin12345!"),
        ).json()["data"]
    assert payload["metrics"]["monthly_review_count"] == 0
    assert payload["metrics"]["monthly_high_risk_contract_count"] == 0
    assert payload["metrics"]["pending_human_review_risk_count"] is None
    assert payload["metrics"]["average_review_duration_ms"] is None
    assert len(payload["review_trend_30d"]) == 30
    assert payload["risk_level_distribution"] == []
    assert payload["top_risk_rules"] == []


def test_dashboard_employee_isolation_and_admin_scope(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        users = []
        for index in range(2):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"employee{index}@example.com",
                    "password": "Employee12345!",
                    "full_name": f"员工{index}",
                },
            )
            users.append(response.json()["data"])
        now = datetime.now(timezone.utc)
        history = HistoryService(tmp_path)
        history.append(_record(review_id="owned", owner_id=users[0]["id"], created_at=now))
        history.append(
            _record(
                review_id="other",
                owner_id=users[1]["id"],
                created_at=now,
                risk_level="高风险",
            )
        )
        employee0_headers = _login(client, "employee0@example.com", "Employee12345!")
        employee1_headers = _login(client, "employee1@example.com", "Employee12345!")
        client.post(
            "/api/v1/workflows",
            headers=employee0_headers,
            json={"contract_id": "contract_owned"},
        )
        client.post(
            "/api/v1/workflows",
            headers=employee1_headers,
            json={"contract_id": "contract_other"},
        )
        employee = client.get(
            "/api/v1/dashboard/summary",
            headers=employee0_headers,
        )
        admin = client.get(
            "/api/v1/dashboard/summary",
            headers=_login(client, "admin@example.com", "Admin12345!"),
        )
    assert employee.status_code == 200
    assert employee.json()["data"]["scope"] == "owned"
    assert employee.json()["data"]["metrics"]["monthly_review_count"] == 1
    assert [item["review_id"] for item in employee.json()["data"]["recent_tasks"]] == ["owned"]
    assert len(employee.json()["data"]["todos"]) == 1
    assert "contract_owned" in employee.json()["data"]["todos"][0]["description"]
    assert admin.json()["data"]["scope"] == "all"
    assert admin.json()["data"]["metrics"]["monthly_review_count"] == 2
    assert admin.json()["data"]["metrics"]["monthly_high_risk_contract_count"] == 1
    assert len(admin.json()["data"]["todos"]) == 2


def test_dashboard_date_boundaries_distribution_and_average(tmp_path: Path) -> None:
    now = datetime(2026, 7, 13, 12, tzinfo=timezone.utc)
    service = _service(tmp_path)
    history = service.history
    history.append(
        _record(
            review_id="month_start",
            owner_id="admin",
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            risk_level="高风险",
            duration_ms=1000,
            contract_type="service",
        )
    )
    history.append(
        _record(
            review_id="month_current",
            owner_id="admin",
            created_at=now,
            risk_level="严重",
            duration_ms=3000,
            contract_type="service",
        )
    )
    history.append(
        _record(
            review_id="previous_month",
            owner_id="admin",
            created_at=datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
            duration_ms=9999,
        )
    )
    history.append(
        _record(
            review_id="future",
            owner_id="admin",
            created_at=now + timedelta(days=1),
            duration_ms=9999,
        )
    )
    summary = service.summary(_actor("admin", UserRole.admin), now=now)
    assert summary.metrics.monthly_review_count == 2
    assert summary.metrics.monthly_high_risk_contract_count == 2
    assert summary.metrics.average_review_duration_ms == 2000
    assert {item.key: item.value for item in summary.risk_level_distribution} == {
        "critical": 1,
        "high": 1,
        "low": 1,
    }
    assert summary.contract_type_distribution[0].label == "服务合同"
    assert summary.top_risk_rules is not None
    assert summary.top_risk_rules[0].rule_id == "R008"
    assert summary.top_risk_rules[0].count == 3


def test_dashboard_incomplete_rule_snapshots_do_not_publish_partial_ranking(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    service = _service(tmp_path)
    service.history.append(
        _record(
            review_id="legacy",
            owner_id="admin",
            created_at=now,
            rule_counts_complete=False,
        )
    )
    summary = service.summary(_actor("admin", UserRole.admin), now=now)
    assert summary.top_risk_rules is None
    assert "top_risk_rules" in summary.unavailable_reasons
