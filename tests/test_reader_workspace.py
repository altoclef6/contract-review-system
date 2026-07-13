import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.core.config import Settings, get_settings
from contract_review.main import create_app
from contract_review.services.history_service import HistoryService
from contract_review.services.reader_workspace_service import (
    ReaderWorkspaceService,
    resolve_text_location,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        jwt_secret_key="test-secret",
        bootstrap_admin_password="Admin12345!",
        report_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        security_data_dir=tmp_path / "security",
        contract_data_dir=tmp_path / "contracts",
    )


def _workspace_record(tmp_path: Path, report: dict, text: str) -> tuple[Settings, dict]:
    settings = _settings(tmp_path)
    settings.report_dir.mkdir(parents=True)
    report_path = settings.report_dir / "review_reader.json"
    text_path = settings.report_dir / "review_reader.source.txt"
    report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    text_path.write_text(text, encoding="utf-8")
    return settings, {
        "review_id": "review_reader",
        "file_name": "测试合同.docx",
        "contract_type": "software_development",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "report_path": str(report_path),
        "contract_text_path": str(text_path),
        "created_by": None,
    }


def test_location_uses_valid_offset_for_repeated_text() -> None:
    text = "付款期限为十日。其他约定。付款期限为十日。"
    second = text.rfind("付款期限为十日")
    location = resolve_text_location(
        text,
        "付款期限为十日",
        start_offset=second,
        end_offset=second + len("付款期限为十日"),
    )
    assert location.status == "exact_offset"
    assert location.start_offset == second


def test_location_out_of_bounds_falls_back_without_invalid_highlight() -> None:
    text = "第一条 付款期限为十日。"
    location = resolve_text_location(
        text,
        "付款期限为十日",
        start_offset=999,
        end_offset=1200,
    )
    assert location.status == "text_match"
    assert location.start_offset is not None
    assert 0 <= location.start_offset < location.end_offset <= len(text)  # type: ignore[operator]


def test_empty_text_and_missing_clause_have_no_fake_position() -> None:
    assert resolve_text_location("", "付款条款").start_offset is None
    assert resolve_text_location("合同正文", "未在合同文本中识别到明确条款").status == "unavailable"


def test_workspace_keeps_xss_as_text_and_does_not_invent_knowledge_basis(tmp_path: Path) -> None:
    xss = '<img src=x onerror="alert(1)">付款条款'
    report = {
        "文件名": "测试合同.docx",
        "总体风险等级": "中风险",
        "风险评分": {"风险分": 45},
        "风险点": [
            {
                "风险编号": "R001",
                "风险类别": "付款结算",
                "风险等级": "中",
                "风险标题": xss,
                "相关条款": xss,
                "问题说明": "模型称存在依据，但没有结构化文档标识。",
                "审查依据": "某模型生成的法规名称",
                "修改方向": "补充付款节点。",
                "来源": "AI增强审查",
                "start_offset": 0,
                "end_offset": len(xss),
            }
        ],
        "依据检索": [{"来源": "普通Markdown片段", "内容": "付款节点", "匹配分": "2"}],
    }
    settings, record = _workspace_record(tmp_path, report, xss)
    workspace = ReaderWorkspaceService(settings).build(record)
    assert workspace.contract_text == xss
    assert workspace.risks[0].title == xss
    assert workspace.risks[0].knowledge_basis == []
    assert workspace.risks[0].ai_involved is True


def test_workspace_only_exposes_effective_structured_basis_and_handles_empty_result(
    tmp_path: Path,
) -> None:
    report = {
        "总体风险等级": "低风险",
        "风险点": [
            {
                "风险编号": "R043",
                "风险类别": "数据",
                "风险等级": "中",
                "风险标题": "缺少数据保存期限",
                "相关条款": "数据处理",
                "问题说明": "未约定保存期限",
                "修改方向": "补充保存期限",
                "来源": "deterministic_rule",
            }
        ],
        "依据检索": [
            {
                "来源": "企业数据制度",
                "document_id": "POLICY-1",
                "article_number": "DATA-01",
                "source_type": "enterprise_policy",
                "status": "effective",
                "updated_at": "2026-07-01T00:00:00Z",
                "内容": "数据保存期限、删除机制和访问权限要求。",
            },
            {
                "来源": "失效制度",
                "document_id": "OLD-1",
                "source_type": "enterprise_policy",
                "status": "expired",
                "内容": "数据保存期限。",
            },
        ],
    }
    settings, record = _workspace_record(tmp_path, report, "数据处理")
    workspace = ReaderWorkspaceService(settings).build(record)
    assert [item.document_id for item in workspace.risks[0].knowledge_basis] == ["POLICY-1"]
    assert workspace.risks[0].location.page_number is None
    empty_settings, empty_record = _workspace_record(
        tmp_path / "empty", {"总体风险等级": None, "风险点": []}, ""
    )
    empty = ReaderWorkspaceService(empty_settings).build(empty_record)
    assert empty.risks == []
    assert empty.chapters == []
    assert empty.contract_text == ""


def _configure_api(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("CONTRACT_DATA_DIR", str(tmp_path / "contracts"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    get_settings.cache_clear()


def test_reader_workspace_and_pdf_endpoints_prevent_idor(tmp_path: Path, monkeypatch) -> None:
    _configure_api(monkeypatch, tmp_path)
    report_dir = tmp_path / "reports"
    upload_dir = tmp_path / "uploads"
    report_dir.mkdir()
    upload_dir.mkdir()
    report_path = report_dir / "owned.json"
    text_path = report_dir / "owned.source.txt"
    pdf_path = upload_dir / "owned.pdf"
    report_path.write_text(json.dumps({"风险点": []}), encoding="utf-8")
    text_path.write_text("<script>alert(1)</script>", encoding="utf-8")
    pdf_path.write_bytes(b"%PDF-1.4\n")

    with TestClient(create_app()) as client:
        def register(email: str) -> tuple[str, str]:
            response = client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Employee12345!", "full_name": email},
            )
            user_id = response.json()["data"]["id"]
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "Employee12345!"},
            )
            return user_id, login.json()["data"]["access_token"]

        owner_id, owner_token = register("owner@example.com")
        _, attacker_token = register("attacker@example.com")
        HistoryService(tmp_path).append(
            {
                "review_id": "review_owned",
                "file_name": "owned.pdf",
                "contract_type": "general",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": owner_id,
                "report_path": str(report_path),
                "contract_text_path": str(text_path),
                "source_file_path": str(pdf_path),
                "exports": {"json": str(report_path)},
            }
        )
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        attacker_headers = {"Authorization": f"Bearer {attacker_token}"}
        workspace = client.get(
            "/api/v1/reader/review_owned/workspace", headers=owner_headers
        )
        assert workspace.status_code == 200
        assert workspace.json()["data"]["contract_text"] == "<script>alert(1)</script>"
        assert client.get(
            "/api/v1/reader/review_owned/workspace", headers=attacker_headers
        ).status_code == 404
        assert client.get(
            "/api/v1/reader/review_owned/file", headers=attacker_headers
        ).status_code == 404
        assert client.get(
            "/api/v1/reader/review_owned/locations",
            headers=attacker_headers,
            params={"text": "owned"},
        ).status_code == 404
