from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from contract_review.core.config import get_settings
from contract_review.graph.state import ContractReviewState, emit_stage
from contract_review.llm.json_client import call_llm_json
from contract_review.rules import RuleEngine
from contract_review.rules.models import RuleMatch
from contract_review.services.rule_center_service import RuleCenterService


def _rule_match_to_legacy(match: RuleMatch, number: int) -> dict[str, Any]:
    levels = {"low": "低", "medium": "中", "high": "高", "critical": "严重"}
    return {
        "hasRisk": True,
        "riskLevel": "HIGH" if match.severity.value in {"high", "critical"} else match.severity.value.upper(),
        "riskName": match.rule_name,
        "originalClause": match.contract_text,
        "riskDescription": match.explanation,
        "possibleConsequence": "需结合具体交易背景评估可能的履约和争议后果。",
        "legalArticleIds": [],
        "legalBasis": [],
        "modificationAdvice": match.recommendation,
        "recommendedClause": match.suggested_revision or "",
        "confidence": match.confidence,
        "风险编号": f"R{number:03d}",
        "风险类别": match.category,
        "风险等级": levels[match.severity.value],
        "短标题": match.rule_name[:10],
        "风险标题": match.rule_name,
        "相关条款": match.contract_text,
        "问题说明": match.explanation,
        "审查依据": "；".join(match.legal_basis) if match.legal_basis else "未检索到可靠法律依据，需人工复核",
        "修改方向": match.recommendation,
        "来源": match.source,
        "rule_id": match.rule_id,
        "risk_score": match.risk_score,
        "requires_human_review": match.requires_human_review,
        "start_offset": match.start_offset,
        "end_offset": match.end_offset,
        "paragraph_index": match.paragraph_index,
        "status": match.status,
    }


def _finding(
    number: int,
    category: str,
    level: str,
    title: str,
    reason: str,
    suggestion_direction: str,
    evidence: str,
    clause_text: str = "未在合同文本中识别到明确条款",
) -> dict[str, Any]:
    return {
        "hasRisk": True,
        "riskLevel": {"低": "LOW", "中": "MEDIUM", "高": "HIGH", "严重": "HIGH"}.get(level, "MEDIUM"),
        "riskName": title,
        "originalClause": clause_text,
        "riskDescription": reason,
        "possibleConsequence": "需结合具体交易背景评估可能的履约和争议后果。",
        "legalArticleIds": [],
        "legalBasis": [],
        "modificationAdvice": suggestion_direction,
        "recommendedClause": "",
        "confidence": 1.0,
        "风险编号": f"R{number:03d}",
        "风险类别": category,
        "风险等级": level,
        "短标题": category[:6],
        "风险标题": title,
        "相关条款": clause_text,
        "问题说明": reason,
        "审查依据": evidence,
        "修改方向": suggestion_direction,
        "来源": "规则审查",
    }


