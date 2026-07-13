
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskSeverity = Literal["low", "medium", "high", "critical"]


class RuleUpdate(BaseModel):
    enabled: bool | None = None
    severity: RiskSeverity | None = None
    contract_types: list[str] | None = None
    recommendation: str | None = Field(default=None, max_length=2000)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    business_description: str | None = Field(default=None, max_length=2000)


class RuleRecord(BaseModel):
    rule_id: str
    name: str
    category: str
    contract_types: list[str]
    severity: RiskSeverity
    detection_method: str
    enabled: bool
    version: int
    description: str
    match_logic_summary: str
    exclusion_logic_summary: str
    recommendation: str
    test_samples: list[str]
    hit_count: int | None = None
    confirmed_count: int | None = None
    rejected_count: int | None = None
    confirmation_rate: float | None = None
    updated_at: datetime


class RuleListResponse(BaseModel):
    items: list[RuleRecord]
    total: int
