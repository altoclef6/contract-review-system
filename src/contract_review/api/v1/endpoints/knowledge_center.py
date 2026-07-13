
# ruff: noqa: B008
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from contract_review.api.dependencies.auth import get_audit_service, require_permission
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic
from contract_review.schemas.knowledge_center import (
    KnowledgeCreate,
    KnowledgeListResponse,
    KnowledgeRecord,
    KnowledgeSourceType,
    KnowledgeStatus,
    KnowledgeUpdate,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.knowledge_center_service import (
    KnowledgeCenterError,
    KnowledgeCenterService,
)

router = APIRouter()


def get_service(settings: Settings = Depends(get_settings)) -> KnowledgeCenterService:
    return KnowledgeCenterService(
        settings.knowledge_center_data_dir,
        Path(__file__).resolve().parents[3] / "knowledge",
    )


@router.get("", response_model=ApiResponse[KnowledgeListResponse])
async def list_knowledge(
    status: KnowledgeStatus | None = Query(default=None),
    source_type: KnowledgeSourceType | None = Query(default=None),
    include_history: bool = Query(default=False),
    _: UserPublic = Depends(require_permission(Permission.knowledge_read)),
    service: KnowledgeCenterService = Depends(get_service),
) -> ApiResponse[KnowledgeListResponse]:
    items = service.list_entries(
        status=status, source_type=source_type, include_history=include_history
    )
    return api_success(KnowledgeListResponse(items=items, total=len(items)))


@router.post("", response_model=ApiResponse[KnowledgeRecord], status_code=201)
async def create_knowledge(
    payload: KnowledgeCreate,
    user: UserPublic = Depends(require_permission(Permission.knowledge_manage)),
    service: KnowledgeCenterService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[KnowledgeRecord]:
    try:
        record = service.create(payload, user.id)
    except KnowledgeCenterError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=user.id,
        action="knowledge.create",
        target=record.id,
        metadata={"document_id": record.document_id, "source_type": record.source_type.value},
    )
    return api_success(record, "知识条目已创建")


@router.get("/{entry_id}", response_model=ApiResponse[KnowledgeRecord])
async def get_knowledge(
    entry_id: str,
    _: UserPublic = Depends(require_permission(Permission.knowledge_read)),
    service: KnowledgeCenterService = Depends(get_service),
) -> ApiResponse[KnowledgeRecord]:
    try:
        return api_success(service.get(entry_id))
    except KnowledgeCenterError as exc:
        raise HTTPException(status_code=404, detail="知识条目不存在") from exc


@router.get("/{entry_id}/history", response_model=ApiResponse[list[KnowledgeRecord]])
async def get_knowledge_history(
    entry_id: str,
    _: UserPublic = Depends(require_permission(Permission.knowledge_read)),
    service: KnowledgeCenterService = Depends(get_service),
) -> ApiResponse[list[KnowledgeRecord]]:
    try:
        current = service.get(entry_id)
    except KnowledgeCenterError as exc:
        raise HTTPException(status_code=404, detail="知识条目不存在") from exc
    return api_success(service.history(current.document_id))


@router.patch("/{entry_id}", response_model=ApiResponse[KnowledgeRecord])
async def update_knowledge(
    entry_id: str,
    payload: KnowledgeUpdate,
    user: UserPublic = Depends(require_permission(Permission.knowledge_manage)),
    service: KnowledgeCenterService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[KnowledgeRecord]:
    try:
        record = service.update(entry_id, payload, user.id)
    except KnowledgeCenterError as exc:
        raise HTTPException(status_code=404, detail="知识条目不存在") from exc
    audit.log_operation(
        actor_id=user.id,
        action="knowledge.new_version",
        target=record.id,
        metadata={
            "document_id": record.document_id,
            "version": record.version,
            "supersedes_id": entry_id,
        },
    )
    return api_success(record, "已创建知识新版本")
