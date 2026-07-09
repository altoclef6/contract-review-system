from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from contract_review.core.config import Settings, get_settings
from contract_review.core.security import TokenError, create_token, decode_token
from contract_review.schemas.auth import ROLE_PERMISSIONS, Permission, UserPublic, UserRole
from contract_review.services.audit_service import AuditService
from contract_review.services.user_service import UserService

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="登录令牌",
    description="请输入登录接口返回的 access_token。系统会自动按访问令牌方式发送。",
)


def get_user_service(settings: Settings = Depends(get_settings)) -> UserService:
    return UserService(settings)


def get_audit_service(settings: Settings = Depends(get_settings)) -> AuditService:
    return AuditService(settings.security_data_dir)


def issue_token_pair(user: UserPublic, settings: Settings) -> tuple[str, str, int]:
    secret = settings.jwt_secret_key.get_secret_value()
    access_minutes = settings.jwt_access_token_minutes
    access_token = create_token(
        subject=user.id,
        role=user.role.value,
        secret=secret,
        token_type="access",
        expires_delta=timedelta(minutes=access_minutes),
    )
    refresh_token = create_token(
        subject=user.id,
        role=user.role.value,
        secret=secret,
        token_type="refresh",
        expires_delta=timedelta(days=settings.jwt_refresh_token_days),
    )
    return access_token, refresh_token, access_minutes * 60


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    users: UserService = Depends(get_user_service),
) -> UserPublic:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = decode_token(
            credentials.credentials,
            secret=settings.jwt_secret_key.get_secret_value(),
            expected_type="access",
        )
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效") from exc

    user = users.get_by_id(str(payload.get("sub")))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    return user


def require_role(*roles: UserRole) -> Callable[[UserPublic], UserPublic]:
    async def dependency(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return dependency


def require_permission(permission: Permission) -> Callable[[UserPublic], UserPublic]:
    async def dependency(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if permission not in ROLE_PERMISSIONS[user.role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return dependency


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else None
