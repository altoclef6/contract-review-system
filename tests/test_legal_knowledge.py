from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from contract_review.agents.validator import validator_node
from contract_review.core.config import get_settings
from contract_review.main import create_app
from contract_review.services.legal_knowledge_service import (
    LegalKnowledgeRetriever,
    LegalKnowledgeService,
)


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECURITY_DATA_DIR", str(tmp_path / "security"))
    monkeypatch.setenv("LEGAL_KNOWLEDGE_DATA_DIR", str(tmp_path / "legal-knowledge"))
    monkeypatch.setenv("RISK_FEEDBACK_DATA_DIR", str(tmp_path / "risk-feedback"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    monkeypatch.setenv("DATABASE_ENABLED", "false")
    get_settings.cache_clear()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_verified_fixture(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict]:
    document_response = client.post(
        "/api/v1/legal-knowledge/documents",
        headers=headers,
        json={
            "name": "自动化测试合同规则",
            "document_type": "test_data",
            "issuing_authority": "自动化测试夹具",
            "document_number": "TEST-LEGAL-001",
            "effect_status": "effective",
            "version_number": "1.0",
            "official_source_url": "https://example.test/legal/001",
            "source_name": "自动化测试来源",
            "full_text": "这是自动化测试资料，不是真实法律原文。付款条件应当明确。",
            "verification_status": "verified",
            "is_enabled": True,
        },
    )
    assert document_response.status_code == 201, document_response.text
    document = document_response.json()["data"]
    versions = client.get(
        f"/api/v1/legal-knowledge/documents/{document['id']}/versions", headers=headers
    ).json()["data"]
    article_response = client.post(
        "/api/v1/legal-knowledge/articles",
        headers=headers,
        json={
            "legal_document_id": document["id"],
            "legal_document_version_id": versions[0]["id"],
            "article_no": "测试第一条",
            "article_no_numeric": 1,
            "title": "付款条件",
            "content": "付款时间、比例和前置条件应当明确。",
            "keywords": ["付款", "支付"],
            "legal_topics": ["付款条件"],
            "contract_types": ["software_development", "general"],
            "is_effective": True,
            "verification_status": "verified",
        },
    )
    assert article_response.status_code == 201, article_response.text
    return document, article_response.json()["data"]


def test_admin_crud_versions_rules_and_employee_read_only(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin = _login(client, "admin@example.com", "Admin12345!")
        document, article = _create_verified_fixture(client, admin)
        updated = client.patch(
            f"/api/v1/legal-knowledge/documents/{document['id']}",
            headers=admin,
            json={"version_number": "1.1", "change_summary": "自动化测试新版本"},
        )
        assert updated.status_code == 200, updated.text
        history = client.get(
            f"/api/v1/legal-knowledge/documents/{document['id']}/versions", headers=admin
        )
        assert history.status_code == 200
        assert [item["version_number"] for item in history.json()["data"]] == ["1.1", "1.0"]

        rule_response = client.post(
            "/api/v1/legal-knowledge/rules",
            headers=admin,
            json={
                "rule_code": "TEST-PAYMENT-001",
                "rule_name": "付款条件不明确",
                "contract_types": ["software_development"],
                "clause_type": "付款结算",
                "risk_level": "high",
                "trigger_condition": "包含付款关键词",
                "keywords": ["付款"],
                "model_prompt": "仅使用提供的测试法条",
                "risk_description": "付款节点不明确",
                "possible_consequence": "可能发生结算争议",
                "modification_advice": "明确付款节点",
                "recommended_clause": "验收后十个工作日内付款。",
                "is_enabled": True,
                "legal_article_ids": [article["id"]],
            },
        )
        assert rule_response.status_code == 201, rule_response.text
        assert rule_response.json()["data"]["legal_article_ids"] == [article["id"]]

        register = client.post(
            "/api/v1/auth/register",
            json={
                "email": "employee@example.com",
                "password": "Employee12345!",
                "full_name": "Employee",
            },
        )
        assert register.status_code == 201
        employee = _login(client, "employee@example.com", "Employee12345!")
        search = client.get(
            "/api/v1/legal-knowledge/articles?keyword=付款", headers=employee
        )
        assert search.status_code == 200
        assert search.json()["data"]["items"][0]["id"] == article["id"]
        assert client.get("/api/v1/legal-knowledge/documents", headers=employee).status_code == 403
        assert (
            client.patch(
                f"/api/v1/legal-knowledge/articles/{article['id']}",
                headers=employee,
                json={"title": "越权修改"},
            ).status_code
            == 403
        )

    matches = LegalKnowledgeRetriever(get_settings()).match_risk_rules(
        "双方约定付款时间另行协商。", "software_development"
    )
    custom = next(item for item in matches if item.get("rule_id") == rule_response.json()["data"]["id"])
    assert custom["legalBasis"][0]["legalArticleId"] == article["id"]
    assert custom["legalBasis"][0]["lawName"] == "自动化测试合同规则"


def test_invalid_article_id_and_unverified_content_are_never_cited(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        admin = _login(client, "admin@example.com", "Admin12345!")
        invalid_rule = client.post(
            "/api/v1/legal-knowledge/rules",
            headers=admin,
            json={
                "rule_code": "TEST-INVALID-001",
                "rule_name": "不存在法条测试",
                "contract_types": ["all"],
                "clause_type": "付款结算",
                "risk_level": "medium",
                "trigger_condition": "测试",
                "keywords": ["付款"],
                "risk_description": "测试",
                "modification_advice": "测试",
                "legal_article_ids": ["article_does_not_exist"],
            },
        )
        assert invalid_rule.status_code == 422

        seeded = client.post("/api/v1/legal-knowledge/imports/demo", headers=admin)
        assert seeded.status_code == 200
        articles = client.get(
            "/api/v1/legal-knowledge/articles?include_unverified=true", headers=admin
        ).json()["data"]["items"]
        assert articles
        assert all(item["verification_status"] == "pending_verification" for item in articles)

    state = {
        "compliance_findings": [
            {
                "风险标题": "模型伪造法条",
                "风险等级": "高",
                "相关条款": "付款时间另行约定",
                "来源": "AI增强审查",
                "legalBasis": [
                    {
                        "legalArticleId": "article_does_not_exist",
                        "lawName": "模型虚构法律",
                        "articleNo": "第一条",
                        "sourceUrl": "https://invalid.example",
                    }
                ],
            }
        ],
        "knowledge_hits": [],
    }
    result = asyncio.run(validator_node(state))
    finding = result["compliance_findings"][0]
    assert finding["legalBasis"] == []
    assert finding["审查依据"] == "未匹配到已核验法律依据"

    service = LegalKnowledgeService(get_settings())
    additions = service.save_review_issue_links(
        review_id="review_test",
        issue_id="issue_test",
        legal_article_ids=["article_does_not_exist"],
        actor_id="tester",
    )
    assert additions == []
