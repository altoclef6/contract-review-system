import json
from pathlib import Path

from contract_review.services.knowledge_service import KnowledgeService


def test_structured_retrieval_excludes_expired_and_keeps_source_identity(tmp_path: Path) -> None:
    documents = [
        {
            "document_id": "effective-1",
            "title": "企业测试制度",
            "source_type": "enterprise_policy",
            "jurisdiction": "TEST",
            "issuing_authority": "虚构企业",
            "version": "1",
            "effective_date": "2026-01-01",
            "expiry_date": None,
            "status": "effective",
            "article_number": "DATA-1",
            "content": "数据保存期限和删除机制",
            "source_url": None,
            "checksum": "test-checksum-1",
        },
        {
            "document_id": "expired-1",
            "title": "失效测试制度",
            "source_type": "review_guideline",
            "jurisdiction": "TEST",
            "issuing_authority": "虚构维护者",
            "version": "0",
            "effective_date": "2020-01-01",
            "expiry_date": "2021-01-01",
            "status": "expired",
            "article_number": "OLD-1",
            "content": "数据保存期限和删除机制",
            "source_url": None,
            "checksum": "test-checksum-2",
        },
    ]
    (tmp_path / "documents.json").write_text(json.dumps(documents), encoding="utf-8")
    findings = [{"风险类别": "保密", "风险标题": "数据保存期限缺失", "问题说明": "数据删除"}]
    hits = KnowledgeService(tmp_path).retrieve(findings, minimum_score=1)
    assert {hit["document_id"] for hit in hits} == {"effective-1"}
    assert hits[0]["article_number"] == "DATA-1"
    assert hits[0]["source_type"] == "enterprise_policy"
    assert hits[0]["is_enterprise_policy"] == "true"


def test_low_relevance_structured_result_is_not_returned(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "src/contract_review/knowledge/test_review_guidelines.json"
    (tmp_path / "test.json").write_bytes(source.read_bytes())
    findings = [{"风险类别": "争议", "风险标题": "仲裁冲突", "问题说明": "管辖法院"}]
    assert KnowledgeService(tmp_path).retrieve(findings, minimum_score=2) == []
