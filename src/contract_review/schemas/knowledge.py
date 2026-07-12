from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel


class KnowledgeSourceType(StrEnum):
    law = "law"
    regulation = "regulation"
    judicial_interpretation = "judicial_interpretation"
    enterprise_policy = "enterprise_policy"
    contract_template = "contract_template"
    review_guideline = "review_guideline"


class KnowledgeStatus(StrEnum):
    draft = "draft"
    effective = "effective"
    amended = "amended"
    expired = "expired"
    repealed = "repealed"


class KnowledgeDocument(BaseModel):
    document_id: str
    title: str
    source_type: KnowledgeSourceType
    jurisdiction: str | None = None
    issuing_authority: str | None = None
    version: str
    effective_date: date | None = None
    expiry_date: date | None = None
    status: KnowledgeStatus
    article_number: str | None = None
    content: str
    source_url: str | None = None
    checksum: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
