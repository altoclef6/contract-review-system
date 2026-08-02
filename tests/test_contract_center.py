import json
from datetime import datetime, timezone
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("CONTRACT_DATA_DIR", str(tmp_path / "contracts"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _register(client: TestClient, email: str) -> dict[str, str]:
    password = "Employee12345!"
    assert client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": email.split("@")[0]},
    ).status_code == 201
    return _login(client, email, password)


def test_contract_center_pagination_filters_admin_scope_and_old_data(
    tmp_path: Path, monkeypatch
) -> None:
    _configure(monkeypatch, tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    old_record = {
        "id": "contract_legacy",
        "title": "Legacy service contract",
        "category": "service",
        "tags": [],
        "counterparty": None,
        "file_name": None,
        "description": None,
        "status": "draft",
        "is_favorite": False,
        "created_at": now,
        "updated_at": now,
        "created_by": "legacy_owner",
        "updated_by": "legacy_owner",
        "expires_at": None,
        "versions": [],
    }
    contract_path = tmp_path / "contracts" / "contracts.json"
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text(json.dumps([old_record]), encoding="utf-8")

    with TestClient(create_app()) as client:
        owner_headers = _register(client, "owner@example.com")
        other_headers = _register(client, "other@example.com")
        admin_headers = _login(client, "admin@example.com", "Admin12345!")
        for index, category in enumerate(("software_development", "technical_service"), start=1):
            response = client.post(
                "/api/v1/contracts",
                headers=owner_headers,
                json={
                    "title": f"Contract {index}",
                    "category": category,
                    "tags": [],
                    "amount": "120000.00" if index == 1 else None,
                },
            )
            assert response.status_code == 201
        page = client.get(
            "/api/v1/contracts?page=1&page_size=1&category=software_development",
            headers=owner_headers,
        ).json()["data"]
        assert page["total"] == 1
        assert len(page["items"]) == 1
        assert page["items"][0]["amount"] == "120000.00"
        assert client.get("/api/v1/contracts", headers=other_headers).json()["data"]["total"] == 0
        admin_items = client.get(
            "/api/v1/contracts?page_size=20", headers=admin_headers
        ).json()["data"]["items"]
        assert len(admin_items) == 3
        legacy = next(item for item in admin_items if item["id"] == "contract_legacy")
        assert legacy["amount"] is None
        assert legacy["current_version"] == 0


def test_version_upload_download_idor_archive_restore_and_risk_filter(
    tmp_path: Path, monkeypatch
) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        owner_headers = _register(client, "owner@example.com")
        attacker_headers = _register(client, "attacker@example.com")
        admin_headers = _login(client, "admin@example.com", "Admin12345!")
        created = client.post(
            "/api/v1/contracts",
            headers=owner_headers,
            json={"title": "Secure contract", "category": "software_development", "tags": []},
        ).json()["data"]
        contract_id = created["id"]
        pdf = fitz.open()
        pdf.new_page().insert_text((72, 72), "Secure contract")
        pdf_bytes = pdf.tobytes()
        pdf.close()
        upload = client.post(
            f"/api/v1/contracts/{contract_id}/versions/upload",
            headers=owner_headers,
            files={"contract_file": ("../secure.pdf", pdf_bytes, "application/pdf")},
            data={"change_note": "Initial file", "version_type": "modified"},
        )
        assert upload.status_code == 201
        version = upload.json()["data"]
        assert version["version_no"] == 1
        assert version["version_type"] == "original"
        assert version["file_size"] > 0
        download_url = f"/api/v1/contracts/{contract_id}/versions/{version['id']}/download"
        assert client.get(download_url, headers=attacker_headers).status_code == 404
        assert client.get(download_url, headers=owner_headers).status_code == 200
        assert client.get(download_url, headers=admin_headers).status_code == 200

        assert client.post(
            f"/api/v1/contracts/{contract_id}/archive", headers=owner_headers
        ).json()["data"]["status"] == "archived"
        assert client.post(
            f"/api/v1/contracts/{contract_id}/restore", headers=owner_headers
        ).json()["data"]["status"] == "draft"

        history_path = tmp_path / "history.json"
        history_path.write_text(
            json.dumps(
                [
                    {
                        "review_id": "review_linked",
                        "contract_id": contract_id,
                        "contract_version_id": version["id"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "overall_risk_level": "高",
                        "risk_counts": {"高": 2, "中": 1},
                    }
                ]
            ),
            encoding="utf-8",
        )
        filtered = client.get(
            "/api/v1/contracts?risk_level=高", headers=owner_headers
        ).json()["data"]
        assert filtered["total"] == 1
        assert filtered["items"][0]["risk_count"] == 3
        overview = client.get(
            f"/api/v1/contracts/{contract_id}/overview", headers=owner_headers
        )
        assert overview.status_code == 200
        assert overview.json()["data"]["recent_reviews"][0]["review_id"] == "review_linked"
        assert client.get(
            f"/api/v1/contracts/{contract_id}/overview", headers=attacker_headers
        ).status_code == 404


def test_txt_upload_splits_clauses_and_rejects_duplicate(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    content = (
        "软件开发服务合同\n\n"
        "第一条 项目范围\n乙方负责开发合同审查系统。\n\n"
        "第二条 付款条件\n甲方在验收后十日内付款。\n\n"
        "第三条 验收标准\n双方依据附件功能清单完成验收。"
    ).encode("utf-8")
    with TestClient(create_app()) as client:
        owner_headers = _register(client, "clause-owner@example.com")
        attacker_headers = _register(client, "clause-attacker@example.com")
        contract = client.post(
            "/api/v1/contracts",
            headers=owner_headers,
            json={"title": "Clause contract", "category": "software_development", "tags": []},
        ).json()["data"]
        url = f"/api/v1/contracts/{contract['id']}/versions/upload"
        uploaded = client.post(
            url,
            headers=owner_headers,
            files={"contract_file": ("software.txt", content, "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        version = uploaded.json()["data"]
        assert version["parse_status"] == "ready"
        clauses_url = f"/api/v1/contracts/{contract['id']}/clauses?version_id={version['id']}"
        clauses = client.get(clauses_url, headers=owner_headers)
        assert clauses.status_code == 200
        assert len(clauses.json()["data"]) >= 3
        assert any(item["clause_type"] == "付款条件" for item in clauses.json()["data"])
        assert client.get(clauses_url, headers=attacker_headers).status_code == 404

        duplicate = client.post(
            url,
            headers=owner_headers,
            files={"contract_file": ("software-copy.txt", content, "text/plain")},
        )
        assert duplicate.status_code == 409
        assert "请勿重复提交" in duplicate.json()["message"]
