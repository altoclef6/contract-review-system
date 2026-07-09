from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from contract_review.schemas.review import ReviewResponse
from contract_review.services.history_service import HistoryService
from contract_review.services.review_service import ReviewService
from contract_review.utils.file_utils import save_upload_file

router = APIRouter()


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="提交合同审查",
    description=(
        "上传 PDF、Word(.docx) 或扫描件图片合同，系统会解析合同文本，"
        "并执行 LangGraph Multi-Agent 审查流程，返回结构化审查结果。"
    ),
    operation_id="提交合同审查",
    response_description="合同审查任务创建成功，返回结构化审查结果。",
)
async def create_review(
    request: Request,
    合同文件: UploadFile = File(
        ...,
        title="合同文件",
        description="待审查的合同文件，支持 PDF、Word(.docx)、PNG、JPG、TIFF、BMP。",
    ),
    x_llm_api_key: str | None = Header(default=None, include_in_schema=False),
    x_llm_provider: str | None = Header(default=None, include_in_schema=False),
    x_llm_model: str | None = Header(default=None, include_in_schema=False),
    x_llm_base_url: str | None = Header(default=None, include_in_schema=False),
) -> ReviewResponse:
    llm_config = {
        "api_key": x_llm_api_key,
        "provider": x_llm_provider,
        "model_name": x_llm_model,
        "base_url": x_llm_base_url,
    }
    llm_config = {key: value for key, value in llm_config.items() if value}

    settings = request.app.state.settings
    saved_path = await save_upload_file(
        file=合同文件,
        upload_dir=settings.upload_dir,
        max_size_mb=settings.max_upload_size_mb,
    )
    service = ReviewService(
        graph=request.app.state.contract_review_graph,
        settings=settings,
    )
    return await service.review_file(
        file_path=saved_path,
        original_file_name=合同文件.filename or saved_path.name,
        content_type=合同文件.content_type,
        llm_config=llm_config,
    )


@router.get("", summary="审查历史", operation_id="审查历史")
async def list_reviews(request: Request) -> list[dict]:
    service = HistoryService(request.app.state.settings.report_dir.parent)
    return service.list_records()


@router.get("/{review_id}", summary="查看审查报告", operation_id="查看审查报告")
async def get_review(request: Request, review_id: str) -> dict:
    record = HistoryService(request.app.state.settings.report_dir.parent).get(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到审查记录")
    json_path = record.get("exports", {}).get("json") or record.get("report_path")
    if not json_path or not Path(json_path).exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")
    return json.loads(Path(json_path).read_text(encoding="utf-8"))


@router.get("/{review_id}/download", summary="下载审查报告", operation_id="下载审查报告")
async def download_review(
    request: Request,
    review_id: str,
    file_type: str = Query(default="pdf", pattern="^(json|docx|pdf)$"),
) -> FileResponse:
    record = HistoryService(request.app.state.settings.report_dir.parent).get(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到审查记录")
    file_path = record.get("exports", {}).get(file_type)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="导出文件不存在")
    media_types = {
        "json": "application/json",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    return FileResponse(
        file_path,
        media_type=media_types[file_type],
        filename=f"{review_id}.{file_type}",
    )
