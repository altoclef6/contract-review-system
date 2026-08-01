from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from contract_review.api.dependencies.auth import get_audit_service, require_permission
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.agent_task import (
    AgentConfirmation,
    AgentTaskCreate,
    AgentTaskPublic,
    AgentToolDefinition,
)
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic, UserRole
from contract_review.services.agent_task_service import AgentTaskError, AgentTaskService
from contract_review.services.audit_service import AuditService

router = APIRouter()
COMPANY_SCOPE_ROLES = {
    UserRole.admin,
    UserRole.company_admin,
    UserRole.legal_manager,
    UserRole.legal,
}


def get_agent_task_service(settings: Settings = Depends(get_settings)) -> AgentTaskService:
    try:
        return AgentTaskService(settings)
    except AgentTaskError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def company_id_of(user: UserPublic) -> str:
    if not user.company_id:
        raise HTTPException(status_code=409, detail="当前账号尚未加入企业")
    return user.company_id


@router.get("/tools", response_model=ApiResponse[list[AgentToolDefinition]])
async def tools(
    _: UserPublic = Depends(require_permission(Permission.agent_run)),
    tasks: AgentTaskService = Depends(get_agent_task_service),
) -> ApiResponse[list[AgentToolDefinition]]:
    return api_success(tasks.list_tools())


@router.post("", response_model=ApiResponse[AgentTaskPublic], status_code=201)
async def create_task(
    payload: AgentTaskCreate,
    actor: UserPublic = Depends(require_permission(Permission.agent_run)),
    tasks: AgentTaskService = Depends(get_agent_task_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[AgentTaskPublic]:
    company_id = company_id_of(actor)
    try:
        task = tasks.create(
            company_id=company_id,
            actor_id=actor.id,
            task_type=payload.task_type,
            objective=payload.objective,
            contract_id=payload.contract_id,
            context=payload.context,
        )
    except AgentTaskError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=actor.id,
        company_id=company_id,
        action="agent.task.created",
        resource_type="agent_task",
        resource_id=task.id,
        target=task.id,
    )
    return api_success(task)


@router.get("", response_model=ApiResponse[list[AgentTaskPublic]])
async def list_tasks(
    actor: UserPublic = Depends(require_permission(Permission.agent_run)),
    tasks: AgentTaskService = Depends(get_agent_task_service),
) -> ApiResponse[list[AgentTaskPublic]]:
    return api_success(
        tasks.list(
            company_id=company_id_of(actor),
            actor_id=actor.id,
            company_scope=actor.role in COMPANY_SCOPE_ROLES,
        )
    )


@router.get("/{task_id}", response_model=ApiResponse[AgentTaskPublic])
async def get_task(
    task_id: str,
    actor: UserPublic = Depends(require_permission(Permission.agent_run)),
    tasks: AgentTaskService = Depends(get_agent_task_service),
) -> ApiResponse[AgentTaskPublic]:
    try:
        result = tasks.get(
            task_id,
            company_id=company_id_of(actor),
            actor_id=actor.id,
            company_scope=actor.role in COMPANY_SCOPE_ROLES,
        )
    except AgentTaskError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return api_success(result)


@router.post("/{task_id}/run", response_model=ApiResponse[AgentTaskPublic])
async def run_task(
    task_id: str,
    actor: UserPublic = Depends(require_permission(Permission.agent_run)),
    tasks: AgentTaskService = Depends(get_agent_task_service),
) -> ApiResponse[AgentTaskPublic]:
    try:
        result = tasks.run(
            task_id,
            company_id=company_id_of(actor),
            actor_id=actor.id,
            company_scope=actor.role in COMPANY_SCOPE_ROLES,
        )
    except AgentTaskError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return api_success(result)


@router.post("/{task_id}/confirmation", response_model=ApiResponse[AgentTaskPublic])
async def confirm_task(
    task_id: str,
    payload: AgentConfirmation,
    actor: UserPublic = Depends(require_permission(Permission.agent_confirm)),
    tasks: AgentTaskService = Depends(get_agent_task_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[AgentTaskPublic]:
    company_id = company_id_of(actor)
    try:
        result = tasks.confirm(
            task_id,
            company_id=company_id,
            actor_id=actor.id,
            approved=payload.approved,
            note=payload.note,
        )
    except AgentTaskError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=actor.id,
        company_id=company_id,
        action="agent.tool.confirmed" if payload.approved else "agent.tool.rejected",
        resource_type="agent_task",
        resource_id=task_id,
        target=task_id,
    )
    return api_success(result)
