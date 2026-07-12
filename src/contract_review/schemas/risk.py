from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RiskSource(StrEnum):
    deterministic_rule = "deterministic_rule"
    knowledge_retrieval = "knowledge_retrieval"
    llm_analysis = "llm_analysis"
    human_review = "human_review"


class RiskStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    modified = "modified"
    resolved = "resolved"


class ExplainableRisk(BaseModel):
    risk_id: str
    contract_id: str | None = None
    review_task_id: str
    title: str
    category: str
    severity: str
    risk_score: float = Field(ge=0, le=100)
    source: RiskSource
    confidence: float = Field(ge=0, le=1)
    contract_text: str
    normalized_text: str
    page_number: int | None = None
    paragraph_index: int | None = None
    clause_number: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    bounding_box: list[float] | None = None
    explanation: str
    legal_basis: list[dict[str, str]] = Field(default_factory=list)
    recommendation: str
    suggested_revision: str | None = None
    requires_human_review: bool
    agent_name: str | None = None
    rule_id: str | None = None
    knowledge_document_ids: list[str] = Field(default_factory=list)
    status: RiskStatus = RiskStatus.pending
    reviewer_comment: str | None = None
    ai_original_recommendation: str | None = None
    human_final_opinion: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
