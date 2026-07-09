from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from contract_review.api.dependencies.auth import get_audit_service, get_user_service, require_role
from contract_review.schemas.auth import (
    ROLE_PERMISSIONS,
    DisableUserRequest,
    ResetPasswordResponse,
    RoleInfo,
    UserPublic,
    UserRole,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.user_service import UserService, UserServiceError

router = APIRouter()


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    _: UserPublic = Depends(require_role(UserRole.admin)),
    users: UserService = Depends(get_user_service),
) -> list[UserPublic]:
    return users.list_users()


@router.patch("/users/{user_id}/disabled", response_model=UserPublic)
async def set_user_disabled(
    user_id: str,
    payload: DisableUserRequest,
    actor: UserPublic = Depends(require_role(UserRole.admin)),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> UserPublic:
    try:
        user = users.set_disabled(user_id=user_id, disabled=payload.disabled)
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=actor.id,
        action="admin.user.disabled" if payload.disabled else "admin.user.enabled",
        target=user_id,
    )
    return user


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_user_password(
    user_id: str,
    actor: UserPublic = Depends(require_role(UserRole.admin)),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ResetPasswordResponse:
    try:
        _, temporary_password = users.reset_password(user_id=user_id)
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=actor.id, action="admin.user.reset_password", target=user_id)
    return ResetPasswordResponse(user_id=user_id, temporary_password=temporary_password)


@router.get("/roles", response_model=list[RoleInfo])
async def list_roles(_: UserPublic = Depends(require_role(UserRole.admin))) -> list[RoleInfo]:
    return [
        RoleInfo(role=role, permissions=sorted(permissions))
        for role, permissions in ROLE_PERMISSIONS.items()
    ]
