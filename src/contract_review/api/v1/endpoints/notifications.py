from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from contract_review.api.dependencies.auth import require_permission
from contract_review.schemas.api_response import ApiResponse, MessageData, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.notification import NotificationPage, NotificationPublic
from contract_review.services.notification_service import (
    NotificationService,
    NotificationServiceError,
)

router = APIRouter()


def get_notification_service(request: Request) -> NotificationService:
    return NotificationService(request.app.state.settings.notification_data_dir)


@router.get("", response_model=ApiResponse[NotificationPage], summary="我的通知")
async def list_notifications(
    user: UserPublic = Depends(require_permission(Permission.notifications_read)),
    service: NotificationService = Depends(get_notification_service),
) -> ApiResponse[NotificationPage]:
    items = service.list_for_user(user.id)
    return api_success(
        NotificationPage(
            items=items,
            unread_count=sum(1 for item in items if not item.is_read),
            total=len(items),
        )
    )


@router.post(
    "/{notification_id}/read",
    response_model=ApiResponse[NotificationPublic],
    summary="标记通知已读",
)
async def mark_notification_read(
    notification_id: str,
    user: UserPublic = Depends(require_permission(Permission.notifications_read)),
    service: NotificationService = Depends(get_notification_service),
) -> ApiResponse[NotificationPublic]:
    try:
        return api_success(service.mark_read(notification_id, user.id), "通知已读")
    except NotificationServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/read-all", response_model=ApiResponse[MessageData], summary="全部标记已读")
async def mark_all_notifications_read(
    user: UserPublic = Depends(require_permission(Permission.notifications_read)),
    service: NotificationService = Depends(get_notification_service),
) -> ApiResponse[MessageData]:
    count = service.mark_all_read(user.id)
    return api_success(MessageData(message=f"已标记 {count} 条通知"))
