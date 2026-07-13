from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardMetrics(BaseModel):
    monthly_review_count: int = Field(description="UTC 自然月内完成的审查记录数")
    monthly_high_risk_contract_count: int = Field(
        description="UTC 自然月内总体风险为高或严重的审查记录数；当前统计单位为审查记录"
    )
    pending_human_review_risk_count: int | None = Field(
        description="待人工复核风险数；风险复核状态未持久化时返回 null"
    )
    average_review_duration_ms: float | None = Field(
        description="UTC 自然月内具有有效 duration_ms 的已完成审查平均耗时"
    )


class DashboardTrendPoint(BaseModel):
    date: str = Field(description="UTC 日期，格式 YYYY-MM-DD")
    count: int


class DashboardDistributionItem(BaseModel):
    key: str
    label: str
    value: int = Field(ge=0)


class DashboardRuleItem(BaseModel):
    rule_id: str
    title: str
    count: int = Field(ge=1)


class DashboardRecentTask(BaseModel):
    review_id: str
    contract_name: str
    contract_type: str
    status: str
    risk_level: str | None = None
    started_at: datetime | None = None
    duration_ms: int | None = None


class DashboardTodoItem(BaseModel):
    id: str
    source: str
    title: str
    description: str
    status: str
    updated_at: datetime
    action_path: str


class DashboardSummary(BaseModel):
    generated_at: datetime
    time_zone: str = "UTC"
    scope: str
    metrics: DashboardMetrics
    review_trend_30d: list[DashboardTrendPoint]
    risk_level_distribution: list[DashboardDistributionItem]
    contract_type_distribution: list[DashboardDistributionItem]
    top_risk_rules: list[DashboardRuleItem] | None
    recent_tasks: list[DashboardRecentTask]
    todos: list[DashboardTodoItem]
    unavailable_reasons: dict[str, str] = Field(default_factory=dict)
    statistics_notes: list[str] = Field(default_factory=list)
