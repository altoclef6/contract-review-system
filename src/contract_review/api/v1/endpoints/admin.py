from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from contract_review.api.dependencies.auth import get_audit_service, get_user_service, require_role
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import (
    ROLE_PERMISSIONS,
    DisableUserRequest,
    ResetPasswordResponse,
    RoleInfo,
    UpdateUserRoleRequest,
    UserPublic,
    UserRole,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.user_service import UserService, UserServiceError

router = APIRouter()


@router.get("/users", response_model=ApiResponse[list[UserPublic]], summary="用户列表")
async def list_users(
    _: UserPublic = Depends(require_role(UserRole.admin)),
    users: UserService = Depends(get_user_service),
) -> ApiResponse[list[UserPublic]]:
    return api_success(users.list_users())


@router.patch(
    "/users/{user_id}/role", response_model=ApiResponse[UserPublic], summary="修改用户角色"
)
async def set_user_role(
    user_id: str,
    payload: UpdateUserRoleRequest,
    actor: UserPublic = Depends(require_role(UserRole.admin)),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[UserPublic]:
    if actor.id == user_id and payload.role is not UserRole.admin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能移除自己的管理员角色")
    try:
        user = users.set_role(user_id=user_id, role=payload.role)
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=actor.id, action="admin.user.role", target=user_id)
    return api_success(user, "用户角色已更新")


@router.patch(
    "/users/{user_id}/disabled",
    response_model=ApiResponse[UserPublic],
    summary="启用或禁用账号",
)
async def set_user_disabled(
    user_id: str,
    payload: DisableUserRequest,
    actor: UserPublic = Depends(require_role(UserRole.admin)),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[UserPublic]:
    try:
        user = users.set_disabled(user_id=user_id, disabled=payload.disabled)
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=actor.id,
        action="admin.user.disabled" if payload.disabled else "admin.user.enabled",
        target=user_id,
    )
    return api_success(user, "账号状态已更新")


@router.post(
    "/users/{user_id}/reset-password",
    response_model=ApiResponse[ResetPasswordResponse],
    summary="重置用户密码",
)
async def reset_user_password(
    user_id: str,
    response: Response,
    actor: UserPublic = Depends(require_role(UserRole.admin)),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ResetPasswordResponse]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        _, temporary_password = users.reset_password(user_id=user_id)
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=actor.id, action="admin.user.reset_password", target=user_id)
    return api_success(
        ResetPasswordResponse(user_id=user_id, temporary_password=temporary_password),
        "密码已重置",
    )


@router.get("/roles", response_model=ApiResponse[list[RoleInfo]], summary="角色权限列表")
async def list_roles(
    _: UserPublic = Depends(require_role(UserRole.admin)),
) -> ApiResponse[list[RoleInfo]]:
    items = [
        RoleInfo(role=role, permissions=sorted(permissions))
        for role, permissions in ROLE_PERMISSIONS.items()
    ]
    return api_success(items)
