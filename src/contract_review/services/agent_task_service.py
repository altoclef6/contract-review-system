from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import select

from contract_review.core.config import Settings
from contract_review.database.models import (
    AgentEventModel,
    AgentStepModel,
    AgentTaskModel,
    AgentToolCallModel,
)
from contract_review.database.session import get_session_factory
from contract_review.schemas.agent_task import (
    AgentEventPublic,
    AgentStepPublic,
    AgentTaskPublic,
    AgentToolCallPublic,
    AgentToolDefinition,
)


class AgentTaskError(ValueError):
    pass


TOOL_REGISTRY: dict[str, AgentToolDefinition] = {
    "contract.search": AgentToolDefinition(
        name="contract.search",
        description="在当前企业范围内检索合同",
        risk_level="low",
        requires_confirmation=False,
    ),
    "contract.read": AgentToolDefinition(
        name="contract.read",
        description="读取当前企业内已授权合同",
        risk_level="low",
        requires_confirmation=False,
    ),
    "contract.compare_versions": AgentToolDefinition(
        name="contract.compare_versions",
        description="比较同一合同的两个版本",
        risk_level="low",
        requires_confirmation=False,
    ),
    "clause.find": AgentToolDefinition(
        name="clause.find",
        description="定位合同中的目标条款",
        risk_level="low",
        requires_confirmation=False,
    ),
    "knowledge.search": AgentToolDefinition(
        name="knowledge.search",
        description="检索当前企业知识库及公共法规",
        risk_level="low",
        requires_confirmation=False,
    ),
    "risk.summarize": AgentToolDefinition(
        name="risk.summarize",
        description="汇总风险并保留来源证据",
        risk_level="low",
        requires_confirmation=False,
    ),
    "report.generate": AgentToolDefinition(
        name="report.generate",
        description="生成可下载或归档的正式审查报告",
        risk_level="high",
        requires_confirmation=True,
    ),
}


TASK_PLANS: dict[str, list[str]] = {
    "contract_review": [
        "contract.read",
        "clause.find",
        "knowledge.search",
        "risk.summarize",
    ],
    "contract_compare": ["contract.read", "contract.compare_versions", "risk.summarize"],
    "risk_summary": ["contract.read", "risk.summarize"],
    "report_generation": ["contract.read", "risk.summarize", "report.generate"],
}


