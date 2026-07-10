from __future__ import annotations

from pathlib import Path

import fitz
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from contract_review.api.dependencies.auth import require_permission
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.reader import TextLocation, TextLocationResult
from contract_review.services.history_service import HistoryService

router = APIRouter()


def _source_pdf(request: Request, review_id: str) -> Path:
    settings = request.app.state.settings
    record = HistoryService(settings.report_dir.parent).get(review_id)
    if not record or not record.get("source_file_path"):
        raise HTTPException(status_code=404, detail="合同源文件不存在")
    path = Path(record["source_file_path"]).resolve()
    upload_root = settings.upload_dir.resolve()
    try:
        path.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="合同源文件路径无效") from exc
    if not path.exists() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="该审查记录没有可预览的 PDF 源文件")
    return path


@router.get("/{review_id}/file", summary="在线预览 PDF 合同")
async def preview_pdf(
    request: Request,
    review_id: str,
    _: UserPublic = Depends(require_permission(Permission.contracts_read)),
) -> FileResponse:
    return FileResponse(_source_pdf(request, review_id), media_type="application/pdf")


@router.get(
    "/{review_id}/locations",
    response_model=ApiResponse[TextLocationResult],
    summary="定位 PDF 风险条款",
)
async def locate_pdf_text(
    request: Request,
    review_id: str,
    text: str = Query(min_length=2, max_length=300),
    _: UserPublic = Depends(require_permission(Permission.contracts_read)),
) -> ApiResponse[TextLocationResult]:
    path = _source_pdf(request, review_id)
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
