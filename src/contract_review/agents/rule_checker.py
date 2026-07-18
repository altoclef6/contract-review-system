from __future__ import annotations

from time import perf_counter
from typing import Any

from contract_review.agents.compliance_checker import _rule_match_to_legacy
from contract_review.graph.state import ContractReviewState, emit_stage
from contract_review.rules import RuleEngine, default_registry
from contract_review.schemas.agent import NodeTelemetry, RuleCheckerOutput, utcnow


async def rule_checker_node(state: ContractReviewState) -> dict[str, Any]:
    emit_stage(state, "RULE_REVIEW")
    started_at = utcnow()
    started = perf_counter()
    matches = RuleEngine(default_registry()).evaluate(
        state.get("raw_text", ""), state.get("contract_type", "general")
    )
    findings = [_rule_match_to_legacy(match, index) for index, match in enumerate(matches, 1)]
    output = RuleCheckerOutput(
        findings=findings,
        rule_count=len(default_registry()),
        telemetry=NodeTelemetry(
            node_name="rule_checker",
            started_at=started_at,
            ended_at=utcnow(),
            duration_ms=(perf_counter() - started) * 1000,
            status="completed",
        ),
    )
    return {
        "compliance_findings": output.findings,
        "node_telemetry": state.get("node_telemetry", []) + [output.telemetry.model_dump()],
    }
