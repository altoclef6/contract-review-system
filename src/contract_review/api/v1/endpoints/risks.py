from __future__ import annotations

# FastAPI dependency/query markers are intentionally declared as defaults.
# ruff: noqa: B008
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from contract_review.api.dependencies.auth import get_audit_service, get_current_user
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import UserPublic
from contract_review.schemas.risk import (
    RiskAssignRequest,
    RiskCommentRequest,
    RiskListResponse,
    RiskRecord,
    RiskRevisionRequest,
    RiskStatus,
    RiskTransitionRequest,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.risk_service import (
    RiskConflictError,
    RiskPermissionError,
    RiskService,
    RiskServiceError,
    RiskTransitionError,
)

router = APIRouter()


def get_risk_service(settings: Settings = Depends(get_settings)) -> RiskService:
    return RiskService(settings)


def _raise(exc: RiskServiceError) -> None:
    if isinstance(exc, RiskPermissionError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, (RiskConflictError, RiskTransitionError)):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_404_NOT_FOUND
    raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("", response_model=ApiResponse[RiskListResponse], summary="风险分页台账")
async def list_risks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    severity: str | None = Query(default=None, max_length=20),
    category: str | None = Query(default=None, max_length=80),
    status_filter: RiskStatus | None = Query(default=None, alias="status"),
    assignee_id: str | None = Query(default=None, max_length=64),
    contract_type: str | None = Query(default=None, max_length=40),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    review_id: str | None = Query(default=None, max_length=64),
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
) -> ApiResponse[RiskListResponse]:
    return api_success(
        risks.list_risks(
            page=page,
            page_size=page_size,
            actor_id=user.id,
            actor_role=user.role.value,
            keyword=keyword,
            severity=severity,
            category=category,
            status=status_filter,
            assignee_id=assignee_id,
            contract_type=contract_type,
            date_from=date_from,
            date_to=date_to,
            review_id=review_id,
        )
    )


@router.get("/{risk_id}", response_model=ApiResponse[RiskRecord], summary="风险详情")
async def get_risk(
    risk_id: str,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
) -> ApiResponse[RiskRecord]:
    try:
        return api_success(risks.get(risk_id, actor_id=user.id, actor_role=user.role.value))
    except RiskServiceError as exc:
        _raise(exc)


async def _transition(
    risk_id: str,
    target: RiskStatus,
    payload: RiskTransitionRequest,
    user: UserPublic,
    risks: RiskService,
    audit: AuditService,
) -> ApiResponse[RiskRecord]:
    try:
        record, old_status = risks.transition(
            risk_id,
            target=target,
            actor_id=user.id,
            actor_role=user.role.value,
            expected_revision=payload.expected_revision,
            reason=payload.reason,
        )
    except RiskServiceError as exc:
        _raise(exc)
    audit.log_operation(
        actor_id=user.id,
        action="risks.transition",
        target=risk_id,
        metadata={
            "old_status": old_status.value,
            "new_status": target.value,
            "reason": payload.reason,
        },
    )
    return api_success(record, "风险状态已更新")


@router.post("/{risk_id}/confirm", response_model=ApiResponse[RiskRecord])
async def confirm_risk(
    risk_id: str,
    payload: RiskTransitionRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    return await _transition(risk_id, RiskStatus.confirmed, payload, user, risks, audit)


@router.post("/{risk_id}/reject", response_model=ApiResponse[RiskRecord])
async def reject_risk(
    risk_id: str,
    payload: RiskTransitionRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    return await _transition(risk_id, RiskStatus.rejected, payload, user, risks, audit)


@router.post("/{risk_id}/start-remediation", response_model=ApiResponse[RiskRecord])
async def start_remediation(
    risk_id: str,
    payload: RiskTransitionRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    return await _transition(risk_id, RiskStatus.remediating, payload, user, risks, audit)


@router.post("/{risk_id}/mark-remediated", response_model=ApiResponse[RiskRecord])
async def mark_remediated(
    risk_id: str,
    payload: RiskTransitionRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    return await _transition(risk_id, RiskStatus.remediated, payload, user, risks, audit)


@router.post("/{risk_id}/close", response_model=ApiResponse[RiskRecord])
async def close_risk(
    risk_id: str,
    payload: RiskTransitionRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    return await _transition(risk_id, RiskStatus.closed, payload, user, risks, audit)


@router.post("/{risk_id}/assign", response_model=ApiResponse[RiskRecord])
async def assign_risk(
    risk_id: str,
    payload: RiskAssignRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    try:
        record = risks.assign(
            risk_id,
            assignee_id=payload.assignee_id,
            actor_id=user.id,
            actor_role=user.role.value,
            expected_revision=payload.expected_revision,
        )
    except RiskServiceError as exc:
        _raise(exc)
    audit.log_operation(
        actor_id=user.id,
        action="risks.assign",
        target=risk_id,
        metadata={"assignee_id": payload.assignee_id},
    )
    return api_success(record, "风险负责人已更新")


@router.post("/{risk_id}/comments", response_model=ApiResponse[RiskRecord])
async def add_risk_comment(
    risk_id: str,
    payload: RiskCommentRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    try:
        record = risks.add_comment(
            risk_id,
            content=payload.content,
            actor_id=user.id,
            actor_role=user.role.value,
            expected_revision=payload.expected_revision,
        )
    except RiskServiceError as exc:
        _raise(exc)
    audit.log_operation(
        actor_id=user.id,
        action="risks.comment",
        target=risk_id,
        metadata={"comment_length": len(payload.content)},
    )
    return api_success(record, "评论已添加")


@router.put("/{risk_id}/revised-clause", response_model=ApiResponse[RiskRecord])
async def save_revised_clause(
    risk_id: str,
    payload: RiskRevisionRequest,
    user: UserPublic = Depends(get_current_user),
    risks: RiskService = Depends(get_risk_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskRecord]:
    try:
        record = risks.save_revision(
            risk_id,
            revised_clause=payload.revised_clause,
            actor_id=user.id,
            actor_role=user.role.value,
            expected_revision=payload.expected_revision,
        )
    except RiskServiceError as exc:
        _raise(exc)
    audit.log_operation(
        actor_id=user.id,
        action="risks.revision.save",
        target=risk_id,
        metadata={"content_length": len(payload.revised_clause)},
    )
    return api_success(record, "人工修改条款已保存")
