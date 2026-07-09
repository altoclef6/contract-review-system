from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from contract_review.graph.state import ContractReviewState
from contract_review.llm.json_client import call_llm_json


def _draft_clause(finding: dict[str, Any]) -> str:
    category = finding.get("风险类别")
    if category == "主体信息":
        return "双方应在合同首页列明完整名称、统一社会信用代码、注册地址、联系人、联系方式及授权代表，并保证上述信息真实、准确、有效。"
    if category == "交易金额":
        return "本合同总价款为人民币【】元（含税/不含税），具体金额、税率、发票类型及价款构成以本合同及附件约定为准。"
    if category == "履行期限":
        return "本合同履行期限为自【】年【】月【】日起至【】年【】月【】日止；各阶段交付、验收及整改期限以双方确认的计划为准。"
    if category == "付款结算":
        return "甲方应在乙方完成对应交付并经甲方验收合格、收到合法有效发票及付款申请资料后【】个工作日内支付相应款项。"
    if category == "违约责任":
        return "任一方违反本合同约定的，应在收到守约方书面通知后【】日内改正；逾期未改正的，应按合同总价款【】%承担违约金，违约金不足以弥补损失的，还应赔偿守约方实际损失。"
    if category == "争议解决":
        return "因本合同引起或与本合同有关的争议，双方应先友好协商；协商不成的，任一方可向【合同签订地/被告住所地】有管辖权的人民法院提起诉讼。"
    if category == "保密义务":
        return "双方对在合同履行过程中知悉的商业秘密、技术资料、经营数据及其他非公开信息负有保密义务，未经披露方书面同意不得向第三方披露。"
    if category == "解除终止":
        return "出现重大违约、无法继续履行、不可抗力持续超过【】日等情形时，守约方有权书面通知解除合同；合同终止后双方应完成结算、资料返还和保密义务延续事项。"
    return "建议结合业务事实补充明确、可执行、可验收的合同条款。"


def _rule_suggestions(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "对应风险编号": finding.get("风险编号"),
            "风险类别": finding.get("风险类别"),
            "修改建议": finding.get("修改方向"),
            "建议条款": _draft_clause(finding),
            "来源": "规则生成",
        }
        for finding in findings
    ]


async def refiner_node(state: ContractReviewState) -> dict:
    findings = state.get("compliance_findings", [])
    llm_config = state.get("llm_config")
    suggestions = _rule_suggestions(findings)

    llm_result = await call_llm_json(
        "你是企业法务合同修改专家。请只输出 JSON，不要输出 Markdown。",
        f"""
请针对以下风险点生成更贴近合同语境的修改建议和参考条款。
输出 JSON：
{{
  "修改建议": [
    {{
      "对应风险编号": "",
      "风险类别": "",
      "修改建议": "",
      "建议条款": ""
    }}
  ]
}}

风险点：
{json.dumps(findings, ensure_ascii=False)}
""",
        max_chars=12000,
        llm_config=llm_config,
    )
    if isinstance(llm_result, dict) and isinstance(llm_result.get("修改建议"), list):
        ai_suggestions = []
        for item in llm_result["修改建议"]:
            if isinstance(item, dict):
                item["来源"] = "AI增强生成"
                ai_suggestions.append(item)
        if ai_suggestions:
            suggestions = ai_suggestions

    trace = state.get("agent_trace", []) + [
        {
            "节点": "反馈与修改 Agent",
            "动作": "根据风险点生成修改建议和参考条款",
            "输出": f"生成 {len(suggestions)} 条修改建议",
            "状态": "完成",
            "时间": datetime.now(timezone.utc).isoformat(),
        }
    ]
    return {"revision_suggestions": suggestions, "agent_trace": trace}
