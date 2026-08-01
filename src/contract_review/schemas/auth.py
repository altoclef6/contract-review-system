from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class UserRole(StrEnum):
    admin = "admin"
    company_admin = "company_admin"
    legal_manager = "legal_manager"
    legal = "legal"
    member = "member"
    employee = "employee"


class Permission(StrEnum):
    users_read = "users:read"
    users_write = "users:write"
    contracts_read = "contracts:read"
    contracts_write = "contracts:write"
    reviews_run = "reviews:run"
    reviews_history = "reviews:history"
    workflows_approve = "workflows:approve"
    notifications_read = "notifications:read"
    prompts_manage = "prompts:manage"
    models_manage = "models:manage"
    rules_read = "rules:read"
    rules_manage = "rules:manage"
    knowledge_read = "knowledge:read"
    knowledge_manage = "knowledge:manage"
    company_manage = "company:manage"
    departments_manage = "departments:manage"
    members_manage = "members:manage"
    audit_read = "audit:read"
    agent_run = "agent:run"
    agent_confirm = "agent:confirm"


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.admin: set(Permission),
    UserRole.company_admin: set(Permission) - {Permission.models_manage},
    UserRole.legal_manager: {
        Permission.contracts_read,
        Permission.contracts_write,
        Permission.reviews_run,
        Permission.reviews_history,
        Permission.workflows_approve,
        Permission.notifications_read,
        Permission.prompts_manage,
        Permission.rules_read,
        Permission.rules_manage,
        Permission.knowledge_read,
        Permission.knowledge_manage,
        Permission.members_manage,
        Permission.audit_read,
        Permission.agent_run,
        Permission.agent_confirm,
    },
    UserRole.legal: {
        Permission.contracts_read,
        Permission.contracts_write,
        Permission.reviews_run,
        Permission.reviews_history,
        Permission.workflows_approve,
        Permission.notifications_read,
        Permission.prompts_manage,
        Permission.rules_read,
        Permission.rules_manage,
        Permission.knowledge_read,
        Permission.knowledge_manage,
        Permission.agent_run,
        Permission.agent_confirm,
    },
    UserRole.member: {
        Permission.contracts_read,
        Permission.contracts_write,
        Permission.reviews_run,
        Permission.notifications_read,
        Permission.rules_read,
        Permission.knowledge_read,
        Permission.agent_run,
    },
    UserRole.employee: {
        Permission.contracts_read,
        Permission.contracts_write,
        Permission.reviews_run,
        Permission.notifications_read,
        Permission.rules_read,
        Permission.knowledge_read,
        Permission.agent_run,
    },
}


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: str | None = None
    department_id: str | None = None
    job_title: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
    token_version: int = Field(default=0, exclude=True)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class DisableUserRequest(BaseModel):
    disabled: bool


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class ResetPasswordResponse(BaseModel):
    user_id: str
    temporary_password: str


class RoleInfo(BaseModel):
    role: UserRole
    permissions: list[Permission]
