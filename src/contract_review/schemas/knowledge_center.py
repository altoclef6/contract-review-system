
from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class KnowledgeSourceType(StrEnum):
    law = "law"
    judicial_interpretation = "judicial_interpretation"
    regulation = "regulation"
    internal_policy = "internal_policy"
    contract_template = "contract_template"
    review_guidance = "review_guidance"
    test_data = "test_data"


class KnowledgeStatus(StrEnum):
    draft = "draft"
    effective = "effective"
    inactive = "inactive"
    expired = "expired"


class KnowledgeWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    article_number: str | None = Field(default=None, max_length=100)
    content: str = Field(min_length=1, max_length=50000)
    source_type: KnowledgeSourceType
    status: KnowledgeStatus = KnowledgeStatus.draft
    issuing_authority: str | None = Field(default=None, max_length=240)
    effective_date: date | None = None
    expiry_date: date | None = None
    source_url: HttpUrl | None = None
    contract_types: list[str] = Field(default_factory=list)
    related_rule_ids: list[str] = Field(default_factory=list)

    @field_validator("source_url", mode="before")
    @classmethod
    def blank_url_is_none(cls, value: object) -> object:
        return None if value == "" else value


class KnowledgeCreate(KnowledgeWrite):
    document_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,79}$")


class KnowledgeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    article_number: str | None = Field(default=None, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=50000)
    source_type: KnowledgeSourceType | None = None
    status: KnowledgeStatus | None = None
    issuing_authority: str | None = Field(default=None, max_length=240)
    effective_date: date | None = None
    expiry_date: date | None = None
    source_url: HttpUrl | None = None
    contract_types: list[str] | None = None
    related_rule_ids: list[str] | None = None


class KnowledgeRecord(BaseModel):
    id: str
    document_id: str
    title: str
    article_number: str | None = None
    content: str
    source_type: KnowledgeSourceType
    status: KnowledgeStatus
    issuing_authority: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    version: int
    source_url: str | None = None
    contract_types: list[str]
    related_rule_ids: list[str]
    supersedes_id: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeRecord]
    total: int
