from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ContractType(StrEnum):
    general = "general"
    purchase = "purchase"
    sales = "sales"
    employment = "employment"
    lease = "lease"
    nda = "nda"
    service = "service"
    other = "other"


class PromptStage(StrEnum):
    extraction = "extraction"
    compliance = "compliance"
    refinement = "refinement"


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    contract_type: ContractType
    stage: PromptStage
    system_prompt: str = Field(min_length=10, max_length=20000)
    description: str | None = Field(default=None, max_length=500)
    is_enabled: bool = True


class PromptTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    system_prompt: str | None = Field(default=None, min_length=10, max_length=20000)
    description: str | None = Field(default=None, max_length=500)
    is_enabled: bool | None = None


class PromptTemplatePublic(BaseModel):
    id: str
    name: str
    contract_type: ContractType
    stage: PromptStage
    system_prompt: str
    description: str | None = None
    is_enabled: bool
    is_default: bool
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