class AgentTaskService:
    def __init__(self, settings: Settings) -> None:
        if not settings.database_enabled:
            raise AgentTaskError("Agent 工作台需要启用数据库")

    def list_tools(self) -> list[AgentToolDefinition]:
        return list(TOOL_REGISTRY.values())

    def create(
        self,
        *,
        company_id: str,
        actor_id: str,
        task_type: str,
        objective: str,
        contract_id: str | None,
        context: dict[str, Any],
    ) -> AgentTaskPublic:
        tool_names = TASK_PLANS.get(task_type)
        if tool_names is None:
            raise AgentTaskError("不支持的 Agent 任务类型")
        plan = [
            {
                "sequence": index,
                "tool": name,
                "description": TOOL_REGISTRY[name].description,
                "requires_confirmation": TOOL_REGISTRY[name].requires_confirmation,
            }
            for index, name in enumerate(tool_names, start=1)
        ]
        with get_session_factory()() as session:
            task = AgentTaskModel(
                company_id=company_id,
                created_by=actor_id,
                contract_id=contract_id,
                task_type=task_type,
                objective=objective,
                status="created",
                plan=plan,
                context=context,
            )
            session.add(task)
            session.flush()
            for item in plan:
                session.add(
                    AgentStepModel(
                        task_id=task.id,
                        sequence=item["sequence"],
                        name=item["tool"],
                        status="pending",
                        requires_confirmation=item["requires_confirmation"],
                        input_data={"contract_id": contract_id},
                    )
                )
            self._event(session, task, "task.created", {"objective": objective})
            session.commit()
            return self._public(session, task)

    def list(self, *, company_id: str, actor_id: str, company_scope: bool) -> list[AgentTaskPublic]:
        with get_session_factory()() as session:
            query = select(AgentTaskModel).where(AgentTaskModel.company_id == company_id)
            if not company_scope:
                query = query.where(AgentTaskModel.created_by == actor_id)
            tasks = session.scalars(query.order_by(AgentTaskModel.created_at.desc())).all()
            return [self._public(session, task) for task in tasks]

    def get(
        self, task_id: str, *, company_id: str, actor_id: str, company_scope: bool
    ) -> AgentTaskPublic:
        with get_session_factory()() as session:
            task = self._owned(session, task_id, company_id, actor_id, company_scope)
            return self._public(session, task)

    def run(
        self, task_id: str, *, company_id: str, actor_id: str, company_scope: bool
    ) -> AgentTaskPublic:
        with get_session_factory()() as session:
            task = self._owned(session, task_id, company_id, actor_id, company_scope)
            if task.status not in {"created", "running", "waiting_confirmation"}:
                raise AgentTaskError("当前任务状态不能执行")
            task.status = "planning"
            task.started_at = task.started_at or datetime.now(timezone.utc)
            self._event(session, task, "task.planning", {"plan": task.plan})
            steps = session.scalars(
                select(AgentStepModel)
                .where(AgentStepModel.task_id == task.id)
                .order_by(AgentStepModel.sequence)
            ).all()
            task.status = "running"
            for step in steps:
                if step.status == "completed":
                    continue
                definition = TOOL_REGISTRY[step.name]
                task.current_step = step.sequence
                if definition.requires_confirmation:
                    existing = session.scalar(
                        select(AgentToolCallModel).where(
                            AgentToolCallModel.task_id == task.id,
                            AgentToolCallModel.step_id == step.id,
                        )
                    )
                    if existing is None:
                        session.add(
                            AgentToolCallModel(
                                task_id=task.id,
                                step_id=step.id,
                                company_id=company_id,
                                tool_name=step.name,
                                risk_level=definition.risk_level,
                                status="waiting_confirmation",
                                arguments=step.input_data,
                            )
                        )
                    step.status = "waiting_confirmation"
                    task.status = "waiting_confirmation"
                    self._event(
                        session,
                        task,
                        "tool.confirmation_required",
                        {"tool": step.name, "step": step.sequence},
                    )
                    session.commit()
                    return self._public(session, task)
                self._execute_safe_step(session, task, step)
            task.status = "completed"
            task.finished_at = datetime.now(timezone.utc)
            task.result = {
                "summary": "Agent 任务已完成",
                "evidence": [
                    {"type": "contract", "id": task.contract_id}
                    if task.contract_id
                    else {"type": "task", "id": task.id}
                ],
                "human_review_required": True,
            }
            self._event(session, task, "task.completed", task.result)
            session.commit()
            return self._public(session, task)

    def confirm(
        self,
        task_id: str,
        *,
        company_id: str,
        actor_id: str,
        approved: bool,
        note: str | None,
    ) -> AgentTaskPublic:
        with get_session_factory()() as session:
            task = self._owned(session, task_id, company_id, actor_id, True)
            call = session.scalar(
                select(AgentToolCallModel)
                .where(
                    AgentToolCallModel.task_id == task.id,
                    AgentToolCallModel.status == "waiting_confirmation",
                )
                .order_by(AgentToolCallModel.created_at)
            )
            if call is None:
                raise AgentTaskError("没有待确认的工具调用")
            call.confirmed_by = actor_id
            call.confirmed_at = datetime.now(timezone.utc)
            step = session.get(AgentStepModel, call.step_id)
            if approved:
                call.status = "completed"
                call.output = {"status": "generated", "note": note}
                if step:
                    step.status = "completed"
                    step.output_data = call.output
                    step.finished_at = datetime.now(timezone.utc)
                task.status = "running"
                self._event(session, task, "tool.confirmed", {"tool": call.tool_name})
            else:
                call.status = "rejected"
                call.output = {"status": "rejected", "note": note}
                if step:
                    step.status = "cancelled"
                task.status = "cancelled"
                task.finished_at = datetime.now(timezone.utc)
                self._event(session, task, "tool.rejected", {"tool": call.tool_name})
            session.commit()
        if approved:
            return self.run(task_id, company_id=company_id, actor_id=actor_id, company_scope=True)
        return self.get(task_id, company_id=company_id, actor_id=actor_id, company_scope=True)

    def _execute_safe_step(self, session: Any, task: AgentTaskModel, step: AgentStepModel) -> None:
        now = datetime.now(timezone.utc)
        step.status = "running"
        step.started_at = now
        output = {
            "status": "completed",
            "tool": step.name,
            "contract_id": task.contract_id,
            "evidence_retained": True,
        }
        call = AgentToolCallModel(
            task_id=task.id,
            step_id=step.id,
            company_id=task.company_id,
            tool_name=step.name,
            risk_level="low",
            status="completed",
            arguments=step.input_data,
            output=output,
        )
        session.add(call)
        step.output_data = output
        step.status = "completed"
        step.finished_at = now
        self._event(session, task, "tool.completed", {"tool": step.name})

    @staticmethod
    def _owned(
        session: Any,
        task_id: str,
        company_id: str,
        actor_id: str,
        company_scope: bool,
    ) -> AgentTaskModel:
        task = session.get(AgentTaskModel, task_id)
        if task is None or task.company_id != company_id:
            raise AgentTaskError("Agent 任务不存在")
        if not company_scope and task.created_by != actor_id:
            raise AgentTaskError("Agent 任务不存在")
        return cast(AgentTaskModel, task)

    @staticmethod
    def _event(
        session: Any, task: AgentTaskModel, event_type: str, payload: dict[str, Any]
    ) -> None:
        session.add(
            AgentEventModel(
                task_id=task.id,
                company_id=task.company_id,
                event_type=event_type,
                payload=payload,
            )
        )

    @staticmethod
    def _public(session: Any, task: AgentTaskModel) -> AgentTaskPublic:
        steps = session.scalars(
            select(AgentStepModel)
            .where(AgentStepModel.task_id == task.id)
            .order_by(AgentStepModel.sequence)
        ).all()
        calls = session.scalars(
            select(AgentToolCallModel)
            .where(AgentToolCallModel.task_id == task.id)
            .order_by(AgentToolCallModel.created_at)
        ).all()
        events = session.scalars(
            select(AgentEventModel)
            .where(AgentEventModel.task_id == task.id)
            .order_by(AgentEventModel.created_at)
        ).all()
        return AgentTaskPublic(
            **{
                column: getattr(task, column)
                for column in (
                    "id",
                    "company_id",
                    "created_by",
                    "contract_id",
                    "task_type",
                    "objective",
                    "status",
                    "current_step",
                    "plan",
                    "context",
                    "result",
                    "safe_error_message",
                    "created_at",
                    "updated_at",
                    "started_at",
                    "finished_at",
                )
            },
            steps=[AgentStepPublic.model_validate(item, from_attributes=True) for item in steps],
            tool_calls=[
                AgentToolCallPublic.model_validate(item, from_attributes=True) for item in calls
            ],
            events=[AgentEventPublic.model_validate(item, from_attributes=True) for item in events],
        )
