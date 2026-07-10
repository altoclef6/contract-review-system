from __future__ import annotations

from typing import Any

RISK_WEIGHTS = {
    "严重": 30,
    "高": 22,
    "中": 12,
    "低": 5,
}

CATEGORY_DIMENSIONS = {
    "主体信息": "主体与授权",
    "交易金额": "金额与结算",
    "付款结算": "金额与结算",
    "履行期限": "履约管理",
    "违约责任": "责任约束",
    "争议解决": "争议处理",
    "保密义务": "信息安全",
    "解除终止": "退出机制",
}


def calculate_risk_score(findings: list[dict[str, Any]]) -> dict[str, Any]:
    dimension_scores: dict[str, int] = {
        "主体与授权": 0,
        "金额与结算": 0,
        "履约管理": 0,
        "责任约束": 0,
        "争议处理": 0,
        "信息安全": 0,
        "退出机制": 0,
        "其他": 0,
    }

    total = 0
    for finding in findings:
        level = str(finding.get("风险等级", "低"))
        category = str(finding.get("风险类别", "其他"))
        weight = RISK_WEIGHTS.get(level, 8)
        dimension = CATEGORY_DIMENSIONS.get(category, "其他")
        dimension_scores[dimension] += weight
        total += weight

    risk_score = min(100, total)
    if risk_score >= 70:
        grade = "高风险"
        action = "建议暂缓签署，优先完成法务复核和条款修订。"
    elif risk_score >= 35:
        grade = "中风险"
        action = "建议修订关键条款后再进入签署流程。"
    else:
        grade = "低风险"
        action = "未发现明显高风险，但仍建议结合业务背景复核。"

    return {
        "风险分": risk_score,
        "安全分": max(0, 100 - risk_score),
        "风险等级": grade,
        "处置建议": action,
        "维度评分": dimension_scores,
        "评分说明": "风险分基于风险等级和风险类别加权计算，分值越高表示合同风险越集中。",
    }
