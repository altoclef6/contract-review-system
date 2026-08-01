from __future__ import annotations

from time import perf_counter
from typing import Any

from contract_review.core.config import get_settings
from contract_review.graph.state import ContractReviewState, emit_stage
from contract_review.schemas.agent import NodeTelemetry, ValidatorOutput, utcnow
from contract_review.services.legal_knowledge_service import LegalKnowledgeRetriever


async def validator_node(state: ContractReviewState) -> dict:
    emit_stage(state, "VALIDATING_RESULT")
    started_at = utcnow()
    started = perf_counter()
    seen: set[tuple[str, str]] = set()
    validated: list[dict[str, Any]] = []
    rejected = downgraded = 0
    retriever = LegalKnowledgeRetriever(get_settings())
    allowed_ids = {
        str(item.get("legalArticleId"))
        for item in state.get("knowledge_hits", [])
        if item.get("legalArticleId")
    }
    for raw in state.get("compliance_findings", []):
        item = dict(raw)
        key = (str(item.get("rule_id") or item.get("风险标题")), str(item.get("相关条款", "")))
        if key in seen:
            rejected += 1
            continue
        seen.add(key)
        if not str(item.get("相关条款", "")).strip() and item.get("来源") != "deterministic_rule":
            item["requires_human_review"] = True
            item["风险等级"] = "中" if item.get("风险等级") in {"高", "严重"} else item.get("风险等级", "中")
            downgraded += 1
        if item.get("风险等级") in {"高", "严重"}:
            item["requires_human_review"] = True
        raw_basis = item.get("legalBasis", item.get("legal_basis", []))
        basis = retriever.validate_legal_basis(
            raw_basis,
            allowed_article_ids=allowed_ids if item.get("来源") == "AI增强审查" else None,
        )
        item["legalBasis"] = basis
        item["legal_basis"] = basis
        item["knowledge_document_ids"] = [entry["legalArticleId"] for entry in basis]
        item["审查依据"] = (
            "；".join(f"《{entry['lawName']}》{entry['articleNo']}" for entry in basis)
            if basis
            else "未匹配到已核验法律依据"
        )
        item["hasRisk"] = bool(item.get("hasRisk", True))
        item["riskLevel"] = item.get("riskLevel") or {
            "低": "low",
            "中": "medium",
            "高": "high",
            "严重": "critical",
        }.get(str(item.get("风险等级")), "medium")
        item["riskName"] = item.get("riskName") or item.get("风险标题") or "合同风险"
        item["originalClause"] = item.get("originalClause") or item.get("相关条款") or ""
        item["riskDescription"] = item.get("riskDescription") or item.get("问题说明") or ""
        item["possibleConsequence"] = item.get("possibleConsequence") or item.get("可能后果") or ""
        item["modificationAdvice"] = item.get("modificationAdvice") or item.get("修改方向") or ""
        item["recommendedClause"] = item.get("recommendedClause") or item.get("推荐条款") or ""
        if not isinstance(item.get("confidence"), (int, float)):
            item["confidence"] = 1.0 if item.get("来源") != "AI增强审查" else 0.6
        validated.append(item)
    telemetry = NodeTelemetry(
        node_name="validator",
        started_at=started_at,
        ended_at=utcnow(),
        duration_ms=(perf_counter() - started) * 1000,
        status="degraded" if downgraded else "completed",
    )
    output = ValidatorOutput(
        findings=validated,
        rejected_count=rejected,
        downgraded_count=downgraded,
        telemetry=telemetry,
    )
    return {
        "compliance_findings": output.findings,
        "node_telemetry": state.get("node_telemetry", []) + [telemetry.model_dump()],
    }
