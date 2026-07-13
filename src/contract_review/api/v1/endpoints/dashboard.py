from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from contract_review.api.dependencies.auth import get_current_user
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import UserPublic
from contract_review.schemas.dashboard import DashboardSummary
from contract_review.services.dashboard_service import DashboardService
from contract_review.services.history_service import HistoryService
from contract_review.services.notification_service import NotificationService
from contract_review.services.workflow_service import WorkflowService

router = APIRouter()


def get_dashboard_service(request: Request) -> DashboardService:
    settings = request.app.state.settings
    return DashboardService(
        history=HistoryService(settings.report_dir.parent),
        workflows=WorkflowService(settings.workflow_data_dir, NotificationService(settings.notification_data_dir)),
    )


@router.get(
    "/summary",
    response_model=ApiResponse[DashboardSummary],
    summary="企业工作台聚合数据",
    description=("使用 UTC 自然月和最近 30 个 UTC 自然日统计。管理员按现有全局权限查看，其他角色仅聚合本人创建的审查和本人提交的工作流。无法可靠计算的指标返回 null。"),
)
async def get_dashboard_summary(
    actor: Annotated[UserPublic, Depends(get_current_user)],
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> ApiResponse[DashboardSummary]:
    return api_success(service.summary(actor))
