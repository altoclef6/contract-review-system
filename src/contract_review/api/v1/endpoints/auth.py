from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from contract_review.api.dependencies.auth import (
    get_audit_service,
    get_client_ip,
    get_current_user,
    get_user_service,
    issue_token_pair,
)
from contract_review.core.config import Settings, get_settings
from contract_review.core.security import TokenError, decode_token
from contract_review.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.user_service import UserService, UserServiceError

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterRequest,
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> UserPublic:
    try:
        user = users.create_user(
            email=str(payload.email),
            password=payload.password,
            full_name=payload.full_name,
        )
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="auth.register", target=user.id)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> TokenResponse:
    user = users.authenticate(email=str(payload.email), password=payload.password)
    audit.log_login(
        user_id=user.id if user else None,
        email=str(payload.email),
        success=user is not None,
        ip_address=get_client_ip(request),
        reason=None if user else "invalid_credentials",
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    access_token, refresh_token, expires_in = issue_token_pair(user, settings)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=user,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    settings: Settings = Depends(get_settings),
    users: UserService = Depends(get_user_service),
) -> TokenResponse:
    try:
        token_payload = decode_token(
            payload.refresh_token,
            secret=settings.jwt_secret_key.get_secret_value(),
            expected_type="refresh",
        )
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新 Token 无效") from exc
    user = users.get_by_id(str(token_payload.get("sub")))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    access_token, refresh_token_value, expires_in = issue_token_pair(user, settings)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        expires_in=expires_in,
        user=user,
    )


@router.get("/me", response_model=UserPublic)
async def current_user(user: UserPublic = Depends(get_current_user)) -> UserPublic:
    return user


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: UserPublic = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> dict[str, str]:
    try:
        users.change_password(
            user_id=user.id,
            old_password=payload.old_password,
            new_password=payload.new_password,
        )
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="auth.change_password", target=user.id)
    return {"message": "密码已修改"}


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    audit: AuditService = Depends(get_audit_service),
) -> dict[str, str]:
    audit.log_operation(
        actor_id=None,
        action="auth.forgot_password.requested",
        target=str(payload.email),
    )
    return {"message": "如果邮箱存在，系统将发送重置密码通知"}
