from __future__ import annotations

import psutil
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from contract_review.api.dependencies.auth import require_role
from contract_review.core.metrics import metrics_registry
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import UserPublic, UserRole
from contract_review.schemas.monitoring import SystemStatus

router = APIRouter()


@router.get("/status", response_model=ApiResponse[SystemStatus], summary="系统运行状态")
async def system_status(
    request: Request,
    _: UserPublic = Depends(require_role(UserRole.admin)),
) -> ApiResponse[SystemStatus]:
    memory = psutil.virtual_memory()
    settings = request.app.state.settings
    return api_success(
        SystemStatus(
            status="正常",
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=memory.percent,
            memory_used_mb=round(memory.used / 1024 / 1024, 2),
            metrics=metrics_registry.snapshot(),
            database_enabled=settings.database_enabled,
            redis_enabled=settings.redis_enabled,
        )
    )


@router.get("/metrics", response_class=PlainTextResponse, summary="Prometheus 指标")
async def prometheus_metrics() -> str:
    snapshot = metrics_registry.snapshot()
    lines = [
        "# HELP contract_review_requests_total Total HTTP requests.",
        "# TYPE contract_review_requests_total counter",
        f"contract_review_requests_total {snapshot['requests_total']}",
        "# TYPE contract_review_errors_total counter",
        f"contract_review_errors_total {snapshot['errors_total']}",
        "# TYPE contract_review_ai_calls_total counter",
        f"contract_review_ai_calls_total {snapshot['ai_calls_total']}",
        "# TYPE contract_review_ai_errors_total counter",
        f"contract_review_ai_errors_total {snapshot['ai_errors_total']}",
        "# TYPE contract_review_request_duration_ms gauge",
        f"contract_review_request_duration_ms {snapshot['average_request_ms']}",
    ]
    return "\n".join(lines) + "\n"
