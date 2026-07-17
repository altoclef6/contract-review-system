from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from ipaddress import ip_address, ip_network

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from contract_review.core.config import Settings, get_settings
from contract_review.core.security import TokenError, create_token, decode_token
from contract_review.schemas.auth import ROLE_PERMISSIONS, Permission, UserPublic, UserRole
from contract_review.services.audit_service import AuditService
from contract_review.services.refresh_token_service import RefreshTokenService
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


def get_refresh_token_service(
    settings: Settings = Depends(get_settings),
) -> RefreshTokenService:
    return RefreshTokenService(settings)


def issue_token_pair(
    user: UserPublic,
    settings: Settings,
    *,
    refresh_token_id: str,
    refresh_family_id: str,
) -> tuple[str, str, int]:
    secret = settings.jwt_secret_key.get_secret_value()
    access_minutes = settings.jwt_access_token_minutes
    access_token = create_token(
        subject=user.id,
        role=user.role.value,
        secret=secret,
        token_type="access",
        expires_delta=timedelta(minutes=access_minutes),
        token_version=user.token_version,
    )
    refresh_token = create_token(
        subject=user.id,
        role=user.role.value,
        secret=secret,
        token_type="refresh",
        expires_delta=timedelta(days=settings.jwt_refresh_token_days),
        token_version=user.token_version,
        token_id=refresh_token_id,
        family_id=refresh_family_id,
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效"
        ) from exc

    user = users.get_by_id(str(payload.get("sub")))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    if int(payload.get("ver", -1)) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效")
    return user


def require_role(*roles: UserRole) -> Callable[[UserPublic], Awaitable[UserPublic]]:
    async def dependency(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return dependency


def require_permission(permission: Permission) -> Callable[[UserPublic], Awaitable[UserPublic]]:
    async def dependency(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if permission not in ROLE_PERMISSIONS[user.role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return dependency


def get_client_ip(request: Request, settings: Settings) -> str | None:
    direct = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for")
    trusted_peer = False
    if settings.trust_proxy_headers and direct:
        try:
            peer = ip_address(direct)
            trusted_peer = any(
                peer in ip_network(cidr, strict=False) for cidr in settings.trusted_proxy_cidrs
            )
        except ValueError:
            trusted_peer = False
    if forwarded_for and trusted_peer:
        return forwarded_for.split(",", 1)[0].strip()
    return direct
