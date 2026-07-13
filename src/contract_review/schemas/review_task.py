from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReviewTaskStatus(StrEnum):
    pending = "PENDING"
    validating = "VALIDATING"
    parsing = "PARSING"
    extracting = "EXTRACTING"
    rule_review = "RULE_REVIEW"
    knowledge_retrieval = "KNOWLEDGE_RETRIEVAL"
    llm_review = "LLM_REVIEW"
    validating_result = "VALIDATING_RESULT"
    persisting_risks = "PERSISTING_RISKS"
    generating_report = "GENERATING_REPORT"
    completed = "COMPLETED"
    failed = "FAILED"
    cancelled = "CANCELLED"


TERMINAL_REVIEW_TASK_STATUSES = {
    ReviewTaskStatus.completed,
    ReviewTaskStatus.failed,
    ReviewTaskStatus.cancelled,
}


class ReviewTaskCreate(BaseModel):
    contract_id: str | None = Field(default=None, max_length=120)
    contract_version_id: str | None = Field(default=None, max_length=120)
    contract_type: str = Field(default="general", max_length=60)
    file_path: str | None = Field(default=None, max_length=1000)
    original_file_name: str | None = Field(default=None, max_length=260)
    content_type: str | None = Field(default=None, max_length=120)
    provider: str | None = Field(default=None, max_length=80)
    model_name: str | None = Field(default=None, max_length=160)
    idempotency_key: str | None = Field(default=None, max_length=160)


class ReviewTaskRecord(BaseModel):
    task_id: str
    contract_id: str | None = None
    contract_version_id: str | None = None
    requested_by: str
    status: ReviewTaskStatus
    current_stage: ReviewTaskStatus
    progress: int | None = None
    idempotency_key: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    retry_count: int = 0
    provider: str | None = None
    model_name: str | None = None
    error_code: str | None = None
    safe_error_message: str | None = None
    celery_task_id: str | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ReviewTaskListResponse(BaseModel):
    items: list[ReviewTaskRecord]
    total: int
    page: int
    page_size: int


class ReviewTaskEvent(BaseModel):
    status: ReviewTaskStatus
    stage: ReviewTaskStatus
    message: str
    created_at: datetime
