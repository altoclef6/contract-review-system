from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.services.history_service import HistoryService, build_history_item


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["access_token"]


def test_history_search_and_statistics(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    service = HistoryService(tmp_path)
    service.append(
        build_history_item(
            review_id="review_purchase",
            file_name="年度采购合同.docx",
            final_report={
                "总体风险等级": "高风险",
                "风险评分": {"风险分": 80, "安全分": 20},
                "风险统计": {"高风险数量": 2},
                "AI增强": "已启用",
            },
            report_path=None,
            exports={},
            contract_type="purchase",
            duration_ms=1200,
            model_provider="deepseek",
            model_name="deepseek-chat",
            prompt_snapshot={"compliance": "采购审查"},
        )
    )
    with TestClient(create_app()) as client:
        token = _login(client, "admin@example.com", "Admin12345!")
        headers = {"Authorization": f"Bearer {token}"}
        listing = client.get(
            "/api/v1/analysis-history?keyword=采购&contract_type=purchase",
            headers=headers,
        )
        assert listing.status_code == 200
        payload = listing.json()["data"]
        assert payload["total"] == 1
        assert payload["items"][0]["model_name"] == "deepseek-chat"
        assert payload["items"][0]["prompt_snapshot"]["compliance"] == "采购审查"

        statistics = client.get("/api/v1/analysis-history/statistics", headers=headers)
        assert statistics.status_code == 200
        stats = statistics.json()["data"]
        assert stats["total_reviews"] == 1
        assert stats["average_risk_score"] == 80
        assert stats["risk_levels"]["高风险"] == 1


def test_employee_cannot_read_analysis_history(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "employee@example.com",
                "password": "Employee12345!",
                "full_name": "普通员工",
            },
        )
        token = _login(client, "employee@example.com", "Employee12345!")
        response = client.get(
            "/api/v1/analysis-history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
