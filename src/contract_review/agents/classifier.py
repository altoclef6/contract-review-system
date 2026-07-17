from __future__ import annotations

from typing import Any, Literal, cast

from contract_review.graph.state import ContractReviewState
from contract_review.schemas.agent import ContractClassification

ContractType = Literal[
    "software_development",
    "technical_service",
    "information_system",
    "software_outsourcing",
    "general",
]


async def contract_classifier_node(state: ContractReviewState) -> dict[str, Any]:
    text = state.get("raw_text", "")[:5000]
    indicators = {
        "software_development": ["软件开发", "源代码", "需求规格"],
        "technical_service": ["技术服务", "服务成果", "服务期限"],
        "information_system": ["信息系统", "系统建设", "项目建设"],
        "software_outsourcing": ["软件外包", "外包开发", "驻场开发"],
    }
    scores = {kind: sum(keyword in text for keyword in keywords) for kind, keywords in indicators.items()}
    selected_value, score = max(scores.items(), key=lambda item: item[1])
    selected = cast(ContractType, selected_value)
    if score == 0:
        selected = "general"
    confidence = min(0.95, 0.45 + score * 0.2) if score else 0.2
    classification = ContractClassification(
        contract_type=selected,
        confidence=confidence,
        requires_human_selection=confidence < 0.6,
        evidence=[keyword for keyword in indicators.get(selected, []) if keyword in text],
    )
    requested = state.get("contract_type", "general")
    contract_type = requested if requested != "general" else classification.contract_type
    return {"contract_type": contract_type, "classification": classification.model_dump()}
