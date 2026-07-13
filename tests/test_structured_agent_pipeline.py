import asyncio

from contract_review.agents.classifier import contract_classifier_node
from contract_review.agents.validator import validator_node
from contract_review.graph.graph_builder import build_contract_review_graph


def test_classifier_returns_structured_confidence() -> None:
    result = asyncio.run(
        contract_classifier_node(
            {"raw_text": "软件开发合同，双方确认源代码和需求规格。", "contract_type": "general"}
        )
    )
    assert result["contract_type"] == "software_development"
    assert 0 <= result["classification"]["confidence"] <= 1
    assert result["classification"]["requires_human_selection"] is False


def test_validator_deduplicates_and_requires_review_for_high_risk() -> None:
    finding = {
        "风险标题": "赔偿责任无上限",
        "风险等级": "高",
        "相关条款": "赔偿不设上限",
        "来源": "deterministic_rule",
        "rule_id": "R023",
    }
    result = asyncio.run(validator_node({"compliance_findings": [finding, finding]}))
    assert len(result["compliance_findings"]) == 1
    assert result["compliance_findings"][0]["requires_human_review"] is True
    assert result["node_telemetry"][0]["node_name"] == "validator"


def test_graph_contains_separated_responsibility_nodes() -> None:
    graph = build_contract_review_graph()
    node_names = set(graph.get_graph().nodes)
    assert {
        "classifier",
        "extractor",
        "rule_checker",
        "knowledge_retriever",
        "compliance_checker",
        "validator",
        "refiner",
        "coordinator",
    }.issubset(node_names)
