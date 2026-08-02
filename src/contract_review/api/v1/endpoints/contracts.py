from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from contract_review.api.dependencies.auth import (
    get_audit_service,
    get_current_user,
    get_user_service,
    require_permission,
)
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.contract_clause import ContractClause
from contract_review.schemas.contract_management import (
    ContractAuditEntry,
    ContractCategory,
    ContractCreate,
    ContractDetail,
    ContractListResponse,
    ContractRecord,
    ContractReviewSummary,
    ContractSortBy,
    ContractStatus,
    ContractUpdate,
    ContractVersion,
    ContractVersionCreate,
    SortOrder,
    VersionCompareRequest,
    VersionComparison,
)
from contract_review.schemas.review_task import ReviewTaskCreate, ReviewTaskRecord
from contract_review.services.audit_service import AuditService
from contract_review.services.contract_clause_service import ContractClauseService
from contract_review.services.contract_service import ContractService, ContractServiceError
from contract_review.services.document_loader import DocumentLoader
from contract_review.services.history_service import HistoryService
from contract_review.services.review_task_service import ReviewTaskService
from contract_review.services.user_service import UserService
from contract_review.utils.file_utils import (
    normalize_original_filename,
    sanitize_filename,
    save_upload_file,
)

router = APIRouter()


def get_contract_service(settings: Settings = Depends(get_settings)) -> ContractService:
    return ContractService(settings.contract_data_dir)


