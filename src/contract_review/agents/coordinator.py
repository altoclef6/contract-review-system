from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract_review.graph.state import ContractReviewState
from contract_review.services.knowledge_service import KnowledgeService
from contract_review.services.risk_scoring import calculate_risk_score


async def coordinator_node(state: ContractReviewState) -> dict[str, Any]:
    if state.get("final_report"):
        return {"next_step": "finish"}

    if "revision_suggestions" not in state:
        trace = state.get("agent_trace", []) + [
            {
                "节点": "协调者 Agent",
                "动作": "接收合同并启动审查流程",
                "输出": "已路由至提取者 Agent",
                "状态": "完成",
                "时间": datetime.now(timezone.utc).isoformat(),
            }
        ]
        return {"next_step": "extractor", "agent_trace": trace}

    findings = state.get("compliance_findings", [])
    risk_summary = state.get("risk_summary", {})
    extracted_fields = state.get("extracted_fields", {})
    risk_score = calculate_risk_score(findings)
    knowledge_hits = state.get("knowledge_hits") or KnowledgeService().retrieve(findings)
    overall_level = risk_summary.get("总体风险等级", "低风险")
    if risk_score.get("风险等级"):
        overall_level = risk_score["风险等级"]
    ai_used = (
        extracted_fields.get("提取方式") == "规则提取 + AI增强"
        or any(item.get("来源") == "AI增强审查" for item in findings)
        or any(item.get("来源") == "AI增强生成" for item in state.get("revision_suggestions", []))
    )

    summary = (
        f"本次审查共识别 {len(findings)} 个风险点，整体评估为{overall_level}。"
        "建议优先处理高风险和中风险条款，再进入正式签署或归档流程。"
        if findings
        else "本次审查未发现明显风险点，建议结合业务背景进行人工复核后再签署。"
    )
    trace = state.get("agent_trace", []) + [
        {
            "节点": "协调者 Agent",
            "动作": "汇总结构化要素、风险点、修改建议与依据检索",
            "输出": f"生成最终报告，整体风险为{overall_level}",
            "状态": "完成",
            "时间": datetime.now(timezone.utc).isoformat(),
        }
    ]

    final_report = {
        "审查编号": state.get("review_id"),
        "文件名": state.get("file_name"),
        "生成时间": datetime.now(timezone.utc).isoformat(),
        "总体风险等级": overall_level,
        "风险评分": risk_score,
        "风险统计": risk_summary,
        "审查摘要": summary,
        "依据检索": knowledge_hits,
        "AI增强": "已启用" if ai_used else "未启用或调用失败，已使用规则审查结果",
        "结构化提取结果": extracted_fields,
        "风险点": findings,
        "修改建议": state.get("revision_suggestions", []),
        "Agent协同轨迹": trace,
        "人工复核提示": "本系统输出用于辅助合同初审，正式签署前仍需由业务负责人或法务人员结合交易背景复核。",
    }
    return {"final_report": final_report, "next_step": "finish", "agent_trace": trace}
