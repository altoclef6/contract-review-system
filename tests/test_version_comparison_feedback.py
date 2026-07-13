
from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.services.version_comparison_service import VersionComparisonService


def _risk(rule: str, text: str, severity: str = "中", category: str = "付款") -> dict:
    return {
        "风险编号": f"risk-{rule}-{severity}",
        "规则编号": rule,
        "风险类别": category,
        "风险等级": severity,
        "风险标题": "付款风险",
        "相关条款": text,
        "章节": "付款条款",
        "原文定位": {"字符起点": 20},
    }


def test_text_comparison_identical_added_removed_and_repeated_paragraphs() -> None:
    service = VersionComparisonService()
    identical = service.compare_text(
        "第一条\n\n重复段落\n\n重复段落", "第一条\n\n重复段落\n\n重复段落"
    )
    assert all(item.change_type.value == "unchanged" for item in identical)

    changes = service.compare_text(
        "第一条 服务范围\n\n第二条 删除内容\n\n重复段落\n\n重复段落",
        "第一条 服务范围已修改\n\n第三条 新增内容\n\n重复段落\n\n重复段落",
    )
    statuses = {item.change_type.value for item in changes}
    assert "modified" in statuses
    assert any(item.target_text == "第三条 新增内容" for item in changes)
    assert sum(item.change_type.value == "unchanged" for item in changes) == 2


def test_large_contract_comparison_keeps_all_paragraphs() -> None:
    service = VersionComparisonService()
    base = "\n\n".join(f"第{i}条 测试内容{i}" for i in range(1500))
    target = base.replace("第750条 测试内容750", "第750条 已修改内容")
    changes = service.compare_text(base, target)
    assert len(changes) == 1500
    assert sum(item.change_type.value == "modified" for item in changes) == 1


def test_risk_matching_added_removed_severity_and_uncertain() -> None:
    service = VersionComparisonService()
    base = [
        _risk("R1", "付款期为30日", "中"),
        _risk("R2", "仅基础版本存在", "低", "保密"),
        _risk("R3", "基础文本完全不同", "中", "验收"),
    ]
    target = [
        _risk("R1", "付款期为30日", "高"),
        _risk("R3", "目标文本完全变化", "中", "验收"),
        _risk("R4", "仅目标版本存在", "低", "知识产权"),
    ]
    for risk in (base[2], target[1]):
        risk.pop("章节")
        risk.pop("原文定位")
    changes = service.compare_risks(base, target)
    statuses = [item.status.value for item in changes]
    assert "severity_increased" in statuses
    assert "uncertain_match" in statuses
    assert "removed" in statuses
    assert "added" in statuses


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("CONTRACT_DATA_DIR", str(tmp_path / "contracts"))
    monkeypatch.setenv("RISK_FEEDBACK_DATA_DIR", str(tmp_path / "feedback"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()[
        "data"
    ]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_contract_with_versions(
    client: TestClient, headers: dict[str, str]
) -> tuple[str, str, str]:
    contract = client.post(
        "/api/v1/contracts", headers=headers, json={"title": "版本测试合同", "category": "service"}
    ).json()["data"]
    contract_id = contract["id"]
    v1 = client.post(
        f"/api/v1/contracts/{contract_id}/versions",
        headers=headers,
        json={
            "file_name": "v1.docx",
            "file_hash": "a" * 64,
            "text_content": "第一条 服务范围\n\n第二条 付款期为30日",
            "risk_snapshot": [_risk("R1", "付款期为30日", "中")],
        },
    ).json()["data"]
    v2 = client.post(
        f"/api/v1/contracts/{contract_id}/versions",
        headers=headers,
        json={
            "file_name": "v2.docx",
            "file_hash": "b" * 64,
            "text_content": "第一条 服务范围已明确\n\n第二条 付款期为60日",
            "risk_snapshot": [_risk("R1", "付款期为60日", "高")],
        },
    ).json()["data"]
    return contract_id, v1["id"], v2["id"]


def test_version_compare_feedback_permissions_duplicates_and_statistics(
    monkeypatch, tmp_path: Path
) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin = _login(client, "admin@example.com", "Admin12345!")
        owner_register = client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "Owner12345!", "full_name": "Owner"},
        )
        owner = _login(client, "owner@example.com", "Owner12345!")
        other_register = client.post(
            "/api/v1/auth/register",
            json={"email": "other@example.com", "password": "Other12345!", "full_name": "Other"},
        )
        other = _login(client, "other@example.com", "Other12345!")
        contract_id, base_id, target_id = _create_contract_with_versions(client, owner)

        compared = client.post(
            f"/api/v1/version-comparisons/{contract_id}",
            headers=owner,
            json={"base_version_id": base_id, "target_version_id": target_id},
        )
        assert compared.status_code == 200
        assert compared.json()["data"]["risk_changes"][0]["status"] == "severity_increased"
        assert (
            client.post(
                f"/api/v1/version-comparisons/{contract_id}",
                headers=other,
                json={"base_version_id": base_id, "target_version_id": target_id},
            ).status_code
            == 404
        )

        payload = {
            "contract_id": contract_id,
            "contract_version_id": target_id,
            "risk_id": "risk-R1-高",
            "rule_id": "R1",
            "contract_type": "service",
            "feedback_type": "inaccurate_severity",
            "suggested_severity": "medium",
            "reason": "结合交易背景应为中风险",
        }
        assert client.post("/api/v1/risk-feedback", headers=owner, json=payload).status_code == 201
        assert client.post("/api/v1/risk-feedback", headers=owner, json=payload).status_code == 409
        assert client.post("/api/v1/risk-feedback", headers=other, json=payload).status_code == 404
        assert (
            client.get(
                f"/api/v1/risk-feedback?contract_id={contract_id}", headers=other
            ).status_code
            == 404
        )
        assert client.get("/api/v1/risk-feedback/statistics", headers=owner).status_code == 403
        stats = client.get("/api/v1/risk-feedback/statistics", headers=admin)
        assert stats.status_code == 200
        assert stats.json()["data"]["severity_adjustment_count"] == 1
        assert owner_register.status_code == 201
        assert other_register.status_code == 201


def test_feedback_requires_valid_risk_and_severity(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        owner = _login(client, "admin@example.com", "Admin12345!")
        contract_id, _, target_id = _create_contract_with_versions(client, owner)
        missing_level = client.post(
            "/api/v1/risk-feedback",
            headers=owner,
            json={
                "contract_id": contract_id,
                "contract_version_id": target_id,
                "risk_id": "risk-R1-高",
                "feedback_type": "inaccurate_severity",
            },
        )
        assert missing_level.status_code == 409
        missing_risk = client.post(
            "/api/v1/risk-feedback",
            headers=owner,
            json={
                "contract_id": contract_id,
                "contract_version_id": target_id,
                "risk_id": "not-present",
                "feedback_type": "not_a_risk",
            },
        )
        assert missing_risk.status_code == 404
