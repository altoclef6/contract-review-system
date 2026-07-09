from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from contract_review.graph.state import ContractReviewState
from contract_review.llm.json_client import call_llm_json


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
        findings.append(_finding(len(findings) + 1, "主体信息", "高", "合同主体信息不完整", "未识别到至少两个明确合同主体，可能影响权利义务归属。", "补充双方完整名称、统一社会信用代码、注册地址、联系人及授权代表。", "企业合同内控要求签约主体信息完整、可核验。"))
    if not amounts:
        findings.append(_finding(len(findings) + 1, "交易金额", "中", "合同金额不明确", "未识别到明确金额或价款计算方式，容易导致结算争议。", "明确合同总价、税率、含税口径、付款节点和结算依据。", "企业付款审批要求合同金额和付款依据清晰。"))
    if not periods:
        findings.append(_finding(len(findings) + 1, "履行期限", "中", "履行期限不明确", "未识别到清晰起止时间或交付期限。", "增加合同生效时间、履行期限、交付节点、验收时间和延期机制。", "履约管理要求期限和验收条件可执行。"))
    if not payment_clauses:
        findings.append(_finding(len(findings) + 1, "付款结算", "中", "付款条款缺失或不清晰", "未识别到付款方式、付款条件、发票要求或结算节点。", "补充付款比例、付款时间、收款账户、发票类型、付款前置条件和逾期处理。", "资金支付内控要求付款节点与验收、发票、审批材料匹配。"))
    if not liability_clauses:
        findings.append(_finding(len(findings) + 1, "违约责任", "高", "缺少明确违约责任", "未明确违约行为、违约金或损失赔偿范围。", "明确逾期交付、逾期付款、质量不合格、保密违约等责任承担方式。", "关键义务必须匹配可执行的违约责任。"))
    elif not any(("违约金" in clause or "%" in clause or "每日" in clause) for clause in liability_clauses):
        findings.append(_finding(len(findings) + 1, "违约责任", "中", "违约责任量化不足", "已识别到违约责任条款，但缺少违约金比例、计算方式或赔偿范围。", "增加违约金计算标准，并说明违约金不足以弥补损失时的补充赔偿机制。", "违约责任应具备可计算性和可执行性。", str(liability_clauses[0])))
    if not dispute_clauses:
        findings.append(_finding(len(findings) + 1, "争议解决", "中", "缺少争议解决条款", "未明确争议解决方式和管辖机构。", "明确协商、诉讼或仲裁方式，并约定有管辖权的法院或仲裁委员会。", "争议管理要求管辖条款明确、合法、便于执行。"))
    if "保密" in text and not confidentiality_clauses:
        findings.append(_finding(len(findings) + 1, "保密义务", "低", "保密条款表达不充分", "出现保密表述，但保密范围、期限和违约责任不完整。", "补充保密信息范围、期限、例外情形、返还销毁要求及违约责任。", "涉商业秘密或经营数据合同应明确保密义务。"))
    if not termination_clauses:
        findings.append(_finding(len(findings) + 1, "解除终止", "低", "解除或终止机制不明确", "未识别到解除、终止或不可抗力处理机制。", "增加解除条件、通知期限、终止后结算、资料返还和责任承担条款。", "合同生命周期管理要求退出机制清晰。"))
    return findings


def _normalize_llm_findings(data: dict[str, Any] | list[Any], start_index: int) -> list[dict[str, Any]]:
    items = data.get("风险点", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=start_index):
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "风险编号": item.get("风险编号") or f"A{index:03d}",
                "风险类别": item.get("风险类别") or item.get("类别") or "AI补充风险",
                "风险等级": item.get("风险等级") or item.get("等级") or "中",
                "短标题": item.get("短标题") or item.get("风险类别") or item.get("类别") or "AI风险",
                "风险标题": item.get("风险标题") or item.get("标题") or "AI识别风险",
                "相关条款": item.get("相关条款") or item.get("条款") or "",
                "问题说明": item.get("问题说明") or item.get("原因") or item.get("说明") or "",
                "审查依据": item.get("审查依据") or item.get("依据") or "AI结合合同文本和常见企业内控要求判断。",
                "修改方向": item.get("修改方向") or item.get("建议") or "",
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
    text = state.get("raw_text", "")
    fields = state.get("extracted_fields", {})
    llm_config = state.get("llm_config")
    findings = _rule_check(fields, text)

    llm_result = await call_llm_json(
        "你是企业合同合规审查专家。请只输出 JSON，不要输出 Markdown。",
        f"""
请基于合同文本和结构化要素，补充识别规则审查可能遗漏的合同风险。
风险等级只能使用：低、中、高、严重。
输出 JSON：
{{
  "风险点": [
    {{
      "风险类别": "",
      "风险等级": "低/中/高/严重",
      "短标题": "2到6个汉字，例如主体缺失、金额不清、责任不足",
      "风险标题": "",
      "相关条款": "",
      "问题说明": "",
      "审查依据": "",
      "修改方向": ""
    }}
  ]
}}

结构化要素：
{json.dumps(fields, ensure_ascii=False)}

规则审查已发现风险：
{json.dumps(findings, ensure_ascii=False)}

合同文本：
{text}
""",
        llm_config=llm_config,
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
