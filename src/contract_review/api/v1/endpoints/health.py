from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    summary="健康检查",
    description="检查后端服务是否已成功启动，并确认接口能够正常响应请求。",
    operation_id="健康检查",
)
async def health_check() -> dict[str, str]:
    return {"status": "正常"}
