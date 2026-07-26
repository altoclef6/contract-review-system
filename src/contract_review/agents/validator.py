from __future__ import annotations

from time import perf_counter
from typing import Any

from contract_review.graph.state import ContractReviewState, emit_stage
from contract_review.schemas.agent import NodeTelemetry, ValidatorOutput, utcnow


async def validator_node(state: ContractReviewState) -> dict[str, Any]:
    emit_stage(state, "VALIDATING_RESULT")
    started_at = utcnow()
    started = perf_counter()
    seen: set[tuple[str, str]] = set()
    validated: list[dict[str, Any]] = []
    rejected = downgraded = 0
    for raw in state.get("compliance_findings", []):
        item = dict(raw)
        key = (str(item.get("rule_id") or item.get("风险标题")), str(item.get("相关条款", "")))
        if key in seen:
            rejected += 1
            continue
        seen.add(key)
        if not str(item.get("相关条款", "")).strip() and item.get("来源") != "deterministic_rule":
            item["requires_human_review"] = True
            item["风险等级"] = "中" if item.get("风险等级") in {"高", "严重"} else item.get("风险等级", "中")
            downgraded += 1
        if item.get("风险等级") in {"高", "严重"}:
            item["requires_human_review"] = True
        validated.append(item)
    telemetry = NodeTelemetry(
        node_name="validator",
        started_at=started_at,
        ended_at=utcnow(),
        duration_ms=(perf_counter() - started) * 1000,
        status="degraded" if downgraded else "completed",
    )
    output = ValidatorOutput(
        findings=validated,
        rejected_count=rejected,
        downgraded_count=downgraded,
        telemetry=telemetry,
    )
    return {
        "compliance_findings": output.findings,
        "node_telemetry": state.get("node_telemetry", []) + [telemetry.model_dump()],
    }
