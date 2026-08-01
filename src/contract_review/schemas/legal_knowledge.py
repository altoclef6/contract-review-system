from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class LegalEffectStatus(StrEnum):
    effective = "effective"
    amended = "amended"
    repealed = "repealed"
    pending_effective = "pending_effective"


class VerificationStatus(StrEnum):
    pending_verification = "pending_verification"
    verified = "verified"
    rejected = "rejected"


class LegalDocumentWrite(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    document_type: str = Field(min_length=1, max_length=80)
    issuing_authority: str | None = Field(default=None, max_length=255)
    document_number: str | None = Field(default=None, max_length=120)
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    effect_status: LegalEffectStatus = LegalEffectStatus.pending_effective
    version_number: str = Field(default="1.0", min_length=1, max_length=80)
    official_source_url: HttpUrl | None = None
    source_name: str = Field(min_length=1, max_length=255)
    full_text: str = Field(default="", max_length=1_000_000)
    verification_status: VerificationStatus = VerificationStatus.pending_verification
    is_enabled: bool = True
    change_summary: str | None = Field(default=None, max_length=1000)

    @field_validator("official_source_url", mode="before")
    @classmethod
    def blank_url_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def verified_content_requires_source(self) -> "LegalDocumentWrite":
        if self.verification_status == VerificationStatus.verified:
            if not self.official_source_url or not self.full_text.strip():
                raise ValueError("标记为已核验时必须提供官方来源地址和法律全文")
        return self


class LegalDocumentCreate(LegalDocumentWrite):
    pass


class LegalDocumentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    document_type: str | None = Field(default=None, min_length=1, max_length=80)
    issuing_authority: str | None = Field(default=None, max_length=255)
    document_number: str | None = Field(default=None, max_length=120)
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    effect_status: LegalEffectStatus | None = None
    version_number: str | None = Field(default=None, min_length=1, max_length=80)
    official_source_url: HttpUrl | None = None
    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    full_text: str | None = Field(default=None, max_length=1_000_000)
    verification_status: VerificationStatus | None = None
    is_enabled: bool | None = None
    change_summary: str | None = Field(default=None, max_length=1000)

    @field_validator("official_source_url", mode="before")
    @classmethod
    def blank_url_is_none(cls, value: object) -> object:
        return None if value == "" else value


class LegalDocumentRecord(BaseModel):
    id: str
    name: str
    document_type: str
    issuing_authority: str | None = None
    document_number: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    effect_status: LegalEffectStatus
    version_number: str
    official_source_url: str | None = None
    source_name: str
    full_text: str
    verification_status: VerificationStatus
    is_enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class LegalDocumentVersionRecord(BaseModel):
    id: str
    legal_document_id: str
    version_number: str
    publication_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    effect_status: LegalEffectStatus
    official_source_url: str | None = None
    source_name: str
    full_text: str
    verification_status: VerificationStatus
    change_summary: str | None = None
    created_by: str
    created_at: datetime


class LegalArticleWrite(BaseModel):
    legal_document_id: str = Field(min_length=1, max_length=64)
    legal_document_version_id: str = Field(min_length=1, max_length=64)
    chapter_no: str | None = Field(default=None, max_length=80)
    chapter_name: str | None = Field(default=None, max_length=255)
    article_no: str = Field(min_length=1, max_length=120)
    article_no_numeric: int | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=300)
    content: str = Field(min_length=1, max_length=100_000)
    keywords: list[str] = Field(default_factory=list, max_length=80)
    legal_topics: list[str] = Field(default_factory=list, max_length=40)
    contract_types: list[str] = Field(default_factory=list, max_length=40)
    is_effective: bool = True
    verification_status: VerificationStatus = VerificationStatus.pending_verification

    @model_validator(mode="after")
    def pending_placeholder_cannot_be_effective(self) -> "LegalArticleWrite":
        if self.verification_status != VerificationStatus.verified and self.is_effective:
            raise ValueError("待核验或已驳回条文不能标记为有效")
        return self


