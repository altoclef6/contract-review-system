
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from contract_review.api.dependencies.auth import get_audit_service, get_current_user
from contract_review.api.v1.endpoints.contracts import get_contract_service
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import UserPublic, UserRole
from contract_review.schemas.contract_management import ContractRecord
from contract_review.schemas.version_comparison import (
    FeedbackStatistics,
    RiskFeedbackCreate,
    RiskFeedbackRecord,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.contract_service import ContractService, ContractServiceError
from contract_review.services.risk_feedback_service import RiskFeedbackError, RiskFeedbackService

router = APIRouter()


def get_service(settings: Settings = Depends(get_settings)) -> RiskFeedbackService:
    return RiskFeedbackService(settings.risk_feedback_data_dir)


def _contract_for_user(
    contract_id: str, user: UserPublic, contracts: ContractService
) -> ContractRecord:
    try:
        contract = contracts.get_contract(contract_id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=404, detail="合同不存在或无权访问") from exc
    if user.role == UserRole.employee and contract.created_by != user.id:
        raise HTTPException(status_code=404, detail="合同不存在或无权访问")
    return contract


@router.post("", response_model=ApiResponse[RiskFeedbackRecord], status_code=201)
async def create_feedback(
    payload: RiskFeedbackCreate,
    user: UserPublic = Depends(get_current_user),
    service: RiskFeedbackService = Depends(get_service),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RiskFeedbackRecord]:
    contract = _contract_for_user(payload.contract_id, user, contracts)
    version = next(
        (item for item in contract.versions if item.id == payload.contract_version_id), None
    )
    if version is None:
        raise HTTPException(status_code=404, detail="合同版本不存在或无权访问")
    risk_ids = {
        str(item.get("risk_id") or item.get("风险编号") or "") for item in version.risk_snapshot
    }
    if payload.risk_id not in risk_ids:
        raise HTTPException(status_code=404, detail="风险不存在或无权访问")
    try:
        record = service.create(payload, user.id)
    except RiskFeedbackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=user.id,
        action="risks.feedback.create",
        target=record.risk_id,
        metadata={"feedback_id": record.id, "feedback_type": record.feedback_type.value},
    )
    return api_success(record, "反馈已保存；该反馈不会自动训练模型")


@router.get("", response_model=ApiResponse[list[RiskFeedbackRecord]])
async def list_feedback(
    contract_id: str = Query(min_length=1, max_length=120),
    user: UserPublic = Depends(get_current_user),
    service: RiskFeedbackService = Depends(get_service),
    contracts: ContractService = Depends(get_contract_service),
) -> ApiResponse[list[RiskFeedbackRecord]]:
    _contract_for_user(contract_id, user, contracts)
    return api_success(service.list_records(contract_id))


@router.get("/statistics", response_model=ApiResponse[FeedbackStatistics])
async def get_feedback_statistics(
    user: UserPublic = Depends(get_current_user),
    service: RiskFeedbackService = Depends(get_service),
) -> ApiResponse[FeedbackStatistics]:
    if user.role == UserRole.employee:
        raise HTTPException(status_code=403, detail="权限不足")
    return api_success(service.statistics())
