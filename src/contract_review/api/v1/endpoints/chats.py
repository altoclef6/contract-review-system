from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from contract_review.api.dependencies.auth import get_audit_service, require_permission
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.chat import (
    ChatAskRequest,
    ChatAskResponse,
    ChatSessionCreate,
    ChatSessionPublic,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.chat_service import ChatService, ChatServiceError

router = APIRouter()


def get_chat_service(request: Request) -> ChatService:
    settings = request.app.state.settings
    return ChatService(settings.chat_data_dir, settings.report_dir.parent)


@router.post(
    "", response_model=ApiResponse[ChatSessionPublic], status_code=201, summary="创建合同 AI 对话"
)
async def create_chat(
    payload: ChatSessionCreate,
    user: UserPublic = Depends(require_permission(Permission.reviews_run)),
    service: ChatService = Depends(get_chat_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ChatSessionPublic]:
    try:
        session = service.create(user.id, payload.review_id, payload.title)
    except ChatServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="chats.create", target=session.id)
    return api_success(session, "AI 对话已创建")


@router.get("", response_model=ApiResponse[list[ChatSessionPublic]], summary="我的 AI 对话列表")
async def list_chats(
    user: UserPublic = Depends(require_permission(Permission.reviews_run)),
    service: ChatService = Depends(get_chat_service),
) -> ApiResponse[list[ChatSessionPublic]]:
    return api_success(service.list_for_user(user.id))


@router.get("/{session_id}", response_model=ApiResponse[ChatSessionPublic], summary="查看 AI 对话")
async def get_chat(
    session_id: str,
    user: UserPublic = Depends(require_permission(Permission.reviews_run)),
    service: ChatService = Depends(get_chat_service),
) -> ApiResponse[ChatSessionPublic]:
    try:
        return api_success(service.get(session_id, user.id))
    except ChatServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{session_id}/messages",
    response_model=ApiResponse[ChatAskResponse],
    summary="向合同 AI 助手提问",
)
async def ask_chat(
    session_id: str,
    payload: ChatAskRequest,
    user: UserPublic = Depends(require_permission(Permission.reviews_run)),
    service: ChatService = Depends(get_chat_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ChatAskResponse]:
    try:
        result = await service.ask(session_id, user.id, payload.message)
    except ChatServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="chats.ask", target=session_id)
    return api_success(result, "AI 已完成回答" if result.ai_available else "模型尚未连接")


@router.delete(
    "/{session_id}", response_model=ApiResponse[ChatSessionPublic], summary="删除 AI 对话"
)
async def delete_chat(
    session_id: str,
    user: UserPublic = Depends(require_permission(Permission.reviews_run)),
    service: ChatService = Depends(get_chat_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ChatSessionPublic]:
    try:
        session = service.delete(session_id, user.id)
    except ChatServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="chats.delete", target=session_id)
    return api_success(session, "AI 对话已删除")
