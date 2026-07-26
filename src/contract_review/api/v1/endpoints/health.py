from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from contract_review.core.config import get_settings
from contract_review.database.session import get_engine
from contract_review.infrastructure.cache import CacheService

router = APIRouter()


@router.get(
    "/health",
    summary="健康检查",
    description="检查后端服务是否已成功启动，并确认接口能够正常响应请求。",
    operation_id="健康检查",
)
async def health_check() -> dict[str, str]:
    return {"status": "正常"}


@router.get("/health/live", summary="存活检查")
async def liveness_check() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", summary="就绪检查")
async def readiness_check() -> dict[str, str | dict[str, str]]:
    settings = get_settings()
    checks: dict[str, str] = {}
    if settings.database_enabled:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["database"] = "ready"
        except Exception:
            checks["database"] = "unavailable"
    else:
        checks["database"] = "disabled"
    if settings.redis_enabled:
        checks["redis"] = "ready" if CacheService(settings).ping() else "unavailable"
    else:
        checks["redis"] = "disabled"
    for name, directory in {
        "uploads": settings.upload_dir,
        "reports": settings.report_dir,
    }.items():
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            checks[name] = "ready"
        except OSError:
            checks[name] = "unavailable"
    if "unavailable" in checks.values():
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}
