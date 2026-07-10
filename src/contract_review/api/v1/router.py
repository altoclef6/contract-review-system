from fastapi import APIRouter

from contract_review.api.v1.endpoints import admin, auth, contracts, health, llm, model_configs, prompt_templates, reviews

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证与账号"])
api_router.include_router(admin.router, prefix="/admin", tags=["后台管理"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["合同管理"])
api_router.include_router(model_configs.router, prefix="/model-configs", tags=["模型配置中心"])
api_router.include_router(prompt_templates.router, prefix="/prompt-templates", tags=["Prompt 模板中心"])
api_router.include_router(health.router, tags=["系统健康"])
api_router.include_router(llm.router, prefix="/llm", tags=["模型连接验证"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["合同审查"])
