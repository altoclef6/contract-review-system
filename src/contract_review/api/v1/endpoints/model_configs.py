from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from contract_review.api.dependencies.auth import get_audit_service, require_permission
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.model_config import (
    ActiveModelConfig,
    ModelConfigCreate,
    ModelConfigPublic,
    ModelConfigUpdate,
    ModelProviderInfo,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.model_config_service import (
    ModelConfigService,
    ModelConfigServiceError,
)

router = APIRouter()


def get_model_config_service(settings: Settings = Depends(get_settings)) -> ModelConfigService:
    return ModelConfigService(
        settings.model_config_data_dir,
        settings.jwt_secret_key.get_secret_value(),
    )


@router.get("/providers", response_model=ApiResponse[list[ModelProviderInfo]], summary="模型服务商列表")
async def list_model_providers(
    _: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ApiResponse[list[ModelProviderInfo]]:
    return api_success(service.list_providers())


@router.post(
    "",
    response_model=ApiResponse[ModelConfigPublic],
    status_code=status.HTTP_201_CREATED,
    summary="创建模型配置",
)
async def create_model_config(
    payload: ModelConfigCreate,
    user: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ModelConfigPublic]:
    record = service.create(payload=payload, actor_id=user.id)
    audit.log_operation(actor_id=user.id, action="models.create", target=record.id)
    return api_success(record, "模型配置已创建")


@router.get("", response_model=ApiResponse[list[ModelConfigPublic]], summary="模型配置列表")
async def list_model_configs(
    _: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ApiResponse[list[ModelConfigPublic]]:
    return api_success(service.list_configs())


@router.get("/active", response_model=ApiResponse[ActiveModelConfig], summary="当前启用模型")
async def get_active_model_config(
    _: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ApiResponse[ActiveModelConfig]:
    return api_success(ActiveModelConfig(config=service.get_active()))


@router.get("/{config_id}", response_model=ApiResponse[ModelConfigPublic], summary="模型配置详情")
async def get_model_config(
    config_id: str,
    _: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ApiResponse[ModelConfigPublic]:
    try:
        return api_success(service.get(config_id))
    except ModelConfigServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{config_id}", response_model=ApiResponse[ModelConfigPublic], summary="更新模型配置")
async def update_model_config(
    config_id: str,
    payload: ModelConfigUpdate,
    user: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ModelConfigPublic]:
    try:
        record = service.update(config_id=config_id, payload=payload, actor_id=user.id)
    except ModelConfigServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="models.update", target=config_id)
    return api_success(record, "模型配置已更新")


@router.post("/{config_id}/active", response_model=ApiResponse[ModelConfigPublic], summary="启用模型配置")
async def activate_model_config(
    config_id: str,
    user: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ModelConfigPublic]:
    try:
        record = service.set_active(config_id=config_id, actor_id=user.id)
    except ModelConfigServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="models.activate", target=config_id)
    return api_success(record, "模型配置已启用")


@router.delete("/{config_id}", response_model=ApiResponse[ModelConfigPublic], summary="删除模型配置")
async def delete_model_config(
    config_id: str,
    user: UserPublic = Depends(require_permission(Permission.models_manage)),
    service: ModelConfigService = Depends(get_model_config_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ModelConfigPublic]:
    try:
        record = service.delete(config_id=config_id, actor_id=user.id)
    except ModelConfigServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="models.delete", target=config_id)
    return api_success(record, "模型配置已删除")
