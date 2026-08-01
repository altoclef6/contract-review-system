from __future__ import annotations

from pathlib import Path

import pytest

from contract_review.core.config import get_settings
from contract_review.database.session import (
    get_engine,
    get_session_factory,
    init_database,
)
from contract_review.schemas.auth import UserRole
from contract_review.schemas.contract_management import ContractCreate
from contract_review.services.agent_task_service import AgentTaskError, AgentTaskService
from contract_review.services.contract_service import ContractService, ContractServiceError
from contract_review.services.organization_service import OrganizationService
from contract_review.services.user_service import UserService


def _database_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    database_path = tmp_path / "enterprise.db"
    monkeypatch.setenv("DATABASE_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    init_database()
    return get_settings()


def test_company_members_departments_and_contract_isolation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _database_runtime(monkeypatch, tmp_path)
    users = UserService(settings)
    admin = users.list_users()[0]
    organizations = OrganizationService(settings)
    department = organizations.create_department(
        admin.company_id or "", name="法务部", code="legal", parent_id=None
    )
    member = users.create_user(
        email="member@example.com",
        password="Member123!",
        full_name="企业成员",
        role=UserRole.member,
        company_id=admin.company_id,
        department_id=department.id,
    )
    contracts = ContractService(tmp_path / "contracts")
    record = contracts.create_contract(
        payload=ContractCreate(title="企业合同"),
        actor_id=member.id,
        company_id=member.company_id,
        department_id=member.department_id,
    )
    contracts.require_access(
        record.id,
        actor_id=admin.id,
        actor_role=admin.role.value,
        company_id=admin.company_id,
    )
    with pytest.raises(ContractServiceError):
        contracts.require_access(
            record.id,
            actor_id=admin.id,
            actor_role=admin.role.value,
            company_id="company_other",
        )


def test_agent_task_persists_events_and_requires_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _database_runtime(monkeypatch, tmp_path)
    admin = UserService(settings).list_users()[0]
    service = AgentTaskService(settings)
    task = service.create(
        company_id=admin.company_id or "",
        actor_id=admin.id,
        task_type="report_generation",
        objective="审查合同并生成正式报告",
        contract_id="contract_demo",
        context={},
    )
    waiting = service.run(
        task.id,
        company_id=admin.company_id or "",
        actor_id=admin.id,
        company_scope=True,
    )
    assert waiting.status == "waiting_confirmation"
    assert waiting.tool_calls[-1].tool_name == "report.generate"
    assert waiting.tool_calls[-1].status == "waiting_confirmation"

    completed = service.confirm(
        task.id,
        company_id=admin.company_id or "",
        actor_id=admin.id,
        approved=True,
        note="同意生成",
    )
    assert completed.status == "completed"
    assert any(event.event_type == "tool.confirmed" for event in completed.events)


def test_agent_task_rejects_cross_company_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _database_runtime(monkeypatch, tmp_path)
    admin = UserService(settings).list_users()[0]
    service = AgentTaskService(settings)
    task = service.create(
        company_id=admin.company_id or "",
        actor_id=admin.id,
        task_type="risk_summary",
        objective="汇总风险",
        contract_id=None,
        context={},
    )
    with pytest.raises(AgentTaskError):
        service.get(
            task.id,
            company_id="company_other",
            actor_id=admin.id,
            company_scope=True,
        )
