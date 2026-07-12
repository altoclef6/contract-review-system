from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from contract_review.api.dependencies.auth import (
    get_audit_service,
    get_current_user,
    require_permission,
)
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.contract_management import (
    ContractCategory,
    ContractCreate,
    ContractListResponse,
    ContractRecord,
    ContractSortBy,
    ContractStatus,
    ContractUpdate,
    ContractVersion,
    ContractVersionCreate,
    SortOrder,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.contract_service import ContractService, ContractServiceError

router = APIRouter()


def get_contract_service(settings: Settings = Depends(get_settings)) -> ContractService:
    return ContractService(settings.contract_data_dir)


@router.post(
    "",
    response_model=ApiResponse[ContractRecord],
    status_code=status.HTTP_201_CREATED,
    summary="创建合同",
)
async def create_contract(
    payload: ContractCreate,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    record = contracts.create_contract(payload=payload, actor_id=user.id)
    audit.log_operation(actor_id=user.id, action="contracts.create", target=record.id)
    return api_success(record, "合同已创建")


@router.get("", response_model=ApiResponse[ContractListResponse], summary="合同列表")
async def list_contracts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    category: ContractCategory | None = None,
    status_filter: ContractStatus | None = Query(default=None, alias="status"),
    tag: str | None = Query(default=None, max_length=50),
    sort_by: ContractSortBy = Query(default="updated_at"),
    sort_order: SortOrder = Query(default="desc"),
    include_deleted: bool = False,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
) -> ApiResponse[ContractListResponse]:
    data = contracts.list_contracts(
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        status=status_filter,
        tag=tag,
        sort_by=sort_by,
        sort_order=sort_order,
        include_deleted=include_deleted,
        actor_id=user.id,
        actor_role=user.role.value,
    )
    return api_success(data)


@router.get("/{contract_id}", response_model=ApiResponse[ContractRecord], summary="合同详情")
async def get_contract(
    contract_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        return api_success(contracts.get_contract(contract_id))
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{contract_id}", response_model=ApiResponse[ContractRecord], summary="更新合同")
async def update_contract(
    contract_id: str,
    payload: ContractUpdate,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.update_contract(
            contract_id=contract_id, payload=payload, actor_id=user.id
        )
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.update", target=contract_id)
    return api_success(record, "合同已更新")


@router.post(
    "/{contract_id}/favorite", response_model=ApiResponse[ContractRecord], summary="收藏合同"
)
async def set_favorite(
    contract_id: str,
    favorite: bool = Query(default=True),
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.set_favorite(
            contract_id=contract_id, favorite=favorite, actor_id=user.id
        )
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.favorite", target=contract_id)
    return api_success(record, "收藏状态已更新")


@router.post(
    "/{contract_id}/archive", response_model=ApiResponse[ContractRecord], summary="归档合同"
)
async def archive_contract(
    contract_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.archive(contract_id=contract_id, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.archive", target=contract_id)
    return api_success(record, "合同已归档")


@router.delete("/{contract_id}", response_model=ApiResponse[ContractRecord], summary="删除合同")
async def delete_contract(
    contract_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.delete(contract_id=contract_id, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.delete", target=contract_id)
    return api_success(record, "合同已删除")


@router.post(
    "/{contract_id}/restore", response_model=ApiResponse[ContractRecord], summary="恢复合同"
)
async def restore_contract(
    contract_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.restore(contract_id=contract_id, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.restore", target=contract_id)
    return api_success(record, "合同已恢复")


@router.post(
    "/{contract_id}/versions",
    response_model=ApiResponse[ContractVersion],
    status_code=status.HTTP_201_CREATED,
    summary="创建合同版本",
)
async def create_contract_version(
    contract_id: str,
    payload: ContractVersionCreate,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractVersion]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        version = contracts.add_version(contract_id=contract_id, payload=payload, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.version.create", target=contract_id)
    return api_success(version, "合同版本已创建")


@router.get(
    "/{contract_id}/versions",
    response_model=ApiResponse[list[ContractVersion]],
    summary="合同版本列表",
)
async def list_contract_versions(
    contract_id: str,
    user: UserPublic = Depends(get_current_user),
    contracts: ContractService = Depends(get_contract_service),
) -> ApiResponse[list[ContractVersion]]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        return api_success(contracts.list_versions(contract_id))
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