class LegalArticleCreate(LegalArticleWrite):
    pass


class LegalArticleUpdate(BaseModel):
    chapter_no: str | None = Field(default=None, max_length=80)
    chapter_name: str | None = Field(default=None, max_length=255)
    article_no: str | None = Field(default=None, min_length=1, max_length=120)
    article_no_numeric: int | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    keywords: list[str] | None = Field(default=None, max_length=80)
    legal_topics: list[str] | None = Field(default=None, max_length=40)
    contract_types: list[str] | None = Field(default=None, max_length=40)
    is_effective: bool | None = None
    verification_status: VerificationStatus | None = None


class LegalArticleRecord(BaseModel):
    id: str
    legal_document_id: str
    legal_document_version_id: str
    law_name: str
    law_version: str
    effect_status: LegalEffectStatus
    source_name: str
    source_url: str | None = None
    chapter_no: str | None = None
    chapter_name: str | None = None
    article_no: str
    article_no_numeric: int | None = None
    title: str | None = None
    content: str
    keywords: list[str]
    legal_topics: list[str]
    contract_types: list[str]
    is_effective: bool
    verification_status: VerificationStatus
    created_by: str
    created_at: datetime
    updated_at: datetime


class ContractRiskRuleWrite(BaseModel):
    rule_code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,79}$")
    rule_name: str = Field(min_length=1, max_length=255)
    contract_types: list[str] = Field(default_factory=lambda: ["all"], max_length=40)
    clause_type: str = Field(min_length=1, max_length=120)
    risk_level: str = Field(pattern=r"^(low|medium|high|critical)$")
    trigger_condition: str = Field(min_length=1, max_length=2000)
    keywords: list[str] = Field(default_factory=list, max_length=80)
    model_prompt: str = Field(default="", max_length=5000)
    risk_description: str = Field(min_length=1, max_length=5000)
    possible_consequence: str = Field(default="", max_length=5000)
    modification_advice: str = Field(min_length=1, max_length=5000)
    recommended_clause: str = Field(default="", max_length=10_000)
    is_enabled: bool = True
    legal_article_ids: list[str] = Field(default_factory=list, max_length=100)


class ContractRiskRuleCreate(ContractRiskRuleWrite):
    pass


class ContractRiskRuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=255)
    contract_types: list[str] | None = Field(default=None, max_length=40)
    clause_type: str | None = Field(default=None, min_length=1, max_length=120)
    risk_level: str | None = Field(default=None, pattern=r"^(low|medium|high|critical)$")
    trigger_condition: str | None = Field(default=None, min_length=1, max_length=2000)
    keywords: list[str] | None = Field(default=None, max_length=80)
    model_prompt: str | None = Field(default=None, max_length=5000)
    risk_description: str | None = Field(default=None, min_length=1, max_length=5000)
    possible_consequence: str | None = Field(default=None, max_length=5000)
    modification_advice: str | None = Field(default=None, min_length=1, max_length=5000)
    recommended_clause: str | None = Field(default=None, max_length=10_000)
    is_enabled: bool | None = None
    legal_article_ids: list[str] | None = Field(default=None, max_length=100)


class ContractRiskRuleRecord(ContractRiskRuleWrite):
    id: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class LegalBasisReference(BaseModel):
    legalArticleId: str
    lawName: str
    articleNo: str
    sourceUrl: str | None = None
    contentSummary: str = ""
    sourceName: str = ""
    version: str = ""


class LegalSearchResponse(BaseModel):
    items: list[LegalArticleRecord]
    total: int


class LegalDocumentListResponse(BaseModel):
    items: list[LegalDocumentRecord]
    total: int


class RiskRuleListResponse(BaseModel):
    items: list[ContractRiskRuleRecord]
    total: int


class DemoSeedResponse(BaseModel):
    documents: int
    articles: int
    rules: int
    message: str