@router.post(
    "",
    response_model=ApiResponse[ContractRecord],
    status_code=status.HTTP_201_CREATED,
    summary="创建合同",
)
async def create_contract(
    payload: ContractCreate,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    record = contracts.create_contract(
        payload=payload,
        actor_id=user.id,
        company_id=user.company_id,
        department_id=user.department_id,
    )
    audit.log_operation(actor_id=user.id, action="contracts.create", target=record.id)
    return api_success(record.model_copy(update={"owner_name": user.full_name}), "合同已创建")


@router.get("", response_model=ApiResponse[ContractListResponse], summary="合同列表")
async def list_contracts(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    category: ContractCategory | None = None,
    status_filter: ContractStatus | None = Query(default=None, alias="status"),
    tag: str | None = Query(default=None, max_length=50),
    sort_by: ContractSortBy = Query(default="updated_at"),
    sort_order: SortOrder = Query(default="desc"),
    include_deleted: bool = False,
    risk_level: str | None = Query(default=None, max_length=30),
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
    users: UserService = Depends(get_user_service),
) -> ApiResponse[ContractListResponse]:
    owner_names = {item.id: item.full_name for item in users.list_users()}
    review_records = HistoryService(request.app.state.settings.report_dir.parent).list_records()
    data = contracts.list_contracts(
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        status=status_filter,
        tag=tag,
        sort_by=sort_by,
        sort_order=sort_order,
        include_deleted=include_deleted,
        risk_level=risk_level,
        review_records=review_records,
        owner_names=owner_names,
        actor_id=user.id,
        actor_role=user.role.value,
        company_id=user.company_id,
    )
    return api_success(data)


@router.get("/{contract_id}", response_model=ApiResponse[ContractRecord], summary="合同详情")
async def get_contract(
    contract_id: str,
    request: Request,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
    users: UserService = Depends(get_user_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        owner_names = {item.id: item.full_name for item in users.list_users()}
        records = HistoryService(request.app.state.settings.report_dir.parent).list_records()
        return api_success(
            contracts.get_contract_enriched(
                contract_id,
                review_records=records,
                owner_names=owner_names,
            )
        )
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{contract_id}", response_model=ApiResponse[ContractRecord], summary="更新合同")
async def update_contract(
    contract_id: str,
    payload: ContractUpdate,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.update_contract(
            contract_id=contract_id, payload=payload, actor_id=user.id
        )
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.update", target=contract_id)
    return api_success(record, "合同已更新")


@router.post(
    "/{contract_id}/favorite", response_model=ApiResponse[ContractRecord], summary="收藏合同"
)
async def set_favorite(
    contract_id: str,
    favorite: bool = Query(default=True),
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.set_favorite(
            contract_id=contract_id, favorite=favorite, actor_id=user.id
        )
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.favorite", target=contract_id)
    return api_success(record, "收藏状态已更新")


@router.post(
    "/{contract_id}/archive", response_model=ApiResponse[ContractRecord], summary="归档合同"
)
async def archive_contract(
    contract_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.archive(contract_id=contract_id, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.archive", target=contract_id)
    return api_success(record, "合同已归档")


@router.delete("/{contract_id}", response_model=ApiResponse[ContractRecord], summary="删除合同")
async def delete_contract(
    contract_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.delete(contract_id=contract_id, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.delete", target=contract_id)
    return api_success(record, "合同已删除")


@router.post(
    "/{contract_id}/restore", response_model=ApiResponse[ContractRecord], summary="恢复合同"
)
async def restore_contract(
    contract_id: str,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        record = contracts.restore(contract_id=contract_id, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.restore", target=contract_id)
    return api_success(record, "合同已恢复")


@router.post(
    "/{contract_id}/versions",
    response_model=ApiResponse[ContractVersion],
    status_code=status.HTTP_201_CREATED,
    summary="创建合同版本",
)
async def create_contract_version(
    contract_id: str,
    payload: ContractVersionCreate,
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractVersion]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        version = contracts.add_version(contract_id=contract_id, payload=payload, actor_id=user.id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.version.create", target=contract_id)
    return api_success(version, "合同版本已创建")


@router.get(
    "/{contract_id}/versions",
    response_model=ApiResponse[list[ContractVersion]],
    summary="合同版本列表",
)
async def list_contract_versions(
    contract_id: str,
    user: UserPublic = Depends(get_current_user),
    contracts: ContractService = Depends(get_contract_service),
) -> ApiResponse[list[ContractVersion]]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        return api_success(contracts.list_versions(contract_id))
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{contract_id}/overview",
    response_model=ApiResponse[ContractDetail],
    summary="合同详情聚合",
)
async def get_contract_overview(
    contract_id: str,
    request: Request,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractDetail]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        all_reviews = HistoryService(request.app.state.settings.report_dir.parent).list_records()
        linked_reviews = [item for item in all_reviews if item.get("contract_id") == contract_id]
        owner_names = {item.id: item.full_name for item in users.list_users()}
        contract = contracts.get_contract_enriched(
            contract_id,
            review_records=linked_reviews,
            owner_names=owner_names,
        )
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不可访问") from exc

    def review_summary(item: dict[str, Any]) -> ContractReviewSummary:
        counts = item.get("risk_counts")
        count = sum(int(value) for value in counts.values()) if isinstance(counts, dict) else None
        created_at = item.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if not isinstance(created_at, datetime):
            raise HTTPException(status_code=422, detail="审查记录缺少有效创建时间")
        return ContractReviewSummary(
            review_id=str(item.get("review_id")),
            created_at=created_at,
            status="completed",
            risk_level=item.get("overall_risk_level"),
            risk_count=count,
            duration_ms=item.get("duration_ms"),
            report_available=bool(item.get("report_path") or item.get("exports")),
        )

    summaries = [review_summary(item) for item in linked_reviews]
    audit_entries = [ContractAuditEntry.model_validate(item) for item in audit.list_operations(target=contract_id)]
    return api_success(
        ContractDetail(
            contract=contract,
            recent_reviews=summaries[:5],
            reports=[item for item in summaries if item.report_available],
            audit_logs=audit_entries,
        )
    )


@router.post(
    "/{contract_id}/versions/upload",
    response_model=ApiResponse[ContractVersion],
    status_code=status.HTTP_201_CREATED,
    summary="安全上传合同新版本",
)
async def upload_contract_version(
    contract_id: str,
    request: Request,
    contract_file: UploadFile = File(...),
    change_note: str | None = Form(default=None, max_length=1000),
    version_type: Literal["original", "modified", "re_review", "final"] = Form(
        default="modified"
    ),
    user: UserPublic = Depends(require_permission(Permission.contracts_write)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractVersion]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不可访问") from exc
    original_name = normalize_original_filename(contract_file.filename or "contract")
    original_content_type = contract_file.content_type
    settings = request.app.state.settings
    contract_upload_dir = settings.upload_dir / "contracts" / contract_id
    saved_path = await save_upload_file(
        file=contract_file,
        upload_dir=contract_upload_dir,
        max_size_mb=settings.max_upload_size_mb,
        max_pdf_pages=settings.max_pdf_pages,
        max_image_pixels=settings.max_image_pixels,
    )
    try:
        digest = hashlib.sha256(saved_path.read_bytes()).hexdigest()
        duplicate = contracts.find_version_by_hash(contract_id, digest)
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"该文件已作为 V{duplicate.version_no} 上传，请勿重复提交。",
            )
        parse_error: str | None = None
        try:
            text_content = await asyncio.to_thread(DocumentLoader(settings).load_text, saved_path)
        except Exception:
            text_content = None
            parse_error = (
                "当前文件可能为扫描版或无可提取文本，请上传可复制文字的 PDF 或 Word 文件。"
            )
        payload = ContractVersionCreate(
            file_name=original_name,
            change_note=change_note,
            file_hash=digest,
            version_type=version_type,
            text_content=text_content,
        )
        version = contracts.add_version(
            contract_id=contract_id,
            payload=payload,
            actor_id=user.id,
            file_path=str(saved_path),
            content_type=original_content_type,
            file_size=saved_path.stat().st_size,
            parse_status="ready" if text_content else "failed",
        )
        clauses = []
        if text_content:
            clauses = await asyncio.to_thread(
                ContractClauseService(settings.contract_data_dir).split_and_save,
                contract_id=contract_id,
                contract_version_id=version.id,
                text=text_content,
            )
    except Exception:
        saved_path.unlink(missing_ok=True)
        raise
    audit.log_operation(
        actor_id=user.id,
        action="contracts.version.upload",
        target=contract_id,
        metadata={
            "version_id": version.id,
            "file_size": version.file_size,
            "parse_status": version.parse_status,
            "clause_count": len(clauses),
            "parse_error": parse_error,
        },
    )
    return api_success(
        version,
        parse_error or f"合同已解析并切分为 {len(clauses)} 个条款",
    )


@router.get(
    "/{contract_id}/clauses",
    response_model=ApiResponse[list[ContractClause]],
    summary="查看合同解析条款",
)
async def list_contract_clauses(
    contract_id: str,
    request: Request,
    version_id: str | None = Query(default=None, max_length=120),
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
) -> ApiResponse[list[ContractClause]]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        if version_id:
            contracts.get_version(contract_id, version_id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不可访问") from exc
    clauses = ContractClauseService(request.app.state.settings.contract_data_dir).list_for_contract(
        contract_id, version_id
    )
    return api_success(clauses)


@router.get(
    "/{contract_id}/versions/{version_id}/download",
    response_class=FileResponse,
    summary="下载合同版本原文件",
)
async def download_contract_version(
    contract_id: str,
    version_id: str,
    request: Request,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> FileResponse:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        version = contracts.get_version(contract_id, version_id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同文件不可访问") from exc
    if not version.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同文件不可访问")
    path = Path(version.file_path).resolve()
    allowed_root = request.app.state.settings.upload_dir.resolve()
    if not path.is_relative_to(allowed_root) or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同文件不可访问")
    audit.log_operation(
        actor_id=user.id,
        action="contracts.version.download",
        target=contract_id,
        metadata={"version_id": version_id},
    )
    return FileResponse(
        path,
        media_type=version.content_type or "application/octet-stream",
        filename=sanitize_filename(version.file_name),
    )


@router.post(
    "/{contract_id}/versions/{version_id}/review",
    response_model=ApiResponse[ReviewTaskRecord],
    summary="发起合同版本审查",
)
async def review_contract_version(
    contract_id: str,
    version_id: str,
    request: Request,
    user: UserPublic = Depends(require_permission(Permission.reviews_run)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ReviewTaskRecord]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        contract = contracts.get_contract(contract_id)
        version = contracts.get_version(contract_id, version_id)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同文件不可访问") from exc
    if not version.file_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前版本没有可审查的原文件")
    path = Path(version.file_path).resolve()
    allowed_root = request.app.state.settings.upload_dir.resolve()
    if not path.is_relative_to(allowed_root) or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同文件不可访问")
    task_service = ReviewTaskService(
        request.app.state.settings,
        graph=request.app.state.contract_review_graph,
    )
    task = task_service.create_task(
        ReviewTaskCreate(
            contract_id=contract_id,
            contract_version_id=version_id,
            contract_type=contract.category.value,
            file_path=str(path),
            original_file_name=version.file_name,
            content_type=version.content_type,
        ),
        actor_id=user.id,
    )
    task = await task_service.enqueue_or_run_async(task.task_id)
    review_id = task.result_summary.get("review_id")
    if review_id:
        contracts.set_version_review(
            contract_id=contract_id,
            version_id=version_id,
            review_id=str(review_id),
            actor_id=user.id,
        )
    audit.log_operation(
        actor_id=user.id,
        action="contracts.review.start",
        target=contract_id,
        metadata={"version_id": version_id, "task_id": task.task_id},
    )
    return api_success(task, "审查任务已创建")


@router.post(
    "/{contract_id}/versions/compare",
    response_model=ApiResponse[VersionComparison],
    summary="比较合同版本并映射历史风险",
)
async def compare_contract_versions(
    contract_id: str,
    payload: VersionCompareRequest,
    user: UserPublic = Depends(require_permission(Permission.contracts_read)),
    contracts: ContractService = Depends(get_contract_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[VersionComparison]:
    try:
        contracts.require_access(contract_id, actor_id=user.id, actor_role=user.role.value)
        comparison = contracts.compare_versions(contract_id, payload)
    except ContractServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit.log_operation(actor_id=user.id, action="contracts.version.compare", target=contract_id)
    return api_success(comparison)
