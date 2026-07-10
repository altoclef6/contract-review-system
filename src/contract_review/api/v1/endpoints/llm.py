from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from contract_review.llm.json_client import call_llm_json

router = APIRouter()


class LLMValidateRequest(BaseModel):
    provider: str = Field(default="deepseek", title="服务商")
    api_key: str = Field(min_length=8, title="API Key")
    model_name: str = Field(default="deepseek-chat", title="模型名称")
    base_url: str = Field(default="https://api.deepseek.com/v1", title="Base URL")


class LLMValidateResponse(BaseModel):
    status: str = Field(title="验证状态")
    provider: str = Field(title="服务商")
    model_name: str = Field(title="模型名称")
    base_url: str = Field(title="Base URL")
    latency_ms: int = Field(title="响应耗时毫秒")
    message: str = Field(title="验证说明")


@router.post(
    "/validate",
    response_model=LLMValidateResponse,
    summary="验证模型 API Key",
    operation_id="验证模型APIKey",
)
async def validate_llm_config(payload: LLMValidateRequest) -> LLMValidateResponse:
    started = time.perf_counter()
    result = await call_llm_json(
        "你是模型连通性检查器。请只输出 JSON，不要输出 Markdown。",
        '{"任务":"请返回 {"ok": true, "message": "连接成功"}"}',
        max_chars=200,
        llm_config={
            "provider": payload.provider,
            "api_key": payload.api_key,
            "model_name": payload.model_name,
            "base_url": payload.base_url,
        },
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模型 API 验证失败，请检查 Key、模型名称、Base URL 或账户余额。",
        )

    return LLMValidateResponse(
        status="可用",
        provider=payload.provider,
        model_name=payload.model_name,
        base_url=payload.base_url,
        latency_ms=latency_ms,
        message=str(result.get("message") or "连接成功"),
    )
