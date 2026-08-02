from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from contract_review.schemas.auth import UserPublic, UserRole


class CompanyPublic(BaseModel):
    id: str
    name: str
    code: str
    status: str
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    settings: dict[str, Any] | None = None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=80)
    parent_id: str | None = None


class DepartmentPublic(BaseModel):
    id: str
    company_id: str
    parent_id: str | None
    name: str
    code: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class MemberCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=80)
    role: UserRole = UserRole.member
    department_id: str | None = None
    job_title: str | None = Field(default=None, max_length=120)


class OrganizationOverview(BaseModel):
    company: CompanyPublic
    departments: list[DepartmentPublic]
    members: list[UserPublic]
