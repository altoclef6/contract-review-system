from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from contract_review.api.dependencies.auth import get_audit_service, get_current_user
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import UserPublic
from contract_review.schemas.workflow import WorkflowActionRequest, WorkflowCreate, WorkflowPublic
from contract_review.services.audit_service import AuditService
from contract_review.services.notification_service import NotificationService
from contract_review.services.workflow_service import WorkflowService, WorkflowServiceError

router = APIRouter()


def get_workflow_service(request: Request) -> WorkflowService:
    settings = request.app.state.settings
    return WorkflowService(
        settings.workflow_data_dir,
        NotificationService(settings.notification_data_dir),
    )


@router.post(
    "", response_model=ApiResponse[WorkflowPublic], status_code=201, summary="发起合同审批"
)
async def create_workflow(
    payload: WorkflowCreate,
    actor: UserPublic = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[WorkflowPublic]:
    try:
        workflow = service.create(payload.contract_id, payload.review_id, actor)
    except WorkflowServiceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log_operation(actor_id=actor.id, action="workflows.create", target=workflow.id)
    return api_success(workflow, "合同审批已发起")


@router.get("", response_model=ApiResponse[list[WorkflowPublic]], summary="审批流程列表")
async def list_workflows(
    actor: UserPublic = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
) -> ApiResponse[list[WorkflowPublic]]:
    return api_success(service.list_for_user(actor))


@router.get("/{workflow_id}", response_model=ApiResponse[WorkflowPublic], summary="审批流程详情")
async def get_workflow(
    workflow_id: str,
    actor: UserPublic = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
) -> ApiResponse[WorkflowPublic]:
    try:
        return api_success(service.get(workflow_id, actor))
    except WorkflowServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{workflow_id}/actions", response_model=ApiResponse[WorkflowPublic], summary="执行审批操作"
)
async def act_on_workflow(
    workflow_id: str,
    payload: WorkflowActionRequest,
    actor: UserPublic = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[WorkflowPublic]:
    try:
        workflow = service.act(workflow_id, payload, actor)
    except WorkflowServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=actor.id,
        action=f"workflows.{payload.action.value}",
        target=workflow_id,
    )
    return api_success(workflow, "审批状态已更新")
