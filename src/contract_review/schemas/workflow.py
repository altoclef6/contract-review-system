from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WorkflowStep(StrEnum):
    uploaded = "uploaded"
    ai_review = "ai_review"
    legal_review = "legal_review"
    manager_review = "manager_review"
    archived = "archived"
    rejected = "rejected"


class WorkflowAction(StrEnum):
    start_ai_review = "start_ai_review"
    ai_completed = "ai_completed"
    approve = "approve"
    reject = "reject"
    resubmit = "resubmit"


class WorkflowCreate(BaseModel):
    contract_id: str = Field(min_length=1, max_length=120)
    review_id: str | None = Field(default=None, max_length=120)


class WorkflowActionRequest(BaseModel):
    action: WorkflowAction
    comment: str | None = Field(default=None, max_length=1000)


class WorkflowEvent(BaseModel):
    step: WorkflowStep
    action: WorkflowAction | str
    actor_id: str
    actor_role: str
    comment: str | None = None
    created_at: datetime


class WorkflowPublic(BaseModel):
    id: str
    contract_id: str
    review_id: str | None = None
    submitter_id: str
    current_step: WorkflowStep
    status: str
    history: list[WorkflowEvent]
    created_at: datetime
    updated_at: datetime
