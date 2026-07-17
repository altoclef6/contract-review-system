from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from contract_review.api.dependencies.auth import require_permission
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic, UserRole
from contract_review.schemas.reader import ReaderWorkspace, TextLocation, TextLocationResult
from contract_review.services.history_service import HistoryService
from contract_review.services.reader_workspace_service import (
    ReaderWorkspaceError,
    ReaderWorkspaceService,
)

router = APIRouter()


def _review_record(request: Request, review_id: str, user: UserPublic) -> dict[str, Any]:
    settings = request.app.state.settings
    record = HistoryService(settings.report_dir.parent).get(review_id)
    if not record or (user.role != UserRole.admin and record.get("created_by") != user.id):
        raise HTTPException(status_code=404, detail="审查记录不可访问")
    return record


def _source_pdf(request: Request, record: dict[str, Any]) -> Path:
    settings = request.app.state.settings
    if not record.get("source_file_path"):
        raise HTTPException(status_code=404, detail="合同源文件不存在")
    path = Path(record["source_file_path"]).resolve()
    upload_root = settings.upload_dir.resolve()
    try:
        path.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="合同源文件不存在") from exc
    if not path.exists() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="该审查记录没有可预览的 PDF 源文件")
    return path


@router.get("/{review_id}/file", summary="在线预览 PDF 合同")
async def preview_pdf(
    request: Request,
    review_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
) -> FileResponse:
    record = _review_record(request, review_id, user)
    return FileResponse(_source_pdf(request, record), media_type="application/pdf")


@router.get(
    "/{review_id}/workspace",
    response_model=ApiResponse[ReaderWorkspace],
    summary="读取三栏审查工作区",
)
async def get_reader_workspace(
    request: Request,
    review_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
) -> ApiResponse[ReaderWorkspace]:
    record = _review_record(request, review_id, user)
    try:
        return api_success(ReaderWorkspaceService(request.app.state.settings).build(record))
    except ReaderWorkspaceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{review_id}/locations",
    response_model=ApiResponse[TextLocationResult],
    summary="定位 PDF 风险条款",
)
async def locate_pdf_text(
    request: Request,
    review_id: str,
    text: str = Query(min_length=2, max_length=300),
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
) -> ApiResponse[TextLocationResult]:
    record = _review_record(request, review_id, user)
    path = _source_pdf(request, record)
    locations: list[TextLocation] = []
    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            for rectangle in page.search_for(text)[:20]:
                locations.append(
                    TextLocation(
                        page=page_index + 1,
                        x0=rectangle.x0,
                        y0=rectangle.y0,
                        x1=rectangle.x1,
                        y1=rectangle.y1,
                        text=text,
                    )
                )
    return api_success(TextLocationResult(review_id=review_id, query=text, locations=locations))
