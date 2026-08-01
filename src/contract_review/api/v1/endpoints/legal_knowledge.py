# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from contract_review.api.dependencies.auth import (
    get_audit_service,
    require_permission,
    require_role,
)
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic, UserRole
from contract_review.schemas.legal_knowledge import (
    ContractRiskRuleCreate,
    ContractRiskRuleRecord,
    ContractRiskRuleUpdate,
    DemoSeedResponse,
    LegalArticleCreate,
    LegalArticleRecord,
    LegalArticleUpdate,
    LegalDocumentCreate,
    LegalDocumentListResponse,
    LegalDocumentRecord,
    LegalDocumentUpdate,
    LegalDocumentVersionRecord,
    LegalEffectStatus,
    LegalSearchResponse,
    RiskRuleListResponse,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.legal_knowledge_service import (
    LegalKnowledgeConflictError,
    LegalKnowledgeError,
    LegalKnowledgeService,
)

router = APIRouter()


def get_service(settings: Settings = Depends(get_settings)) -> LegalKnowledgeService:
    return LegalKnowledgeService(settings)


def _raise_service_error(exc: LegalKnowledgeError) -> None:
    if isinstance(exc, LegalKnowledgeConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if str(exc).startswith("关联法条不存在"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if "不存在" in str(exc) or "不可访问" in str(exc):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/documents", response_model=ApiResponse[LegalDocumentListResponse])
async def list_documents(
    name: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    effect_status: LegalEffectStatus | None = Query(default=None),
    include_disabled: bool = Query(default=False),
    _: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[LegalDocumentListResponse]:
    items = service.list_documents(
        name=name,
        document_type=document_type,
        effect_status=effect_status,
        include_disabled=include_disabled,
    )
    return api_success(LegalDocumentListResponse(items=items, total=len(items)))


@router.post(
    "/documents", response_model=ApiResponse[LegalDocumentRecord], status_code=status.HTTP_201_CREATED
)
async def create_document(
    payload: LegalDocumentCreate,
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[LegalDocumentRecord]:
    try:
        record = service.create_document(payload, user.id)
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)
    audit.log_operation(
        actor_id=user.id,
        action="legal.document.create",
        target=record.id,
        metadata={
            "name": record.name,
            "version": record.version_number,
            "verification_status": record.verification_status.value,
        },
    )
    return api_success(record, "法律文件已创建")


@router.get("/documents/{document_id}", response_model=ApiResponse[LegalDocumentRecord])
async def get_document(
    document_id: str,
    _: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[LegalDocumentRecord]:
    try:
        return api_success(service.get_document(document_id))
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)


@router.patch("/documents/{document_id}", response_model=ApiResponse[LegalDocumentRecord])
async def update_document(
    document_id: str,
    payload: LegalDocumentUpdate,
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[LegalDocumentRecord]:
    try:
        record = service.update_document(document_id, payload, user.id)
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)
    audit.log_operation(
        actor_id=user.id,
        action=(
            "legal.document.toggle"
            if payload.model_fields_set == {"is_enabled"}
            else "legal.document.new_version"
        ),
        target=document_id,
        metadata={
            "fields": sorted(payload.model_fields_set),
            "version": record.version_number,
            "verification_status": record.verification_status.value,
        },
    )
    message = (
        "法律文件状态已更新"
        if payload.model_fields_set == {"is_enabled"}
        else "已创建法律文件新版本，旧版本保持不变"
    )
    return api_success(record, message)


@router.get(
    "/documents/{document_id}/versions",
    response_model=ApiResponse[list[LegalDocumentVersionRecord]],
)
async def list_document_versions(
    document_id: str,
    _: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[list[LegalDocumentVersionRecord]]:
    try:
        return api_success(service.list_versions(document_id))
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)


@router.get("/versions", response_model=ApiResponse[list[LegalDocumentVersionRecord]])
async def list_all_versions(
    _: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[list[LegalDocumentVersionRecord]]:
    return api_success(service.list_versions())


@router.get("/articles", response_model=ApiResponse[LegalSearchResponse])
async def search_articles(
    law_name: str | None = Query(default=None),
    article_no: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    legal_topic: str | None = Query(default=None),
    contract_type: str | None = Query(default=None),
    clause_type: str | None = Query(default=None),
    effect_status: LegalEffectStatus | None = Query(default=None),
    include_unverified: bool = Query(default=False),
    user: UserPublic = Depends(require_permission(Permission.knowledge_read)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[LegalSearchResponse]:
    items = service.search_articles(
        law_name=law_name,
        article_no=article_no,
        keyword=keyword,
        legal_topic=legal_topic,
        contract_type=contract_type,
        clause_type=clause_type,
        effect_status=effect_status,
        include_unverified=include_unverified and user.role == UserRole.admin,
    )
    return api_success(LegalSearchResponse(items=items, total=len(items)))


@router.post(
    "/articles", response_model=ApiResponse[LegalArticleRecord], status_code=status.HTTP_201_CREATED
)
async def create_article(
    payload: LegalArticleCreate,
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[LegalArticleRecord]:
    try:
        record = service.create_article(payload, user.id)
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)
    audit.log_operation(
        actor_id=user.id,
        action="legal.article.create",
        target=record.id,
        metadata={
            "document_id": record.legal_document_id,
            "version_id": record.legal_document_version_id,
            "article_no": record.article_no,
            "verification_status": record.verification_status.value,
        },
    )
    return api_success(record, "法律条文已创建")


@router.get("/articles/{article_id}", response_model=ApiResponse[LegalArticleRecord])
async def get_article(
    article_id: str,
    user: UserPublic = Depends(require_permission(Permission.knowledge_read)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[LegalArticleRecord]:
    try:
        return api_success(service.get_article(article_id, public_only=user.role != UserRole.admin))
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)


@router.patch("/articles/{article_id}", response_model=ApiResponse[LegalArticleRecord])
async def update_article(
    article_id: str,
    payload: LegalArticleUpdate,
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[LegalArticleRecord]:
    try:
        record = service.update_article(article_id, payload, user.id)
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)
    audit.log_operation(
        actor_id=user.id,
        action="legal.article.update",
        target=article_id,
        metadata={"fields": sorted(payload.model_fields_set)},
    )
    return api_success(record, "法律条文已更新")


@router.delete("/articles/{article_id}", response_model=ApiResponse[LegalArticleRecord])
async def deactivate_article(
    article_id: str,
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[LegalArticleRecord]:
    try:
        record = service.deactivate_article(article_id, user.id)
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)
    audit.log_operation(
        actor_id=user.id,
        action="legal.article.deactivate",
        target=article_id,
        metadata={"article_no": record.article_no},
    )
    return api_success(record, "法律条文已停用")


@router.get("/rules", response_model=ApiResponse[RiskRuleListResponse])
async def list_rules(
    enabled: bool | None = Query(default=None),
    contract_type: str | None = Query(default=None),
    clause_type: str | None = Query(default=None),
    _: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[RiskRuleListResponse]:
    items = service.list_rules(
        enabled=enabled, contract_type=contract_type, clause_type=clause_type
    )
    return api_success(RiskRuleListResponse(items=items, total=len(items)))


@router.post(
    "/rules", response_model=ApiResponse[ContractRiskRuleRecord], status_code=status.HTTP_201_CREATED
)
async def create_rule(
    payload: ContractRiskRuleCreate,
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRiskRuleRecord]:
    try:
        record = service.create_rule(payload, user.id)
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)
    audit.log_operation(
        actor_id=user.id,
        action="legal.rule.create",
        target=record.id,
        metadata={
            "rule_code": record.rule_code,
            "article_ids": record.legal_article_ids,
        },
    )
    return api_success(record, "合同风险规则已创建")


@router.patch("/rules/{rule_id}", response_model=ApiResponse[ContractRiskRuleRecord])
async def update_rule(
    rule_id: str,
    payload: ContractRiskRuleUpdate,
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[ContractRiskRuleRecord]:
    try:
        record = service.update_rule(rule_id, payload, user.id)
    except LegalKnowledgeError as exc:
        _raise_service_error(exc)
    audit.log_operation(
        actor_id=user.id,
        action="legal.rule.update",
        target=rule_id,
        metadata={"fields": sorted(payload.model_fields_set)},
    )
    return api_success(record, "合同风险规则已更新")


@router.get("/standard-clauses", response_model=ApiResponse[list[dict[str, str]]])
async def list_standard_clauses(
    _: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
) -> ApiResponse[list[dict[str, str]]]:
    return api_success(service.standard_clauses())


@router.post("/imports/demo", response_model=ApiResponse[DemoSeedResponse])
async def import_demo_data(
    user: UserPublic = Depends(require_role(UserRole.admin)),
    service: LegalKnowledgeService = Depends(get_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[DemoSeedResponse]:
    result = service.seed_demo_data(user.id)
    audit.log_operation(
        actor_id=user.id,
        action="legal.demo_import",
        target="legal-knowledge",
        metadata=result.model_dump(),
    )
    return api_success(result, result.message)
