from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ContractCategory(StrEnum):
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
    version_type: Literal["original", "modified", "re_review", "final"] = "original"


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
    file_name: str | None = None
    description: str | None = None
    status: ContractStatus
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    expires_at: datetime | None = None
    versions: list[ContractVersion] = Field(default_factory=list)


class ContractListResponse(BaseModel):
    items: list[ContractRecord]
    total: int
    page: int
    page_size: int


ContractSortBy = Literal["created_at", "updated_at", "title", "status", "category"]
SortOrder = Literal["asc", "desc"]
