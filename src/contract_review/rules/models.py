from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ConditionType(StrEnum):
    keyword = "keyword"
    regex = "regex"
    missing = "missing"
    numeric = "numeric"
    all = "all"
    any = "any"


class RuleDefinition(BaseModel):
    rule_id: str
    rule_name: str
    description: str
    contract_type: str = "all"
    category: str
    severity: Severity
    enabled: bool = True
    version: str = "1.0.0"
    condition_type: ConditionType
    condition: dict[str, Any]
    explanation: str
    recommendation: str
    suggested_revision_template: str | None = None
    legal_basis_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuleMatch(BaseModel):
    rule_id: str
    rule_name: str
    category: str
    severity: Severity
    risk_score: float
    source: str = "deterministic_rule"
    confidence: float = 1.0
    contract_text: str
    normalized_text: str
    page_number: int | None = None
    paragraph_index: int | None = None
    clause_number: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    bounding_box: list[float] | None = None
    explanation: str
    legal_basis: list[str] = Field(default_factory=list)
    recommendation: str
    suggested_revision: str | None = None
    requires_human_review: bool
    status: str = "pending"
    execution_ms: float = 0.0
