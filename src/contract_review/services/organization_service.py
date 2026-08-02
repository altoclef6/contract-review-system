from __future__ import annotations

from typing import Any

from sqlalchemy import select

from contract_review.core.config import Settings
from contract_review.database.models import CompanyModel, DepartmentModel
from contract_review.database.session import get_session_factory
from contract_review.schemas.organization import CompanyPublic, DepartmentPublic


class OrganizationServiceError(ValueError):
    pass


class OrganizationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _require_database(self) -> None:
        if not self.settings.database_enabled:
            raise OrganizationServiceError("企业协作功能需要启用数据库")

    def get_company(self, company_id: str) -> CompanyPublic:
        self._require_database()
        with get_session_factory()() as session:
            model = session.get(CompanyModel, company_id)
            if model is None:
                raise OrganizationServiceError("企业不存在")
            return CompanyPublic.model_validate(model, from_attributes=True)

    def update_company(
        self, company_id: str, *, name: str | None, settings: dict[str, Any] | None
    ) -> CompanyPublic:
        self._require_database()
        with get_session_factory()() as session:
            model = session.get(CompanyModel, company_id)
            if model is None:
                raise OrganizationServiceError("企业不存在")
            if name is not None:
                model.name = name
            if settings is not None:
                model.settings = settings
            session.commit()
            session.refresh(model)
            return CompanyPublic.model_validate(model, from_attributes=True)

    def list_departments(self, company_id: str) -> list[DepartmentPublic]:
        self._require_database()
        with get_session_factory()() as session:
            rows = session.scalars(
                select(DepartmentModel)
                .where(DepartmentModel.company_id == company_id)
                .order_by(DepartmentModel.name)
            ).all()
            return [DepartmentPublic.model_validate(row, from_attributes=True) for row in rows]

    def create_department(
        self,
        company_id: str,
        *,
        name: str,
        code: str | None,
        parent_id: str | None,
    ) -> DepartmentPublic:
        self._require_database()
        with get_session_factory()() as session:
            if parent_id:
                parent = session.get(DepartmentModel, parent_id)
                if parent is None or parent.company_id != company_id:
                    raise OrganizationServiceError("上级部门不存在")
            duplicate = session.scalar(
                select(DepartmentModel).where(
                    DepartmentModel.company_id == company_id,
                    DepartmentModel.name == name,
                )
            )
            if duplicate is not None:
                raise OrganizationServiceError("部门名称已存在")
            model = DepartmentModel(
                company_id=company_id,
                name=name,
                code=code,
                parent_id=parent_id,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return DepartmentPublic.model_validate(model, from_attributes=True)

    def assert_department(self, company_id: str, department_id: str | None) -> None:
        if department_id is None:
            return
        self._require_database()
        with get_session_factory()() as session:
            model = session.get(DepartmentModel, department_id)
            if model is None or model.company_id != company_id:
                raise OrganizationServiceError("部门不存在或不属于当前企业")
