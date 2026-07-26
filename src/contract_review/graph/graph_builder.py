from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from contract_review.agents.classifier import contract_classifier_node
from contract_review.agents.compliance_checker import compliance_checker_node
from contract_review.agents.coordinator import coordinator_node
from contract_review.agents.extractor import extractor_node
from contract_review.agents.knowledge_retriever import knowledge_retriever_node
from contract_review.agents.refiner import refiner_node
from contract_review.agents.rule_checker import rule_checker_node
from contract_review.agents.validator import validator_node
from contract_review.graph.routing import route_after_coordinator
from contract_review.graph.state import ContractReviewState


def build_contract_review_graph() -> Any:
    """Build the core LangGraph topology for contract review.

    Topology:
        Coordinator -> Extractor -> Compliance Checker -> Refiner -> Coordinator -> END

    Concrete agent prompts and model calls are intentionally isolated in agent modules.
    This builder only wires graph nodes and routing behavior.
    """
    graph = StateGraph(ContractReviewState)

    graph.add_node("coordinator", coordinator_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("classifier", contract_classifier_node)
    graph.add_node("rule_checker", rule_checker_node)
    graph.add_node("knowledge_retriever", knowledge_retriever_node)
    graph.add_node("compliance_checker", compliance_checker_node)
    graph.add_node("refiner", refiner_node)
    graph.add_node("validator", validator_node)

    graph.add_edge(START, "coordinator")
    graph.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {
            "extractor": "classifier",
            "finish": END,
        },
    )
    graph.add_edge("classifier", "extractor")
    graph.add_edge("extractor", "rule_checker")
    graph.add_edge("rule_checker", "knowledge_retriever")
    graph.add_edge("knowledge_retriever", "compliance_checker")
    graph.add_edge("compliance_checker", "validator")
    graph.add_edge("validator", "refiner")
    graph.add_edge("refiner", "coordinator")

    return graph.compile()
