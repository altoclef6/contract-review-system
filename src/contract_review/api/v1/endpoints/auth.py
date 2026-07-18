from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from contract_review.api.dependencies.auth import (
    get_audit_service,
    get_client_ip,
    get_current_user,
    get_refresh_token_service,
    get_user_service,
    issue_token_pair,
)
from contract_review.core.config import Settings, get_settings
from contract_review.core.security import TokenError, decode_token
from contract_review.schemas.api_response import ApiResponse, MessageData, api_success
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
from contract_review.services.login_rate_limiter import (
    LoginRateLimiter,
    LoginRateLimitExceeded,
    LoginRateLimitUnavailable,
)
from contract_review.services.refresh_token_service import (
    RefreshTokenError,
    RefreshTokenReuseError,
    RefreshTokenService,
    RefreshTokenUnavailable,
)
from contract_review.services.user_service import UserService, UserServiceError

router = APIRouter()


@router.post(
    "/register",
    response_model=ApiResponse[UserPublic],
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register_user(
    payload: RegisterRequest,
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[UserPublic]:
    try:
        user = users.create_user(
            email=str(payload.email),
            password=payload.password,
            full_name=payload.full_name,
        )
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="auth.register", target=user.id)
    return api_success(user, "注册成功")


@router.post("/login", response_model=ApiResponse[TokenResponse], summary="用户登录")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
    refresh_sessions: RefreshTokenService = Depends(get_refresh_token_service),
) -> ApiResponse[TokenResponse]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    limiter = LoginRateLimiter(settings)
    try:
        limit_key = limiter.check(
            email=str(payload.email), client_ip=get_client_ip(request, settings)
        )
    except LoginRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="登录尝试过多，请稍后重试") from exc
    except LoginRateLimitUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="登录安全服务暂不可用") from exc
    user = users.authenticate(email=str(payload.email), password=payload.password)
    audit.log_login(
        user_id=user.id if user else None,
        email=str(payload.email),
        success=user is not None,
        ip_address=get_client_ip(request, settings),
        reason=None if user else "invalid_credentials",
    )
    if user is None:
        try:
            limiter.failed(limit_key)
        except LoginRateLimitUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="登录安全服务暂不可用") from exc
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    limiter.succeeded(limit_key)
    refresh_exp = int(
        (datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_days)).timestamp()
    )
    try:
        family_id, token_id = refresh_sessions.issue(
            user_id=user.id, token_version=user.token_version, expires_at=refresh_exp
        )
    except RefreshTokenUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="会话安全服务暂不可用") from exc
    access_token, refresh_token, expires_in = issue_token_pair(
        user,
        settings,
        refresh_token_id=token_id,
        refresh_family_id=family_id,
    )
    return api_success(
        TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=user,
        ),
        "登录成功",
    )


@router.post("/refresh", response_model=ApiResponse[TokenResponse], summary="刷新令牌")
async def refresh_token(
    payload: RefreshTokenRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
    users: UserService = Depends(get_user_service),
    refresh_sessions: RefreshTokenService = Depends(get_refresh_token_service),
) -> ApiResponse[TokenResponse]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        token_payload = decode_token(
            payload.refresh_token,
            secret=settings.jwt_secret_key.get_secret_value(),
            expected_type="refresh",
        )
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新 Token 无效"
        ) from exc
    user = users.get_by_id(str(token_payload.get("sub")))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    if int(token_payload.get("ver", -1)) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新 Token 无效")
    family_id = token_payload.get("family")
    token_id = token_payload.get("jti")
    if not isinstance(family_id, str) or not isinstance(token_id, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新 Token 无效")
    refresh_exp = int(
        (datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_days)).timestamp()
    )
    try:
        new_token_id = refresh_sessions.rotate(
            user_id=user.id,
            family_id=family_id,
            token_id=token_id,
            token_version=user.token_version,
            expires_at=refresh_exp,
        )
    except RefreshTokenReuseError as exc:
        users.revoke_sessions(user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="检测到刷新 Token 重放，登录已撤销"
        ) from exc
    except RefreshTokenUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="会话安全服务暂不可用") from exc
    except RefreshTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新 Token 无效") from exc
    access_token, refresh_token_value, expires_in = issue_token_pair(
        user,
        settings,
        refresh_token_id=new_token_id,
        refresh_family_id=family_id,
    )
    return api_success(
        TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_value,
            expires_in=expires_in,
            user=user,
        ),
        "Token 已刷新",
    )


@router.post("/logout", response_model=ApiResponse[MessageData], summary="退出当前会话")
async def logout(
    payload: RefreshTokenRequest,
    settings: Settings = Depends(get_settings),
    refresh_sessions: RefreshTokenService = Depends(get_refresh_token_service),
) -> ApiResponse[MessageData]:
    try:
        token_payload = decode_token(
            payload.refresh_token,
            secret=settings.jwt_secret_key.get_secret_value(),
            expected_type="refresh",
        )
        family_id = token_payload.get("family")
        if isinstance(family_id, str):
            refresh_sessions.revoke_family(family_id)
    except RefreshTokenUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="会话安全服务暂不可用") from exc
    except TokenError:
        pass
    return api_success(MessageData(message="会话已退出"), "会话已退出")


@router.post("/logout-all", response_model=ApiResponse[MessageData], summary="撤销全部会话")
async def logout_all(
    user: UserPublic = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
    refresh_sessions: RefreshTokenService = Depends(get_refresh_token_service),
) -> ApiResponse[MessageData]:
    users.revoke_sessions(user.id)
    try:
        refresh_sessions.revoke_user(user.id)
    except RefreshTokenUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="会话安全服务暂不可用") from exc
    return api_success(MessageData(message="全部会话已撤销"), "全部会话已撤销")


@router.get("/me", response_model=ApiResponse[UserPublic], summary="当前用户")
async def current_user(user: UserPublic = Depends(get_current_user)) -> ApiResponse[UserPublic]:
    return api_success(user)


@router.post("/change-password", response_model=ApiResponse[MessageData], summary="修改密码")
async def change_password(
    payload: ChangePasswordRequest,
    user: UserPublic = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[MessageData]:
    try:
        users.change_password(
            user_id=user.id,
            old_password=payload.old_password,
            new_password=payload.new_password,
        )
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="auth.change_password", target=user.id)
    return api_success(MessageData(message="密码已修改"), "密码已修改")


@router.post("/forgot-password", response_model=ApiResponse[MessageData], summary="忘记密码")
async def forgot_password(
    payload: ForgotPasswordRequest,
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[MessageData]:
    audit.log_operation(
        actor_id=None,
        action="auth.forgot_password.requested",
        target=str(payload.email),
    )
    return api_success(MessageData(message="如果邮箱存在，系统将发送重置密码通知"))
