
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from contract_review.api.dependencies.auth import get_audit_service, require_permission
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.rule_center import RuleListResponse, RuleRecord, RuleUpdate
from contract_review.services.audit_service import AuditService
from contract_review.services.rule_center_service import RuleCenterError, RuleCenterService

router = APIRouter()


def get_service(settings: Settings = Depends(get_settings)) -> RuleCenterService:
    return RuleCenterService(settings.rule_center_data_dir, settings.risk_feedback_data_dir)


@router.get("", response_model=ApiResponse[RuleListResponse])
async def list_rules(
    enabled: bool | None = Query(default=None),
    _: UserPublic = Depends(require_permission(Permission.rules_read)),
    service: RuleCenterService = Depends(get_service),
) -> ApiResponse[RuleListResponse]:
    items = service.list_rules()
    if enabled is not None:
        items = [item for item in items if item.enabled is enabled]
    return api_success(RuleListResponse(items=items, total=len(items)))


@router.get("/{rule_id}", response_model=ApiResponse[RuleRecord])
async def get_rule(
    rule_id: str,
    _: UserPublic = Depends(require_permission(Permission.rules_read)),
    service: RuleCenterService = Depends(get_service),
) -> ApiResponse[RuleRecord]:
    try:
        return api_success(service.get(rule_id))
    except RuleCenterError as exc:
        raise HTTPException(status_code=404, detail="规则不存在") from exc


@router.patch("/{rule_id}", response_model=ApiResponse[RuleRecord])
async def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    user: UserPublic = Depends(require_permission(Permission.rules_manage)),
    service: RuleCenterService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[RuleRecord]:
    try:
        record = service.update(rule_id, payload)
    except RuleCenterError as exc:
        raise HTTPException(status_code=404, detail="规则不存在") from exc
    audit.log_operation(
        actor_id=user.id,
        action="rules.update",
        target=rule_id,
        metadata={"fields": sorted(payload.model_fields_set), "version": record.version},
    )
    return api_success(record, "规则配置已更新")
