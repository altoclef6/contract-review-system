from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from contract_review.api.dependencies.auth import (
    get_audit_service,
    get_current_user,
    get_user_service,
    require_permission,
)
from contract_review.core.config import Settings, get_settings
from contract_review.schemas.api_response import ApiResponse, api_success
from contract_review.schemas.auth import Permission, UserPublic, UserRole
from contract_review.schemas.organization import (
    CompanyPublic,
    CompanyUpdate,
    DepartmentCreate,
    DepartmentPublic,
    MemberCreate,
    OrganizationOverview,
)
from contract_review.services.audit_service import AuditService
from contract_review.services.organization_service import (
    OrganizationService,
    OrganizationServiceError,
)
from contract_review.services.user_service import UserService, UserServiceError

router = APIRouter()


def get_organization_service(settings: Settings = Depends(get_settings)) -> OrganizationService:
    return OrganizationService(settings)


def require_company(user: UserPublic) -> str:
    if not user.company_id:
        raise HTTPException(status_code=409, detail="当前账号尚未加入企业")
    return user.company_id


@router.get("/overview", response_model=ApiResponse[OrganizationOverview])
async def overview(
    user: UserPublic = Depends(get_current_user),
    organizations: OrganizationService = Depends(get_organization_service),
    users: UserService = Depends(get_user_service),
) -> ApiResponse[OrganizationOverview]:
    company_id = require_company(user)
    members = [item for item in users.list_users() if item.company_id == company_id]
    return api_success(
        OrganizationOverview(
            company=organizations.get_company(company_id),
            departments=organizations.list_departments(company_id),
            members=members,
        )
    )


@router.patch("/company", response_model=ApiResponse[CompanyPublic])
async def update_company(
    payload: CompanyUpdate,
    actor: UserPublic = Depends(require_permission(Permission.company_manage)),
    organizations: OrganizationService = Depends(get_organization_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[CompanyPublic]:
    company_id = require_company(actor)
    result = organizations.update_company(company_id, name=payload.name, settings=payload.settings)
    audit.log_operation(
        actor_id=actor.id, company_id=company_id, action="company.updated", target=company_id
    )
    return api_success(result)


@router.get("/departments", response_model=ApiResponse[list[DepartmentPublic]])
async def departments(
    user: UserPublic = Depends(get_current_user),
    organizations: OrganizationService = Depends(get_organization_service),
) -> ApiResponse[list[DepartmentPublic]]:
    return api_success(organizations.list_departments(require_company(user)))


@router.post(
    "/departments",
    response_model=ApiResponse[DepartmentPublic],
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    payload: DepartmentCreate,
    actor: UserPublic = Depends(require_permission(Permission.departments_manage)),
    organizations: OrganizationService = Depends(get_organization_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[DepartmentPublic]:
    company_id = require_company(actor)
    try:
        result = organizations.create_department(
            company_id, name=payload.name, code=payload.code, parent_id=payload.parent_id
        )
    except OrganizationServiceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=actor.id, company_id=company_id, action="department.created", target=result.id
    )
    return api_success(result)


@router.get("/members", response_model=ApiResponse[list[UserPublic]])
async def members(
    actor: UserPublic = Depends(require_permission(Permission.users_read)),
    users: UserService = Depends(get_user_service),
) -> ApiResponse[list[UserPublic]]:
    company_id = require_company(actor)
    return api_success([item for item in users.list_users() if item.company_id == company_id])


@router.post(
    "/members", response_model=ApiResponse[UserPublic], status_code=status.HTTP_201_CREATED
)
async def create_member(
    payload: MemberCreate,
    actor: UserPublic = Depends(require_permission(Permission.members_manage)),
    organizations: OrganizationService = Depends(get_organization_service),
    users: UserService = Depends(get_user_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApiResponse[UserPublic]:
    company_id = require_company(actor)
    if payload.role is UserRole.admin:
        raise HTTPException(status_code=403, detail="企业管理员不能创建系统管理员")
    try:
        organizations.assert_department(company_id, payload.department_id)
        result = users.create_user(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role,
            company_id=company_id,
            department_id=payload.department_id,
            job_title=payload.job_title,
        )
    except (OrganizationServiceError, UserServiceError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log_operation(
        actor_id=actor.id, company_id=company_id, action="member.created", target=result.id
    )
    return api_success(result)