def _rule_check(fields: dict[str, Any], text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    parties = fields.get("合同主体", [])
    amounts = fields.get("合同金额", [])
    periods = fields.get("履行期限", [])
    payment_clauses = fields.get("付款条款", [])
    liability_clauses = fields.get("违约责任条款", [])
    dispute_clauses = fields.get("争议解决条款", [])
    confidentiality_clauses = fields.get("保密条款", [])
    termination_clauses = fields.get("解除终止条款", [])

    if len(parties) < 2:
        findings.append(
            _finding(
                len(findings) + 1,
                "主体信息",
                "高",
                "合同主体信息不完整",
                "未识别到至少两个明确合同主体，可能影响权利义务归属。",
                "补充双方完整名称、统一社会信用代码、注册地址、联系人及授权代表。",
                "企业合同内控要求签约主体信息完整、可核验。",
            )
        )
    if not amounts:
        findings.append(
            _finding(
                len(findings) + 1,
                "交易金额",
                "中",
                "合同金额不明确",
                "未识别到明确金额或价款计算方式，容易导致结算争议。",
                "明确合同总价、税率、含税口径、付款节点和结算依据。",
                "企业付款审批要求合同金额和付款依据清晰。",
            )
        )
    if not periods:
        findings.append(
            _finding(
                len(findings) + 1,
                "履行期限",
                "中",
                "履行期限不明确",
                "未识别到清晰起止时间或交付期限。",
                "增加合同生效时间、履行期限、交付节点、验收时间和延期机制。",
                "履约管理要求期限和验收条件可执行。",
            )
        )
    if not payment_clauses:
        findings.append(
            _finding(
                len(findings) + 1,
                "付款结算",
                "中",
                "付款条款缺失或不清晰",
                "未识别到付款方式、付款条件、发票要求或结算节点。",
                "补充付款比例、付款时间、收款账户、发票类型、付款前置条件和逾期处理。",
                "资金支付内控要求付款节点与验收、发票、审批材料匹配。",
            )
        )
    if not liability_clauses:
        findings.append(
            _finding(
                len(findings) + 1,
                "违约责任",
                "高",
                "缺少明确违约责任",
                "未明确违约行为、违约金或损失赔偿范围。",
                "明确逾期交付、逾期付款、质量不合格、保密违约等责任承担方式。",
                "关键义务必须匹配可执行的违约责任。",
            )
        )
    elif not any(
        ("违约金" in clause or "%" in clause or "每日" in clause) for clause in liability_clauses
    ):
        findings.append(
            _finding(
                len(findings) + 1,
                "违约责任",
                "中",
                "违约责任量化不足",
                "已识别到违约责任条款，但缺少违约金比例、计算方式或赔偿范围。",
                "增加违约金计算标准，并说明违约金不足以弥补损失时的补充赔偿机制。",
                "违约责任应具备可计算性和可执行性。",
                str(liability_clauses[0]),
            )
        )
    if not dispute_clauses:
        findings.append(
            _finding(
                len(findings) + 1,
                "争议解决",
                "中",
                "缺少争议解决条款",
                "未明确争议解决方式和管辖机构。",
                "明确协商、诉讼或仲裁方式，并约定有管辖权的法院或仲裁委员会。",
                "争议管理要求管辖条款明确、合法、便于执行。",
            )
        )
    if "保密" in text and not confidentiality_clauses:
        findings.append(
            _finding(
                len(findings) + 1,
                "保密义务",
                "低",
                "保密条款表达不充分",
                "出现保密表述，但保密范围、期限和违约责任不完整。",
                "补充保密信息范围、期限、例外情形、返还销毁要求及违约责任。",
                "涉商业秘密或经营数据合同应明确保密义务。",
            )
        )
    if not termination_clauses:
        findings.append(
            _finding(
                len(findings) + 1,
                "解除终止",
                "低",
                "解除或终止机制不明确",
                "未识别到解除、终止或不可抗力处理机制。",
                "增加解除条件、通知期限、终止后结算、资料返还和责任承担条款。",
                "合同生命周期管理要求退出机制清晰。",
            )
        )
    return findings


def _normalize_llm_findings(
    data: dict[str, Any] | list[Any], start_index: int
) -> list[dict[str, Any]]:
    items = data.get("风险点", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=start_index):
        if not isinstance(item, dict):
            continue
        if item.get("hasRisk") is False:
            continue
        risk_level = str(item.get("riskLevel") or "").upper()
        level_cn = {
            "LOW": "低",
            "MEDIUM": "中",
            "HIGH": "高",
        }.get(risk_level, item.get("风险等级") or item.get("等级") or "中")
        legal_article_ids = item.get("legalArticleIds") if isinstance(item.get("legalArticleIds"), list) else []
        basis = [{"legalArticleId": value} for value in legal_article_ids if value]
        if not basis and isinstance(item.get("legalBasis"), list):
            basis = item.get("legalBasis")
        risk_name = item.get("riskName") or item.get("风险标题") or item.get("标题") or "AI识别风险"
        original_clause = item.get("originalClause") or item.get("相关条款") or item.get("条款") or ""
        description = item.get("riskDescription") or item.get("问题说明") or item.get("原因") or item.get("说明") or ""
        advice = item.get("modificationAdvice") or item.get("修改方向") or item.get("建议") or ""
        result.append(
            {
                "hasRisk": True,
                "riskLevel": risk_level if risk_level in {"LOW", "MEDIUM", "HIGH"} else {"低": "LOW", "中": "MEDIUM", "高": "HIGH", "严重": "HIGH"}.get(str(level_cn), "MEDIUM"),
                "riskName": risk_name,
                "clauseId": item.get("clauseId"),
                "originalClause": original_clause,
                "riskDescription": description,
                "possibleConsequence": item.get("possibleConsequence") or item.get("可能后果") or "",
                "legalBasis": basis,
                "legalArticleIds": [str(value) for value in legal_article_ids if value],
                "modificationAdvice": advice,
                "recommendedClause": item.get("recommendedClause") or item.get("推荐条款") or "",
                "confidence": item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else 0.6,
                "风险编号": item.get("风险编号") or f"A{index:03d}",
                "风险类别": item.get("风险类别") or item.get("类别") or "AI补充风险",
                "风险等级": level_cn,
                "短标题": item.get("短标题")
                or item.get("风险类别")
                or item.get("类别")
                or "AI风险",
                "风险标题": risk_name,
                "相关条款": original_clause,
                "问题说明": description,
                "可能后果": item.get("possibleConsequence") or item.get("可能后果") or "",
                "审查依据": "待后端校验模型返回的法律依据",
                "修改方向": advice,
                "推荐条款": item.get("recommendedClause") or item.get("推荐条款") or "",
                "legal_basis": basis,
                "来源": "AI增强审查",
            }
        )
    return result


def _risk_summary(findings: list[dict[str, Any]]) -> dict[str, Any]:
    overall = "低风险"
    if any(item.get("风险等级") in {"高", "严重"} for item in findings):
        overall = "高风险"
    elif any(item.get("风险等级") == "中" for item in findings):
        overall = "中风险"
    return {
        "总体风险等级": overall,
        "风险数量": len(findings),
        "高风险数量": sum(1 for item in findings if item.get("风险等级") in {"高", "严重"}),
        "中风险数量": sum(1 for item in findings if item.get("风险等级") == "中"),
        "低风险数量": sum(1 for item in findings if item.get("风险等级") == "低"),
    }


async def compliance_checker_node(state: ContractReviewState) -> dict:
    emit_stage(state, "LLM_REVIEW")
    text = state.get("raw_text", "")
    fields = state.get("extracted_fields", {})
    llm_config = state.get("llm_config")
    contract_type = state.get("contract_type", "general")
    findings = list(state.get("compliance_findings", []))
    if not findings:
        settings = get_settings()
        registry = RuleCenterService(
            settings.rule_center_data_dir,
            settings.risk_feedback_data_dir,
        ).configured_registry(contract_type)
        deterministic = RuleEngine(registry).evaluate(text, contract_type)
        findings = [_rule_match_to_legacy(match, index) for index, match in enumerate(deterministic, 1)]

    llm_result = await call_llm_json(
        state.get("prompt_templates", {}).get(
            "compliance", "你是企业合同合规审查专家。请只输出 JSON，不要输出 Markdown。"
        ),
        f"""
请基于合同文本、结构化要素、规则审查结果和系统提供的已核验法律条文，补充识别遗漏风险。
你只能从“可选法律依据”中选择 legalArticleId；不得自行生成、改写或猜测法律名称、条号和来源。
没有可靠匹配时 legalArticleIds 必须为空数组。riskLevel 只能使用 HIGH、MEDIUM、LOW。
输出 JSON：
{{
  "风险点": [
    {{
      "hasRisk": true,
      "riskLevel": "HIGH/MEDIUM/LOW",
      "riskName": "",
      "clauseId": "",
      "originalClause": "",
      "riskDescription": "",
      "possibleConsequence": "",
      "legalArticleIds": [],
      "modificationAdvice": "",
      "recommendedClause": "",
      "confidence": 0.0,
      "风险类别": "付款结算/验收/违约责任/知识产权/保密义务/解除终止/争议解决/其他"
    }}
  ]
}}

结构化要素：
{json.dumps(fields, ensure_ascii=False)}

规则审查已发现风险：
{json.dumps(findings, ensure_ascii=False)}

可选法律依据（只允许返回其中的 legalArticleId；为空时不得引用法律）：
{json.dumps([item for item in state.get("knowledge_hits", []) if item.get("legalArticleId")], ensure_ascii=False)}

当前合同条款（clauseId 只允许从以下 id 中选择）：
{json.dumps(state.get("contract_clauses", []), ensure_ascii=False)}

合同文本：
{text}
""",
        llm_config=llm_config,
        agent_role="compliance",
    )
    if llm_result:
        findings.extend(_normalize_llm_findings(llm_result, len(findings) + 1))

    summary = _risk_summary(findings)
    trace = state.get("agent_trace", []) + [
        {
            "节点": "合规审查 Agent",
            "动作": "对照企业内控和合同审查规则识别风险",
            "输出": f"发现 {summary['风险数量']} 个风险点，整体为{summary['总体风险等级']}",
            "状态": "完成",
            "时间": datetime.now(timezone.utc).isoformat(),
        }
    ]
    return {"compliance_findings": findings, "risk_summary": summary, "agent_trace": trace}
