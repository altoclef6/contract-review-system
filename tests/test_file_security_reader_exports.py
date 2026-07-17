import zipfile
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.pdfbase import pdfmetrics

from contract_review.core.config import get_settings
from contract_review.core.exceptions import UnsafeUploadError
from contract_review.main import create_app
from contract_review.services.history_service import HistoryService, build_history_item
from contract_review.services.report_service import ReportService
from contract_review.utils.file_utils import normalize_original_filename, validate_file_signature


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


def test_original_filename_removes_paths_controls_and_spoofing_marks() -> None:
    assert normalize_original_filename("../目录/合同\u202egnp.pdf") == "合同gnp.pdf"
    assert normalize_original_filename("C:\\temp\\合同\r\n.pdf") == "合同.pdf"
    assert len(normalize_original_filename(f"{'长' * 300}.pdf")) == 260


def test_docx_rejects_archive_path_traversal(tmp_path: Path) -> None:
    malicious = tmp_path / "contract.docx"
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
        archive.writestr("../outside.exe", b"payload")
    with pytest.raises(UnsafeUploadError, match="不安全路径"):
        validate_file_signature(malicious)


def test_docx_rejects_non_office_zip(tmp_path: Path) -> None:
    fake_docx = tmp_path / "contract.docx"
    with zipfile.ZipFile(fake_docx, "w") as archive:
        archive.writestr("payload.exe", b"payload")
    with pytest.raises(UnsafeUploadError, match="有效的 DOCX"):
        validate_file_signature(fake_docx)


def test_docx_rejects_external_relationships_and_macros(tmp_path: Path) -> None:
    external = tmp_path / "external.docx"
    with zipfile.ZipFile(external, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
        archive.writestr(
            "word/_rels/document.xml.rels",
            '<Relationships><Relationship TargetMode="External" Target="https://example.test" /></Relationships>',
        )
    with pytest.raises(UnsafeUploadError, match="外部资源"):
        validate_file_signature(external)

    alternate_external = tmp_path / "alternate-external.docx"
    with zipfile.ZipFile(alternate_external, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
        archive.writestr(
            "word/_rels/document.xml.rels",
            "<Relationships><Relationship targetmode = 'EXTERNAL' Target = 'https://example.test' /></Relationships>",
        )
    with pytest.raises(UnsafeUploadError, match="外部资源"):
        validate_file_signature(alternate_external)

    macro = tmp_path / "macro.docx"
    with zipfile.ZipFile(macro, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
        archive.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(UnsafeUploadError, match="宏"):
        validate_file_signature(macro)


def test_file_signature_uses_configured_page_and_pixel_limits(tmp_path: Path) -> None:
    pdf_path = tmp_path / "two-pages.pdf"
    with fitz.open() as document:
        document.new_page()
        document.new_page()
        document.save(pdf_path)
    with pytest.raises(UnsafeUploadError, match="页数"):
        validate_file_signature(pdf_path, max_pdf_pages=1)

    image_path = tmp_path / "image.png"
    Image.new("RGB", (2, 2)).save(image_path)
    with pytest.raises(UnsafeUploadError, match="像素"):
        validate_file_signature(image_path, max_image_pixels=3)


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


def test_pdf_export_uses_portable_font_fallback(tmp_path: Path, monkeypatch) -> None:
    registered_fonts = pdfmetrics.getRegisteredFontNames()
    monkeypatch.setattr(
        pdfmetrics,
        "getRegisteredFontNames",
        lambda: [name for name in registered_fonts if name != "ChineseFont"],
    )
    monkeypatch.setattr(Path, "exists", lambda _path: False)

    path = ReportService(tmp_path).save_pdf_report(
        "portable_font",
        {
            "审查编号": "portable_font",
            "文件名": "合同.pdf",
            "总体风险等级": "低风险",
            "审查摘要": "中文导出不依赖宿主机字体。",
        },
    )

    assert path.read_bytes().startswith(b"%PDF-")


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
