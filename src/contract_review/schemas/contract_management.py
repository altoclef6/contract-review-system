from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ContractCategory(StrEnum):
    software_development = "software_development"
    technical_service = "technical_service"
    information_system = "information_system"
    software_outsourcing = "software_outsourcing"
    procurement = "procurement"
    sales = "sales"
    labor = "labor"
    lease = "lease"
    nda = "nda"
    service = "service"
    other = "other"


class ContractStatus(StrEnum):
    draft = "draft"
    reviewing = "reviewing"
    legal_review = "legal_review"
    manager_review = "manager_review"
    archived = "archived"
    deleted = "deleted"


class ContractCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    category: ContractCategory = ContractCategory.other
    tags: list[str] = Field(default_factory=list, max_length=20)
    counterparty: str | None = Field(default=None, max_length=160)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default="CNY", min_length=3, max_length=3)
    file_name: str | None = Field(default=None, max_length=260)
    description: str | None = Field(default=None, max_length=1000)
    expires_at: datetime | None = None
    file_hash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    text_content: str | None = None


class ContractUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    category: ContractCategory | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    counterparty: str | None = Field(default=None, max_length=160)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: ContractStatus | None = None
    description: str | None = Field(default=None, max_length=1000)
    expires_at: datetime | None = None


class ContractVersionCreate(BaseModel):
    file_name: str = Field(min_length=1, max_length=260)
    change_note: str | None = Field(default=None, max_length=1000)
    review_id: str | None = Field(default=None, max_length=120)
    file_hash: str = Field(pattern="^[a-f0-9]{64}$")
    parent_version_id: str | None = Field(default=None, max_length=120)
    text_content: str | None = None
    risk_snapshot: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    version_type: Literal["original", "modified", "re_review", "final"] = "modified"


class ContractVersion(BaseModel):
    id: str
    version_no: int
    file_name: str
    change_note: str | None = None
    review_id: str | None = None
    created_at: datetime
    created_by: str
    file_hash: str | None = None
    parent_version_id: str | None = None
    text_content: str | None = Field(default=None, exclude=True)
    risk_snapshot: list[dict[str, Any]] = Field(default_factory=list, exclude=True)
    version_type: Literal["original", "modified", "re_review", "final"] = "original"
    content_type: str | None = None
    file_size: int | None = Field(default=None, ge=0)
    parse_status: Literal["pending", "ready", "failed", "unavailable"] = "unavailable"
    review_status: str | None = None
    risk_level: str | None = None
    file_path: str | None = Field(default=None, exclude=True)


class ClauseDiff(BaseModel):
    operation: Literal["added", "deleted", "unchanged"]
    text: str


class RiskRemediationMapping(BaseModel):
    risk_id: str
    status: Literal["unresolved", "partially_resolved", "resolved", "newly_introduced"]
    old_text: str
    new_text: str | None = None


class VersionComparison(BaseModel):
    from_version_id: str
    to_version_id: str
    clause_diffs: list[ClauseDiff]
    risk_mappings: list[RiskRemediationMapping] = Field(default_factory=list)


class VersionRiskInput(BaseModel):
    risk_id: str
    contract_text: str


class VersionCompareRequest(BaseModel):
    from_version_id: str
    to_version_id: str
    old_risks: list[VersionRiskInput] = Field(default_factory=list)


class ContractRecord(BaseModel):
    id: str
    title: str
    category: ContractCategory
    tags: list[str]
    counterparty: str | None = None
    amount: Decimal | None = None
    currency: str | None = "CNY"
    file_name: str | None = None
    description: str | None = None
    status: ContractStatus
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    owner_name: str | None = None
    updated_by: str
    expires_at: datetime | None = None
    versions: list[ContractVersion] = Field(default_factory=list)
    current_version: int = 0
    latest_risk_level: str | None = None
    risk_count: int | None = None


class ContractListResponse(BaseModel):
    items: list[ContractRecord]
    total: int
    page: int
    page_size: int


ContractSortBy = Literal["created_at", "updated_at", "title", "status", "category"]
SortOrder = Literal["asc", "desc"]


class ContractReviewSummary(BaseModel):
    review_id: str
    created_at: datetime
    status: str
    risk_level: str | None = None
    risk_count: int | None = None
    duration_ms: int | None = None
    report_available: bool = False


class ContractAuditEntry(BaseModel):
    action: str
    actor_id: str | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContractDetail(BaseModel):
    contract: ContractRecord
    recent_reviews: list[ContractReviewSummary] = Field(default_factory=list)
    reports: list[ContractReviewSummary] = Field(default_factory=list)
    audit_logs: list[ContractAuditEntry] = Field(default_factory=list)
