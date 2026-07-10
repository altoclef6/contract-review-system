from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.auth import UserPublic, UserRole
from contract_review.schemas.workflow import (
    WorkflowAction,
    WorkflowActionRequest,
    WorkflowPublic,
    WorkflowStep,
)
from contract_review.services.notification_service import NotificationService


class WorkflowServiceError(ValueError):
    pass


class WorkflowService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path, notifications: NotificationService) -> None:
        self.path = data_dir / "workflows.json"
        self.store = JsonDocumentStore(self.path, "workflows")
        self.notifications = notifications

    def create(self, contract_id: str, review_id: str | None, actor: UserPublic) -> WorkflowPublic:
        with self._lock:
            records = self._load()
            if any(
                item["contract_id"] == contract_id
                and item["current_step"] not in {"archived", "rejected"}
                for item in records
            ):
                raise WorkflowServiceError("该合同已有进行中的审批流程")
            now = self._now()
            record = {
                "id": f"workflow_{uuid4().hex}",
                "contract_id": contract_id,
                "review_id": review_id,
                "submitter_id": actor.id,
                "current_step": WorkflowStep.uploaded.value,
                "status": "processing",
                "history": [self._event(WorkflowStep.uploaded, "create", actor, "合同已提交审批")],
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
            self._save(records)
            return WorkflowPublic.model_validate(record)

    def list_for_user(self, actor: UserPublic) -> list[WorkflowPublic]:
        records = self._load()
        if actor.role is UserRole.employee:
            records = [item for item in records if item["submitter_id"] == actor.id]
        records.sort(key=lambda item: item["updated_at"], reverse=True)
        return [WorkflowPublic.model_validate(item) for item in records]

    def get(self, workflow_id: str, actor: UserPublic) -> WorkflowPublic:
        record = self._find(self._load(), workflow_id)
        if actor.role is UserRole.employee and record["submitter_id"] != actor.id:
            raise WorkflowServiceError("审批流程不存在或无权访问")
        return WorkflowPublic.model_validate(record)

    def act(
        self,
        workflow_id: str,
        payload: WorkflowActionRequest,
        actor: UserPublic,
    ) -> WorkflowPublic:
        with self._lock:
            records = self._load()
            record = self._find(records, workflow_id)
            if actor.role is UserRole.employee and record["submitter_id"] != actor.id:
                raise WorkflowServiceError("审批流程不存在或无权操作")
            current = WorkflowStep(record["current_step"])
            next_step, status = self._transition(current, payload.action, actor)
            record["current_step"] = next_step.value
            record["status"] = status
            record["updated_at"] = self._now()
            record["history"].append(
                self._event(next_step, payload.action.value, actor, payload.comment)
            )
            self._save(records)
        self.notifications.create(
            user_id=record["submitter_id"],
            type="workflow_updated",
            title="合同审批状态已更新",
            content=f"合同 {record['contract_id']} 已进入 {next_step.value} 阶段。",
            payload={"workflow_id": workflow_id, "step": next_step.value},
        )
        return WorkflowPublic.model_validate(record)

    def _transition(
        self,
        current: WorkflowStep,
        action: WorkflowAction,
        actor: UserPublic,
    ) -> tuple[WorkflowStep, str]:
        if current is WorkflowStep.uploaded and action is WorkflowAction.start_ai_review:
            return WorkflowStep.ai_review, "processing"
        if current is WorkflowStep.ai_review and action is WorkflowAction.ai_completed:
            if actor.role not in {UserRole.admin, UserRole.legal}:
                raise WorkflowServiceError("仅法务或管理员可确认 AI 初审完成")
            return WorkflowStep.legal_review, "pending_legal"
        if current is WorkflowStep.legal_review:
            if actor.role not in {UserRole.admin, UserRole.legal}:
                raise WorkflowServiceError("当前节点需要法务审核")
            if action is WorkflowAction.approve:
                return WorkflowStep.manager_review, "pending_manager"
            if action is WorkflowAction.reject:
                return WorkflowStep.rejected, "rejected"
        if current is WorkflowStep.manager_review:
            if actor.role is not UserRole.admin:
                raise WorkflowServiceError("当前节点需要管理员代表主管审核")
            if action is WorkflowAction.approve:
                return WorkflowStep.archived, "completed"
            if action is WorkflowAction.reject:
                return WorkflowStep.rejected, "rejected"
        if current is WorkflowStep.rejected and action is WorkflowAction.resubmit:
            return WorkflowStep.uploaded, "processing"
        raise WorkflowServiceError("当前状态不允许执行该操作")

    def _event(
        self,
        step: WorkflowStep,
        action: str,
        actor: UserPublic,
        comment: str | None,
    ) -> dict[str, str | None]:
        return {
            "step": step.value,
            "action": action,
            "actor_id": actor.id,
            "actor_role": actor.role.value,
            "comment": comment,
            "created_at": self._now(),
        }

    def _find(self, records: list[dict[str, Any]], workflow_id: str) -> dict[str, Any]:
        for record in records:
            if record["id"] == workflow_id:
                return record
        raise WorkflowServiceError("审批流程不存在")

    def _load(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        return data if isinstance(data, list) else []

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.store.write(records)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
