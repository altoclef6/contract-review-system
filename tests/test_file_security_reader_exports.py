from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from contract_review.core.config import get_settings
from contract_review.core.exceptions import UnsafeUploadError
from contract_review.main import create_app
from contract_review.services.history_service import HistoryService, build_history_item
from contract_review.services.report_service import ReportService
from contract_review.utils.file_utils import validate_file_signature


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin12345!"},
    )
    return response.json()["data"]["access_token"]


def test_file_signature_rejects_disguised_executable(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "contract.pdf"
    fake_pdf.write_bytes(b"MZ\x90\x00malicious")
    with pytest.raises(UnsafeUploadError):
        validate_file_signature(fake_pdf)


def test_report_exports_markdown_and_excel(tmp_path: Path) -> None:
    report = {
        "审查编号": "review_export",
        "文件名": "采购合同.pdf",
        "总体风险等级": "高风险",
        "风险评分": {"风险分": 80, "安全分": 20},
        "审查摘要": "存在付款风险。",
        "风险点": [
            {
                "风险编号": "R001",
                "风险等级": "高",
                "风险类别": "付款结算",
                "风险标题": "付款条件缺失",
                "问题说明": "未约定付款条件。",
                "修改方向": "补充验收后付款。",
            }
        ],
        "修改建议": [],
    }
    exports = ReportService(tmp_path).save_all_reports("review_export", report)
    assert {"json", "docx", "pdf", "markdown", "xlsx"}.issubset(exports)
    assert exports["markdown"].read_text(encoding="utf-8").startswith("# 合同智能审查报告")
    assert exports["xlsx"].stat().st_size > 0


def test_pdf_reader_locates_clause(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    pdf_path = upload_dir / "contract.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Payment must be completed after acceptance.")
    document.save(pdf_path)
    document.close()
    HistoryService(tmp_path).append(
        build_history_item(
            review_id="review_reader",
            file_name="contract.pdf",
            final_report={},
            report_path=None,
            exports={},
            source_file_path=str(pdf_path),
        )
    )
    with TestClient(create_app()) as client:
        headers = {"Authorization": f"Bearer {_login(client)}"}
        preview = client.get("/api/v1/reader/review_reader/file", headers=headers)
        assert preview.status_code == 200
        locations = client.get(
            "/api/v1/reader/review_reader/locations",
            headers=headers,
            params={"text": "acceptance"},
        )
        assert locations.status_code == 200
        assert locations.json()["data"]["locations"][0]["page"] == 1
