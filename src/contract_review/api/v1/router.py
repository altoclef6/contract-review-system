from fastapi import APIRouter

from contract_review.api.v1.endpoints import (
    admin,
    analysis_history,
    auth,
    chats,
    contracts,
    health,
    llm,
    model_configs,
    monitoring,
    notifications,
    prompt_templates,
    reader,
    reviews,
    workflows,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证与账号"])
api_router.include_router(admin.router, prefix="/admin", tags=["后台管理"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["合同管理"])
api_router.include_router(model_configs.router, prefix="/model-configs", tags=["模型配置中心"])
api_router.include_router(
    prompt_templates.router, prefix="/prompt-templates", tags=["Prompt 模板中心"]
)
api_router.include_router(workflows.router, prefix="/workflows", tags=["合同审批工作流"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知中心"])
api_router.include_router(reader.router, prefix="/reader", tags=["PDF 在线阅读器"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["系统监控"])
api_router.include_router(chats.router, prefix="/chats", tags=["合同 AI 助手"])
api_router.include_router(
    analysis_history.router,
    prefix="/analysis-history",
    tags=["分析历史与统计"],
)
api_router.include_router(health.router, tags=["系统健康"])
api_router.include_router(llm.router, prefix="/llm", tags=["模型连接验证"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["合同审查"])
