from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from contract_review.api.dependencies.auth import require_permission
from contract_review.schemas.analysis_history import (
    AnalysisHistoryPage,
    AnalysisRecord,
    AnalysisStatistics,
)
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.services.history_service import HistoryService

router = APIRouter()


def get_history_service(request: Request) -> HistoryService:
    return HistoryService(request.app.state.settings.report_dir.parent)


@router.get("", response_model=ApiResponse[AnalysisHistoryPage], summary="分析历史列表")
async def list_analysis_history(
    keyword: str | None = Query(default=None, max_length=100),
    risk_level: str | None = Query(default=None, max_length=20),
    contract_type: str | None = Query(default=None, max_length=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: UserPublic = Depends(require_permission(Permission.reviews_history)),
    service: HistoryService = Depends(get_history_service),
) -> ApiResponse[AnalysisHistoryPage]:
    records, total = service.search(
        keyword=keyword,
        risk_level=risk_level,
        contract_type=contract_type,
        page=page,
        page_size=page_size,
    )
    return api_success(
        AnalysisHistoryPage(
            items=[AnalysisRecord.model_validate(item) for item in records],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/statistics", response_model=ApiResponse[AnalysisStatistics], summary="分析统计")
async def get_analysis_statistics(
    _: UserPublic = Depends(require_permission(Permission.reviews_history)),
    service: HistoryService = Depends(get_history_service),
) -> ApiResponse[AnalysisStatistics]:
    return api_success(AnalysisStatistics.model_validate(service.statistics()))


@router.get("/{review_id}", response_model=ApiResponse[AnalysisRecord], summary="分析历史详情")
async def get_analysis_history(
    review_id: str,
    _: UserPublic = Depends(require_permission(Permission.reviews_history)),
    service: HistoryService = Depends(get_history_service),
) -> ApiResponse[AnalysisRecord]:
    record = service.get(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return api_success(AnalysisRecord.model_validate(record))
