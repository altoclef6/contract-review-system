# ruff: noqa: B008

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from contract_review.api.dependencies.auth import get_audit_service, get_current_user
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import UserPublic, UserRole
from contract_review.schemas.review_task import (
    ReviewTaskCreate,
    ReviewTaskEvent,
    ReviewTaskListResponse,
    ReviewTaskRecord,
    ReviewTaskStatus,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.review_task_service import (
    ReviewTaskConflictError,
    ReviewTaskError,
    ReviewTaskPermissionError,
    ReviewTaskService,
)

router = APIRouter()


def _is_admin(user: UserPublic) -> bool:
    return user.role in {UserRole.admin, UserRole.legal}


def get_task_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ReviewTaskService:
    graph = getattr(request.app.state, "contract_review_graph", None)
    return ReviewTaskService(settings, graph=graph)


def _raise_api_error(exc: ReviewTaskError) -> NoReturn:
    if isinstance(exc, ReviewTaskPermissionError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review task not found")
    if isinstance(exc, ReviewTaskConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "",
    response_model=ApiResponse[ReviewTaskRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create async review task",
)
async def create_review_task(
    payload: ReviewTaskCreate,
    user: UserPublic = Depends(get_current_user),
    tasks: ReviewTaskService = Depends(get_task_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ReviewTaskRecord]:
    task = tasks.create_task(payload, actor_id=user.id)
    audit.log_operation(
        actor_id=user.id,
        action="review_tasks.create",
        target=task.task_id,
        metadata={"contract_id": task.contract_id, "status": task.status.value},
    )
    try:
        task = tasks.enqueue_or_run(task.task_id)
    except ReviewTaskError as exc:
        _raise_api_error(exc)
    return api_success(task, "review task created")


@router.get("", response_model=ApiResponse[ReviewTaskListResponse], summary="List review tasks")
async def list_review_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: ReviewTaskStatus | None = Query(default=None, alias="status"),
    user: UserPublic = Depends(get_current_user),
    tasks: ReviewTaskService = Depends(get_task_service),
) -> ApiResponse[ReviewTaskListResponse]:
    return api_success(
        tasks.list_tasks(
            actor_id=user.id,
            as_admin=_is_admin(user),
            page=page,
            page_size=page_size,
            status=status_filter,
        )
    )


@router.get("/{task_id}", response_model=ApiResponse[ReviewTaskRecord], summary="Get review task")
async def get_review_task(
    task_id: str,
    user: UserPublic = Depends(get_current_user),
    tasks: ReviewTaskService = Depends(get_task_service),
) -> ApiResponse[ReviewTaskRecord]:
    try:
        return api_success(tasks.get_task(task_id, actor_id=user.id, as_admin=_is_admin(user)))
    except ReviewTaskError as exc:
        _raise_api_error(exc)

@router.post(
    "/{task_id}/cancel",
    response_model=ApiResponse[ReviewTaskRecord],
    summary="Cancel review task",
)
async def cancel_review_task(
    task_id: str,
    user: UserPublic = Depends(get_current_user),
    tasks: ReviewTaskService = Depends(get_task_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ReviewTaskRecord]:
    try:
        task = tasks.cancel_task(task_id, actor_id=user.id, as_admin=_is_admin(user))
    except ReviewTaskError as exc:
        _raise_api_error(exc)
    audit.log_operation(actor_id=user.id, action="review_tasks.cancel", target=task_id)
    return api_success(task, "review task cancelled")


@router.post(
    "/{task_id}/retry",
    response_model=ApiResponse[ReviewTaskRecord],
    summary="Retry failed review task",
)
async def retry_review_task(
    task_id: str,
    user: UserPublic = Depends(get_current_user),
    tasks: ReviewTaskService = Depends(get_task_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ReviewTaskRecord]:
    try:
        task = tasks.retry_task(task_id, actor_id=user.id, as_admin=_is_admin(user))
    except ReviewTaskError as exc:
        _raise_api_error(exc)
    audit.log_operation(actor_id=user.id, action="review_tasks.retry", target=task_id)
    return api_success(task, "review task retried")


@router.get(
    "/{task_id}/events",
    response_model=ApiResponse[list[ReviewTaskEvent]],
    summary="Get review task events",
)
async def get_review_task_events(
    task_id: str,
    user: UserPublic = Depends(get_current_user),
    tasks: ReviewTaskService = Depends(get_task_service),
) -> ApiResponse[list[ReviewTaskEvent]]:
    try:
        return api_success(tasks.events(task_id, actor_id=user.id, as_admin=_is_admin(user)))
    except ReviewTaskError as exc:
        _raise_api_error(exc)
