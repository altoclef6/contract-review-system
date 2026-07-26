from __future__ import annotations

from typing import Any, Literal

from contract_review.core.config import get_settings
from contract_review.graph.state import ContractReviewState
from contract_review.llm.json_client import call_llm_json
from contract_review.schemas.agent import ContractClassification
from contract_review.services.prompt_template_service import PromptTemplateService

ContractType = Literal[
    "software_development",
    "technical_service",
    "information_system",
    "software_outsourcing",
    "procurement",
    "sales",
    "labor",
    "lease",
    "nda",
    "service",
    "other",
    "general",
]

SUPPORTED_TYPES: tuple[ContractType, ...] = (
    "software_development",
    "technical_service",
    "information_system",
    "software_outsourcing",
    "procurement",
    "sales",
    "labor",
    "lease",
    "nda",
    "service",
    "other",
    "general",
)

TYPE_INDICATORS: dict[ContractType, tuple[str, ...]] = {
    "software_development": ("软件开发", "源代码", "需求规格", "软件著作权", "里程碑交付"),
    "technical_service": ("技术服务", "技术咨询", "服务成果", "技术方案", "服务期限"),
    "information_system": ("信息系统", "系统建设", "项目建设", "系统集成", "验收测试"),
    "software_outsourcing": ("软件外包", "外包开发", "驻场开发", "人员外包", "外包服务"),
    "procurement": ("采购合同", "采购方", "供应商", "采购订单", "货物验收"),
    "sales": ("销售合同", "销售方", "买方", "卖方", "销售价格"),
    "labor": ("劳动合同", "用人单位", "劳动者", "试用期", "社会保险"),
    "lease": ("租赁合同", "出租人", "承租人", "租赁期限", "租金"),
    "nda": ("保密协议", "保密义务", "保密信息", "商业秘密", "竞业限制"),
    "service": ("服务合同", "服务内容", "服务费用", "服务标准", "服务期限"),
}

REQUEST_ALIASES = {"purchase": "procurement", "employment": "labor"}


def _heuristic_classification(text: str) -> ContractClassification:
    scores = {
        kind: sum(1 for keyword in keywords if keyword in text)
        for kind, keywords in TYPE_INDICATORS.items()
    }
    selected_value, score = max(scores.items(), key=lambda item: item[1])
    selected = selected_value
    if score == 0:
        selected = "other"
    evidence = [keyword for keyword in TYPE_INDICATORS.get(selected, ()) if keyword in text]
    confidence = min(0.96, 0.48 + score * 0.13) if score else 0.25
    return ContractClassification(
        contract_type=selected,
        confidence=confidence,
        requires_human_selection=confidence < 0.6,
        evidence=evidence[:6],
        method="content_heuristic",
    )


async def _llm_classification(
    text: str, llm_config: dict[str, Any]
) -> ContractClassification | None:
    response = await call_llm_json(
        "你是合同类型分类器。只依据合同原文分类，不提供法律意见。输出严格 JSON。",
        (
            "请从以下类型中选择一个："
            f"{', '.join(SUPPORTED_TYPES)}。"
            "返回 contract_type、confidence(0到1)、evidence(原文中的短语数组)。\n\n"
            f"合同原文：\n{text[:8000]}"
        ),
        max_chars=10000,
        llm_config=llm_config,
    )
    if not isinstance(response, dict):
        return None
    contract_type = str(response.get("contract_type") or "")
    if contract_type not in SUPPORTED_TYPES:
        return None
    raw_confidence = response.get("confidence")
    if not isinstance(raw_confidence, (int, float)):
        return None
    raw_evidence = response.get("evidence")
    evidence = (
        [str(item)[:80] for item in raw_evidence if isinstance(item, str)][:6]
        if isinstance(raw_evidence, list)
        else []
    )
    confidence = max(0.0, min(1.0, float(raw_confidence)))
    return ContractClassification(
        contract_type=contract_type,
        confidence=confidence,
        requires_human_selection=confidence < 0.6,
        evidence=evidence,
        method="llm",
    )


async def contract_classifier_node(state: ContractReviewState) -> dict[str, Any]:
    text = state.get("raw_text", "")
    llm_config = state.get("llm_config", {})
    classification = await _llm_classification(text, llm_config)
    classification = classification or _heuristic_classification(text)
    requested = REQUEST_ALIASES.get(
        state.get("contract_type", "auto"), state.get("contract_type", "auto")
    )
    override_applied = requested not in {"", "auto", "general"}
    contract_type = requested if override_applied else classification.contract_type
    classification.override_applied = override_applied
    settings = get_settings()
    prompt_templates = PromptTemplateService(settings.prompt_template_data_dir).resolve(
        contract_type
    )
    return {
        "contract_type": contract_type,
        "classification": classification.model_dump(),
        "prompt_templates": prompt_templates,
    }
