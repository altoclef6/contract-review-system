from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AgentTaskStatus(StrEnum):
    created = "created"
    planning = "planning"
    running = "running"
    waiting_confirmation = "waiting_confirmation"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgentTaskCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=80)
    objective: str = Field(min_length=1, max_length=2000)
    contract_id: str | None = None
    context: dict = Field(default_factory=dict)


class AgentStepPublic(BaseModel):
    id: str
    sequence: int
    name: str
    status: str
    requires_confirmation: bool
    input_data: dict
    output_data: dict
    started_at: datetime | None
    finished_at: datetime | None


class AgentToolCallPublic(BaseModel):
    id: str
    step_id: str | None
    tool_name: str
    risk_level: str
    status: str
    arguments: dict
    output: dict
    confirmed_by: str | None
    confirmed_at: datetime | None


class AgentEventPublic(BaseModel):
    id: str
    event_type: str
    payload: dict
    created_at: datetime


class AgentTaskPublic(BaseModel):
    id: str
    company_id: str
    created_by: str
    contract_id: str | None
    task_type: str
    objective: str
    status: AgentTaskStatus
    current_step: int
    plan: list[dict]
    context: dict
    result: dict
    safe_error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[AgentStepPublic] = Field(default_factory=list)
    tool_calls: list[AgentToolCallPublic] = Field(default_factory=list)
    events: list[AgentEventPublic] = Field(default_factory=list)


class AgentConfirmation(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=500)


class AgentToolDefinition(BaseModel):
    name: str
    description: str
    risk_level: str
    requires_confirmation: bool
