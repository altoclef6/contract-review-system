from __future__ import annotations

from time import perf_counter

from contract_review.graph.state import ContractReviewState, emit_stage
from contract_review.schemas.agent import KnowledgeRetrieverOutput, NodeTelemetry, utcnow
from contract_review.services.knowledge_service import KnowledgeService


async def knowledge_retriever_node(state: ContractReviewState) -> dict:
    emit_stage(state, "KNOWLEDGE_RETRIEVAL")
    started_at = utcnow()
    started = perf_counter()
    degraded = False
    try:
        hits = KnowledgeService().retrieve(state.get("compliance_findings", []))
    except (OSError, ValueError, TypeError):
        hits = []
        degraded = True
    output = KnowledgeRetrieverOutput(
        hits=hits,
        degraded=degraded,
        telemetry=NodeTelemetry(
            node_name="knowledge_retriever",
            started_at=started_at,
            ended_at=utcnow(),
            duration_ms=(perf_counter() - started) * 1000,
            status="degraded" if degraded else "completed",
        ),
    )
    return {
        "knowledge_hits": output.hits,
        "node_telemetry": state.get("node_telemetry", []) + [output.telemetry.model_dump()],
    }
