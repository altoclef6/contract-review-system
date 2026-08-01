from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class NodeTelemetry(BaseModel):
    node_name: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0)
    input_tokens: int | None = None
    output_tokens: int | None = None
    model_name: str | None = None
    cost: float | None = None
    retry_count: int = 0
    status: Literal["completed", "degraded", "failed"]


class ContractClassification(BaseModel):
    contract_type: Literal[
        "software_development",
        "technical_service",
        "information_system",
        "software_outsourcing",
        "general",
    ]
    confidence: float = Field(ge=0, le=1)
    requires_human_selection: bool
    evidence: list[str] = Field(default_factory=list)


class RuleCheckerOutput(BaseModel):
    findings: list[dict[str, Any]]
    rule_count: int
    telemetry: NodeTelemetry


class KnowledgeRetrieverOutput(BaseModel):
    hits: list[dict[str, Any]]
    degraded: bool = False
    telemetry: NodeTelemetry


class ValidatorOutput(BaseModel):
    findings: list[dict[str, Any]]
    rejected_count: int = 0
    downgraded_count: int = 0
    telemetry: NodeTelemetry


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
