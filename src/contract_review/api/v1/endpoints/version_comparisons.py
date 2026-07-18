
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from contract_review.api.dependencies.auth import get_current_user
from contract_review.api.v1.endpoints.contracts import get_contract_service
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import UserPublic, UserRole
from contract_review.schemas.contract_management import ContractRecord
from contract_review.schemas.version_comparison import (
    VersionCompareRequest,
    VersionComparisonResult,
)
from contract_review.services.contract_service import ContractService, ContractServiceError
from contract_review.services.version_comparison_service import (
    VersionComparisonError,
    VersionComparisonService,
)

router = APIRouter()


def _require_contract_access(
    contract_id: str, user: UserPublic, service: ContractService
) -> ContractRecord:
    try:
        contract = service.get_contract(contract_id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=404, detail="合同不存在或无权访问") from exc
    if user.role == UserRole.employee and contract.created_by != user.id:
        raise HTTPException(status_code=404, detail="合同不存在或无权访问")
    return contract


@router.post("/{contract_id}", response_model=ApiResponse[VersionComparisonResult])
async def compare_versions(
    contract_id: str,
    payload: VersionCompareRequest,
    user: UserPublic = Depends(get_current_user),
    contracts: ContractService = Depends(get_contract_service),
) -> ApiResponse[VersionComparisonResult]:
    contract = _require_contract_access(contract_id, user, contracts)
    versions = {}
    for item in contract.versions:
        version_data = item.model_dump(mode="json")
        version_data["text_content"] = item.text_content
        version_data["risk_snapshot"] = item.risk_snapshot
        versions[item.id] = version_data
    if payload.base_version_id not in versions or payload.target_version_id not in versions:
        raise HTTPException(status_code=404, detail="合同版本不存在或无权访问")
    try:
        result = VersionComparisonService().compare_snapshots(
            contract_id=contract_id,
            base_version=versions[payload.base_version_id],
            target_version=versions[payload.target_version_id],
        )
    except VersionComparisonError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return api_success(result)
