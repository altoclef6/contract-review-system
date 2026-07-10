from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class UserRole(StrEnum):
    admin = "admin"
    legal = "legal"
    employee = "employee"


class Permission(StrEnum):
    users_read = "users:read"
    users_write = "users:write"
    contracts_read = "contracts:read"
    contracts_write = "contracts:write"
    reviews_run = "reviews:run"
    reviews_history = "reviews:history"
    prompts_manage = "prompts:manage"
    models_manage = "models:manage"


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.admin: set(Permission),
    UserRole.legal: {
        Permission.contracts_read,
        Permission.contracts_write,
        Permission.reviews_run,
        Permission.reviews_history,
        Permission.prompts_manage,
    },
    UserRole.employee: {
        Permission.contracts_read,
        Permission.contracts_write,
        Permission.reviews_run,
    },
}


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


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
