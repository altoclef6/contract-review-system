from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalysisRecord(BaseModel):
    review_id: str
    file_name: str
    contract_type: str = "general"
    created_at: datetime
    duration_ms: int | None = None
    model_provider: str | None = None
    model_name: str | None = None
    prompt_snapshot: dict[str, str] = Field(default_factory=dict)
    token_usage: int | None = None
    source_file_path: str | None = None
    overall_risk_level: str | None = None
    risk_score: int | float | None = None
    safe_score: int | float | None = None
    risk_counts: dict[str, Any] = Field(default_factory=dict)
    ai_status: str | None = None
    report_path: str | None = None
    exports: dict[str, str] = Field(default_factory=dict)


class AnalysisHistoryPage(BaseModel):
    items: list[AnalysisRecord]
    total: int
    page: int
    page_size: int


class AnalysisStatistics(BaseModel):
    total_reviews: int
    average_risk_score: float
    average_duration_ms: float
    risk_levels: dict[str, int]
    contract_types: dict[str, int]
    models: dict[str, int]
