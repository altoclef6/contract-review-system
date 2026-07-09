from fastapi import APIRouter

from contract_review.api.v1.endpoints import health, llm, reviews

api_router = APIRouter()
api_router.include_router(health.router, tags=["系统健康"])
api_router.include_router(llm.router, prefix="/llm", tags=["模型配置"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["合同审查"])
