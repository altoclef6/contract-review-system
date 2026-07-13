
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TextChangeType(StrEnum):
    added = "added"
    removed = "removed"
    modified = "modified"
    unchanged = "unchanged"


class RiskChangeStatus(StrEnum):
    added = "added"
    removed = "removed"
    unchanged = "unchanged"
    severity_increased = "severity_increased"
    severity_decreased = "severity_decreased"
    text_changed = "text_changed"
    remediated = "remediated"
    uncertain_match = "uncertain_match"


class VersionCompareRequest(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=120)
    target_version_id: str = Field(min_length=1, max_length=120)


class TextDiffSegment(BaseModel):
    change_type: TextChangeType
    base_index: int | None = None
    target_index: int | None = None
    base_text: str = ""
    target_text: str = ""


class RiskComparison(BaseModel):
    status: RiskChangeStatus
    match_score: float | None = None
    base_risk: dict[str, Any] | None = None
    target_risk: dict[str, Any] | None = None
    explanation: str


class VersionComparisonResult(BaseModel):
    contract_id: str
    base_version_id: str
    target_version_id: str
    text_segments: list[TextDiffSegment]
    risk_changes: list[RiskComparison]
    summary: dict[str, int]


class FeedbackType(StrEnum):
    confirmed_risk = "confirmed_risk"
    not_a_risk = "not_a_risk"
    inaccurate_severity = "inaccurate_severity"
    unusable_suggestion = "unusable_suggestion"


class RiskFeedbackCreate(BaseModel):
    contract_id: str = Field(min_length=1, max_length=120)
    contract_version_id: str = Field(min_length=1, max_length=120)
    risk_id: str = Field(min_length=1, max_length=160)
    rule_id: str | None = Field(default=None, max_length=160)
    contract_type: str | None = Field(default=None, max_length=80)
    feedback_type: FeedbackType
    suggested_severity: str | None = Field(
        default=None, pattern="^(low|medium|high|critical|低|中|高|严重)$"
    )
    reason: str | None = Field(default=None, max_length=2000)


class RiskFeedbackRecord(RiskFeedbackCreate):
    id: str
    actor_id: str
    created_at: datetime


class FeedbackStatistics(BaseModel):
    total: int
    confirmed_count: int
    rejected_count: int
    confirmation_rate: float | None = None
    rejection_rate: float | None = None
    severity_adjustment_count: int
    unusable_suggestion_count: int
    by_contract_type: dict[str, int]
    by_rule: dict[str, dict[str, int | float | None]]
    by_date: dict[str, int]
    recent_feedback: list[RiskFeedbackRecord]
