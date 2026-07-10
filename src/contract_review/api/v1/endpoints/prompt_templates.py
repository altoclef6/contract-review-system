from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from contract_review.api.dependencies.auth import get_audit_service, require_permission
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.prompt_template import (
    ContractType,
    PromptStage,
    PromptTemplateCreate,
    PromptTemplatePublic,
    PromptTemplateUpdate,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.prompt_template_service import PromptTemplateService, PromptTemplateServiceError

router = APIRouter()


def get_prompt_service(settings: Settings = Depends(get_settings)) -> PromptTemplateService:
    return PromptTemplateService(settings.prompt_template_data_dir)


@router.get("", response_model=ApiResponse[list[PromptTemplatePublic]], summary="Prompt 模板列表")
async def list_prompt_templates(
    contract_type: ContractType | None = Query(default=None, description="合同类型"),
    stage: PromptStage | None = Query(default=None, description="Agent 阶段"),
    _: UserPublic = Depends(require_permission(Permission.prompts_manage)),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ApiResponse[list[PromptTemplatePublic]]:
    return api_success(service.list_templates(contract_type=contract_type, stage=stage))


@router.post("", response_model=ApiResponse[PromptTemplatePublic], status_code=201, summary="创建 Prompt 模板")
async def create_prompt_template(
    payload: PromptTemplateCreate,
    user: UserPublic = Depends(require_permission(Permission.prompts_manage)),
    service: PromptTemplateService = Depends(get_prompt_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[PromptTemplatePublic]:
    record = service.create(payload, user.id)
    audit.log_operation(actor_id=user.id, action="prompts.create", target=record.id)
    return api_success(record, "Prompt 模板已创建")


@router.get("/{template_id}", response_model=ApiResponse[PromptTemplatePublic], summary="Prompt 模板详情")
async def get_prompt_template(
    template_id: str,
    _: UserPublic = Depends(require_permission(Permission.prompts_manage)),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ApiResponse[PromptTemplatePublic]:
    try:
        return api_success(service.get(template_id))
    except PromptTemplateServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{template_id}", response_model=ApiResponse[PromptTemplatePublic], summary="更新 Prompt 模板")
async def update_prompt_template(
    template_id: str,
    payload: PromptTemplateUpdate,
    user: UserPublic = Depends(require_permission(Permission.prompts_manage)),
    service: PromptTemplateService = Depends(get_prompt_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[PromptTemplatePublic]:
    try:
        record = service.update(template_id, payload, user.id)
    except PromptTemplateServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="prompts.update", target=template_id)
    return api_success(record, "Prompt 模板已更新")


@router.post("/{template_id}/default", response_model=ApiResponse[PromptTemplatePublic], summary="设为默认 Prompt 模板")
async def set_default_prompt_template(
    template_id: str,
    user: UserPublic = Depends(require_permission(Permission.prompts_manage)),
    service: PromptTemplateService = Depends(get_prompt_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[PromptTemplatePublic]:
    try:
        record = service.set_default(template_id, user.id)
    except PromptTemplateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="prompts.default", target=template_id)
    return api_success(record, "默认 Prompt 模板已更新")


@router.delete("/{template_id}", response_model=ApiResponse[PromptTemplatePublic], summary="删除 Prompt 模板")
async def delete_prompt_template(
    template_id: str,
    user: UserPublic = Depends(require_permission(Permission.prompts_manage)),
    service: PromptTemplateService = Depends(get_prompt_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[PromptTemplatePublic]:
    try:
        record = service.delete(template_id)
    except PromptTemplateServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="prompts.delete", target=template_id)
    return api_success(record, "Prompt 模板已删除")
