from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskSource(StrEnum):
    deterministic_rule = "deterministic_rule"
    knowledge_retrieval = "knowledge_retrieval"
    llm_analysis = "llm_analysis"
    human_review = "human_review"


class RiskStatus(StrEnum):
    pending_review = "pending_review"
    confirmed = "confirmed"
    rejected = "rejected"
    remediating = "remediating"
    remediated = "remediated"
    closed = "closed"


class RiskComment(BaseModel):
    comment_id: str
    author_id: str
    content: str
    created_at: datetime


class RiskStateEvent(BaseModel):
    event_id: str
    actor_id: str
    old_status: RiskStatus | None = None
    new_status: RiskStatus
    reason: str | None = None
    created_at: datetime


class RiskRecord(BaseModel):
    risk_id: str
    source_risk_id: str | None = None
    contract_id: str | None = None
    contract_version_id: str | None = None
    review_id: str
    severity: str
    category: str
    title: str
    matched_text: str
    normalized_text: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    page_number: int | None = None
    paragraph_index: int | None = None
    bounding_box: list[float] | None = None
    rule_id: str | None = None
    knowledge_document_ids: list[str] = Field(default_factory=list)
    legal_basis: list[dict[str, Any]] = Field(default_factory=list)
    detection_source: RiskSource
    ai_involved: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    risk_score: float = Field(default=0, ge=0, le=100)
    explanation: str
    recommendation: str
    status: RiskStatus = RiskStatus.pending_review
    assignee_id: str | None = None
    reviewer_id: str | None = None
    review_comment: str | None = None
    revised_clause: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
    resolved_at: datetime | None = None
    revision: int = 1
    state_history: list[RiskStateEvent] = Field(default_factory=list)
    comments: list[RiskComment] = Field(default_factory=list)
    contract_title: str | None = None
    contract_type: str | None = None
    contract_version: int | None = None
    assignee_name: str | None = None


class RiskListResponse(BaseModel):
    items: list[RiskRecord]
    total: int
    page: int
    page_size: int


class RiskTransitionRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class RiskAssignRequest(BaseModel):
    assignee_id: str | None = Field(default=None, max_length=64)
    expected_revision: int = Field(ge=1)


class RiskCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    expected_revision: int = Field(ge=1)


class RiskRevisionRequest(BaseModel):
    revised_clause: str = Field(min_length=1, max_length=10000)
    expected_revision: int = Field(ge=1)


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
    status: RiskStatus = RiskStatus.pending_review
    reviewer_comment: str | None = None
    ai_original_recommendation: str | None = None
    human_final_opinion: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
