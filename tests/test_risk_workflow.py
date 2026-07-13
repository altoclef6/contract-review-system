from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.schemas.risk import RiskStatus
from contract_review.services.audit_service import AuditService
from contract_review.services.risk_service import TRANSITIONS, RiskService, RiskTransitionError


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_ENABLED", "false")
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("CONTRACT_DATA_DIR", str(tmp_path / "contracts"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-risk-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _register(client: TestClient, email: str) -> tuple[str, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Employee12345!", "full_name": email},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"], _login(client, email, "Employee12345!")


def _seed(settings, owner_id: str, review_id: str, count: int = 1):
    findings = [
        {
            "风险编号": f"R-{review_id}-{index}",
            "风险等级": "高" if index == 0 else "中",
            "风险类别": "付款结算",
            "风险标题": f"付款风险 {index}",
            "相关条款": "付款周期超过180天",
            "问题说明": "付款周期过长，需人工复核。",
            "修改方向": "缩短付款周期并明确节点。",
            "来源": "deterministic_rule",
            "rule_id": "PAYMENT-180",
            "start_offset": 10,
            "end_offset": 20,
            "page_number": 2,
            "knowledge_document_ids": ["TEST-POLICY-1"],
        }
        for index in range(count)
    ]
    return RiskService(settings).persist_review_findings(
        review_id=review_id,
        findings=findings,
        contract_id=None,
        contract_version_id=None,
        created_by=owner_id,
    )


def _post_transition(client: TestClient, headers: dict[str, str], risk: dict, action: str):
    return client.post(
        f"/api/v1/risks/{risk['risk_id']}/{action}",
        headers=headers,
        json={"expected_revision": risk["revision"], "reason": f"test {action}"},
    )


def test_risk_full_legal_transition_paths_and_persistence(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        owner_id, owner_headers = _register(client, "owner@example.com")
        admin_headers = _login(client, "admin@example.com", "Admin12345!")
        records = _seed(get_settings(), owner_id, "review-transitions", 2)

        listed = client.get("/api/v1/risks", headers=owner_headers).json()["data"]
        assert listed["total"] == 2
        assert listed["items"][0]["matched_text"] == "付款周期超过180天"
        assert listed["items"][0]["contract_version_id"] is None
        assert listed["items"][0]["page_number"] == 2
        assert listed["items"][0]["rule_id"] == "PAYMENT-180"
        assert listed["items"][0]["knowledge_document_ids"] == ["TEST-POLICY-1"]
        assert listed["items"][0]["status"] == "pending_review"

        current = client.get(f"/api/v1/risks/{records[0].risk_id}", headers=admin_headers).json()[
            "data"
        ]
        for action, expected in [
            ("confirm", "confirmed"),
            ("start-remediation", "remediating"),
            ("mark-remediated", "remediated"),
            ("start-remediation", "remediating"),
            ("mark-remediated", "remediated"),
            ("close", "closed"),
        ]:
            response = _post_transition(client, admin_headers, current, action)
            assert response.status_code == 200, response.text
            current = response.json()["data"]
            assert current["status"] == expected
        assert current["confirmed_at"] is not None
        assert current["resolved_at"] is not None
        assert len(current["state_history"]) == 7
        audit_records = AuditService(get_settings().security_data_dir).list_operations(
            target=current["risk_id"]
        )
        assert any(
            item["action"] == "risks.transition"
            and item["metadata"]["old_status"] == "pending_review"
            and item["metadata"]["new_status"] == "confirmed"
            for item in audit_records
        )

        rejected = client.get(f"/api/v1/risks/{records[1].risk_id}", headers=admin_headers).json()[
            "data"
        ]
        response = _post_transition(client, admin_headers, rejected, "reject")
        rejected = response.json()["data"]
        assert rejected["status"] == RiskStatus.rejected.value
        response = _post_transition(client, admin_headers, rejected, "close")
        assert response.json()["data"]["status"] == RiskStatus.closed.value


def test_risk_idor_assignment_comments_revision_and_conflict(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        owner_id, owner_headers = _register(client, "owner@example.com")
        assignee_id, assignee_headers = _register(client, "assignee@example.com")
        _, attacker_headers = _register(client, "attacker@example.com")
        admin_headers = _login(client, "admin@example.com", "Admin12345!")
        record = _seed(get_settings(), owner_id, "review-idor")[0]
        path = f"/api/v1/risks/{record.risk_id}"

        assert client.get(path, headers=attacker_headers).status_code == 404
        assert (
            client.post(
                f"{path}/comments",
                headers=attacker_headers,
                json={"content": "越权评论", "expected_revision": 1},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"{path}/assign",
                headers=owner_headers,
                json={"assignee_id": assignee_id, "expected_revision": 1},
            ).status_code
            == 403
        )

        assigned = client.post(
            f"{path}/assign",
            headers=admin_headers,
            json={"assignee_id": assignee_id, "expected_revision": 1},
        )
        assert assigned.status_code == 200
        current = assigned.json()["data"]
        assert current["assignee_id"] == assignee_id
        assert client.get(path, headers=assignee_headers).status_code == 200

        commented = client.post(
            f"{path}/comments",
            headers=assignee_headers,
            json={"content": "已核对付款周期", "expected_revision": current["revision"]},
        )
        assert commented.status_code == 200
        current = commented.json()["data"]
        assert current["comments"][-1]["content"] == "已核对付款周期"

        revised = client.put(
            f"{path}/revised-clause",
            headers=assignee_headers,
            json={
                "revised_clause": "付款周期调整为30日。",
                "expected_revision": current["revision"],
            },
        )
        assert revised.status_code == 200
        assert revised.json()["data"]["revised_clause"] == "付款周期调整为30日。"

        stale = client.post(
            f"{path}/comments",
            headers=owner_headers,
            json={"content": "并发旧版本", "expected_revision": current["revision"]},
        )
        assert stale.status_code == 409


def test_illegal_transition_and_permission_failure_roll_back(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        owner_id, owner_headers = _register(client, "owner@example.com")
        admin_headers = _login(client, "admin@example.com", "Admin12345!")
        record = _seed(get_settings(), owner_id, "review-rollback")[0]
        path = f"/api/v1/risks/{record.risk_id}"

        employee_confirm = _post_transition(
            client, owner_headers, record.model_dump(mode="json"), "confirm"
        )
        assert employee_confirm.status_code == 403
        illegal = _post_transition(
            client, admin_headers, record.model_dump(mode="json"), "mark-remediated"
        )
        assert illegal.status_code == 409
        assert "pending_review" in illegal.json()["detail"]

        unchanged = client.get(path, headers=admin_headers).json()["data"]
        assert unchanged["status"] == "pending_review"
        assert unchanged["revision"] == 1
        assert len(unchanged["state_history"]) == 1


def test_every_disallowed_state_transition_is_rejected(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    settings = get_settings()
    actor_id = "admin-test"
    service = RiskService(settings)
    records = _seed(settings, actor_id, "review-all-invalid", 6)
    by_status = {RiskStatus.pending_review: records[0]}

    def move(record, target: RiskStatus):
        return service.transition(
            record.risk_id,
            target=target,
            actor_id=actor_id,
            actor_role="admin",
            expected_revision=record.revision,
            reason="prepare state",
        )[0]

    by_status[RiskStatus.confirmed] = move(records[1], RiskStatus.confirmed)
    by_status[RiskStatus.rejected] = move(records[2], RiskStatus.rejected)
    remediating = move(records[3], RiskStatus.confirmed)
    by_status[RiskStatus.remediating] = move(remediating, RiskStatus.remediating)
    remediated = move(records[4], RiskStatus.confirmed)
    remediated = move(remediated, RiskStatus.remediating)
    by_status[RiskStatus.remediated] = move(remediated, RiskStatus.remediated)
    closed = move(records[5], RiskStatus.rejected)
    by_status[RiskStatus.closed] = move(closed, RiskStatus.closed)

    for current_status, record in by_status.items():
        for target in set(RiskStatus) - TRANSITIONS[current_status]:
            with pytest.raises(RiskTransitionError):
                service.transition(
                    record.risk_id,
                    target=target,
                    actor_id=actor_id,
                    actor_role="admin",
                    expected_revision=record.revision,
                    reason="must fail",
                )
            unchanged = service.get(record.risk_id, actor_id=actor_id, actor_role="admin")
            assert unchanged.status == current_status
            assert unchanged.revision == record.revision
