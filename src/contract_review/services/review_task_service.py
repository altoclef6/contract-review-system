from __future__ import annotations

import asyncio
import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from uuid import uuid4

from contract_review.core.config import Settings
from contract_review.infrastructure.cache import CacheService
from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.review_task import (
    TERMINAL_REVIEW_TASK_STATUSES,
    ReviewTaskCreate,
    ReviewTaskEvent,
    ReviewTaskListResponse,
    ReviewTaskRecord,
    ReviewTaskStatus,
)
from contract_review.services.local_task_executor import local_task_executor
from contract_review.services.review_service import ReviewService


class ReviewTaskError(ValueError):
    pass


class ReviewTaskPermissionError(ReviewTaskError):
    pass


class ReviewTaskConflictError(ReviewTaskError):
    pass


class ReviewTaskUnavailable(ReviewTaskError):
    pass


class ReviewTaskService:
    _lock = threading.Lock()
    _store_lock_key = "review-task-store:lock"

    def __init__(self, settings: Settings, graph: Any | None = None) -> None:
        self.settings = settings
        self.graph = graph
        self.store = JsonDocumentStore(settings.review_task_data_dir / "tasks.json", "review_tasks")
        self.cache = CacheService(settings)

    def create_task(self, payload: ReviewTaskCreate, actor_id: str) -> ReviewTaskRecord:
        with self._serialized_store():
            tasks = self._load()
            safe_file_path = self._validated_file_path(payload.file_path)
            idem = payload.idempotency_key or self._default_idempotency_key(payload, actor_id)
            existing = self._find_by_idempotency(tasks, idem, actor_id)
            if existing and existing["status"] not in {ReviewTaskStatus.failed.value}:
                return self._to_record(existing)
            now = self._now()
            task: dict[str, Any] = {
                "task_id": f"task_{uuid4().hex}",
                "contract_id": payload.contract_id,
                "contract_version_id": payload.contract_version_id,
                "requested_by": actor_id,
                "status": ReviewTaskStatus.pending.value,
                "current_stage": ReviewTaskStatus.pending.value,
                "progress": None,
                "idempotency_key": idem,
                "started_at": None,
                "finished_at": None,
                "heartbeat_at": None,
                "retry_count": 0,
                "provider": payload.provider,
                "model_name": payload.model_name,
                "error_code": None,
                "safe_error_message": None,
                "celery_task_id": None,
                "result_summary": {},
                "file_path": safe_file_path,
                "original_file_name": payload.original_file_name,
                "content_type": payload.content_type,
                "contract_type": payload.contract_type,
                "review_id": None,
                "audit_events": [self._event(ReviewTaskStatus.pending, "task.created")],
                "created_at": now,
                "updated_at": now,
            }
            tasks.append(task)
            self._save(tasks)
            return self._to_record(task)

    def enqueue_or_run(self, task_id: str) -> ReviewTaskRecord:
        if self.settings.redis_enabled:
            try:
                from contract_review.tasks.jobs import run_review_task

                celery_result = run_review_task.delay(task_id)
            except Exception as exc:
                if not self.settings.review_tasks_sync_fallback:
                    try:
                        self.fail_task(task_id, "QUEUE_UNAVAILABLE", self._safe_error(exc))
                    except ReviewTaskUnavailable as unavailable:
                        raise unavailable from exc
                    raise ReviewTaskConflictError("review task queue unavailable") from exc
            else:
                try:
                    self.set_celery_task_id(task_id, str(celery_result.id))
                except ReviewTaskUnavailable:
                    # The queue accepted the task. Avoid enqueueing a duplicate merely because
                    # the informational Celery id could not be persisted during a short outage.
                    pass
                return self.get_task(task_id, actor_id=None, as_admin=True)
        asyncio.run(self.execute_task(task_id))
        return self.get_task(task_id, actor_id=None, as_admin=True)

    async def enqueue_or_run_async(self, task_id: str) -> ReviewTaskRecord:
        if self.settings.redis_enabled:
            return self.enqueue_or_run(task_id)
        if self.settings.app_mode == "desktop":
            local_task_executor.submit(
                self.execute_task(task_id),
                max_concurrent=self.settings.desktop_max_concurrent_tasks,
            )
            return self.get_task(task_id, actor_id=None, as_admin=True)
        await self.execute_task(task_id)
        return self.get_task(task_id, actor_id=None, as_admin=True)

    async def execute_task(self, task_id: str) -> ReviewTaskRecord:
        try:
            task = self.get_task(task_id, actor_id=None, as_admin=True)
        except ReviewTaskUnavailable as exc:
            raise ConnectionError("review task state backend unavailable") from exc
        if task.status == ReviewTaskStatus.cancelled:
            return task
        if task.status == ReviewTaskStatus.completed:
            return task
        lock_key = f"review-task-lock:{task_id}"
        lock_value = {"task_id": task_id, "owner": uuid4().hex}
        lock_acquired = self.cache.set_if_absent_json(
            lock_key,
            lock_value,
            self.settings.review_task_timeout_seconds + 60,
        )
        if self.settings.redis_enabled and not lock_acquired:
            if not self.cache.ping():
                raise ConnectionError("review task lock backend unavailable")
            # Another worker owns the task. Returning current state avoids duplicate results.
            return self.get_task(task_id, actor_id=None, as_admin=True)
        try:
            self.update_stage(task_id, ReviewTaskStatus.validating)
            current = self._get_raw(task_id)
            if not current.get("file_path"):
                raise ReviewTaskError("review task has no file path")
            self._raise_if_cancelled(task_id)
            service = ReviewService(graph=self.graph, settings=self.settings)

            def stage_callback(stage: str) -> None:
                self.update_stage(task_id, ReviewTaskStatus(stage))
                self._raise_if_cancelled(task_id)

            response = await service.review_file(
                file_path=Path(str(current["file_path"])),
                original_file_name=str(
                    current.get("original_file_name") or Path(str(current["file_path"])).name
                ),
                content_type=current.get("content_type"),
                llm_config={
                    key: value
                    for key, value in {
                        "provider": current.get("provider"),
                        "model_name": current.get("model_name"),
                    }.items()
                    if value
                },
                contract_type=str(current.get("contract_type") or "general"),
                stage_callback=stage_callback,
                actor_id=str(current["requested_by"]),
                contract_id=current.get("contract_id"),
                contract_version_id=current.get("contract_version_id"),
            )
            self.complete_task(
                task_id,
                {
                    "review_id": response.review_id,
                    "risk_count": len(response.risk_findings),
                    "report_path": response.report_path,
                    "ai_executed": not any("LLM" in str(item) for item in response.errors),
                },
                response.review_id,
            )
        except ReviewTaskConflictError:
            self.cancel_task(task_id, actor_id=None, as_admin=True)
        except ReviewTaskUnavailable as exc:
            raise ConnectionError("review task state backend unavailable") from exc
        except Exception as exc:
            try:
                self.fail_task(task_id, "TASK_FAILED", self._safe_error(exc))
            except ReviewTaskUnavailable as unavailable:
                raise ConnectionError("review task state backend unavailable") from unavailable
        finally:
            if lock_acquired:
                self.cache.delete_if_json(lock_key, lock_value)
        return self.get_task(task_id, actor_id=None, as_admin=True)

    def list_tasks(
        self,
        *,
        actor_id: str,
        as_admin: bool,
        page: int,
        page_size: int,
        status: ReviewTaskStatus | None = None,
    ) -> ReviewTaskListResponse:
        self.mark_expired_tasks()
        items = [self._to_record(item) for item in self._load()]
        if not as_admin:
            items = [item for item in items if item.requested_by == actor_id]
        if status:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda item: item.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return ReviewTaskListResponse(
            items=items[start : start + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_task(
        self, task_id: str, actor_id: str | None, as_admin: bool = False
    ) -> ReviewTaskRecord:
        self.mark_expired_tasks()
        task = self._get_raw(task_id)
        if not as_admin and actor_id is not None and task["requested_by"] != actor_id:
            raise ReviewTaskPermissionError("review task not found")
        return self._to_record(task)

    def cancel_task(
        self, task_id: str, actor_id: str | None, as_admin: bool = False
    ) -> ReviewTaskRecord:
        with self._serialized_store():
            tasks = self._load()
            task = self._find(tasks, task_id)
            if not as_admin and actor_id is not None and task["requested_by"] != actor_id:
                raise ReviewTaskPermissionError("review task not found")
            if task["status"] in {ReviewTaskStatus.completed.value, ReviewTaskStatus.failed.value}:
                raise ReviewTaskConflictError("finished review task cannot be cancelled")
            if task["status"] != ReviewTaskStatus.cancelled.value:
                now = self._now()
                task.update(
                    status=ReviewTaskStatus.cancelled.value,
                    current_stage=ReviewTaskStatus.cancelled.value,
                    finished_at=now,
                    updated_at=now,
                )
                task.setdefault("audit_events", []).append(
                    self._event(ReviewTaskStatus.cancelled, "task.cancelled")
                )
            self._save(tasks)
            return self._to_record(task)

    def retry_task(self, task_id: str, actor_id: str, as_admin: bool) -> ReviewTaskRecord:
        with self._serialized_store():
            tasks = self._load()
            task = self._find(tasks, task_id)
            if not as_admin and task["requested_by"] != actor_id:
                raise ReviewTaskPermissionError("review task not found")
            if task["status"] != ReviewTaskStatus.failed.value:
                raise ReviewTaskConflictError("only failed review task can be retried")
            if int(task.get("retry_count") or 0) >= self.settings.review_task_max_retries:
                raise ReviewTaskConflictError("review task retry limit reached")
            now = self._now()
            task.update(
                status=ReviewTaskStatus.pending.value,
                current_stage=ReviewTaskStatus.pending.value,
                progress=None,
                started_at=None,
                finished_at=None,
                heartbeat_at=None,
                retry_count=int(task.get("retry_count") or 0) + 1,
                error_code=None,
                safe_error_message=None,
                celery_task_id=None,
                updated_at=now,
            )
            task.setdefault("audit_events", []).append(
                self._event(ReviewTaskStatus.pending, "task.retry")
            )
            self._save(tasks)
        return self.enqueue_or_run(task_id)

    def events(self, task_id: str, actor_id: str, as_admin: bool) -> list[ReviewTaskEvent]:
        task = self._get_raw(task_id)
        if not as_admin and task["requested_by"] != actor_id:
            raise ReviewTaskPermissionError("review task not found")
        return [ReviewTaskEvent.model_validate(item) for item in task.get("audit_events", [])]

    def update_stage(self, task_id: str, status: ReviewTaskStatus) -> None:
        with self._serialized_store():
            tasks = self._load()
            task = self._find(tasks, task_id)
            if task["status"] == ReviewTaskStatus.cancelled.value:
                raise ReviewTaskConflictError("review task cancelled")
            now = self._now()
            task.update(
                status=status.value,
                current_stage=status.value,
                started_at=task.get("started_at") or now,
                heartbeat_at=now,
                updated_at=now,
            )
            task.setdefault("audit_events", []).append(
                self._event(status, f"stage.{status.value.lower()}")
            )
            self._save(tasks)

    def complete_task(self, task_id: str, summary: dict[str, Any], review_id: str | None) -> None:
        with self._serialized_store():
            tasks = self._load()
            task = self._find(tasks, task_id)
            if task["status"] == ReviewTaskStatus.cancelled.value:
                raise ReviewTaskConflictError("review task cancelled")
            if task["status"] == ReviewTaskStatus.completed.value:
                return
            now = self._now()
            task.update(
                status=ReviewTaskStatus.completed.value,
                current_stage=ReviewTaskStatus.completed.value,
                progress=100,
                finished_at=now,
                heartbeat_at=now,
                result_summary=summary,
                review_id=review_id,
                updated_at=now,
            )
            task.setdefault("audit_events", []).append(
                self._event(ReviewTaskStatus.completed, "task.completed")
            )
            self._save(tasks)

    def fail_task(self, task_id: str, code: str, message: str) -> None:
        with self._serialized_store():
            tasks = self._load()
            task = self._find(tasks, task_id)
            if task["status"] in {
                ReviewTaskStatus.cancelled.value,
                ReviewTaskStatus.completed.value,
            }:
                return
            now = self._now()
            task.update(
                status=ReviewTaskStatus.failed.value,
                current_stage=ReviewTaskStatus.failed.value,
                finished_at=now,
                heartbeat_at=now,
                error_code=code,
                safe_error_message=message,
                updated_at=now,
            )
            task.setdefault("audit_events", []).append(self._event(ReviewTaskStatus.failed, code))
            self._save(tasks)

    def set_celery_task_id(self, task_id: str, celery_task_id: str) -> None:
        with self._serialized_store():
            tasks = self._load()
            task = self._find(tasks, task_id)
            task["celery_task_id"] = celery_task_id
            task["updated_at"] = self._now()
            self._save(tasks)

    def mark_expired_tasks(self) -> int:
        with self._serialized_store():
            tasks = self._load()
            now = datetime.now(timezone.utc)
            changed = 0
            for task in tasks:
                if task["status"] in {status.value for status in TERMINAL_REVIEW_TASK_STATUSES}:
                    continue
                heartbeat = self._parse_dt(
                    task.get("heartbeat_at") or task.get("started_at") or task.get("created_at")
                )
                if heartbeat and now - heartbeat > timedelta(
                    seconds=self.settings.review_task_timeout_seconds
                ):
                    task.update(
                        status=ReviewTaskStatus.failed.value,
                        current_stage=ReviewTaskStatus.failed.value,
                        finished_at=now.isoformat(),
                        error_code="TASK_EXPIRED",
                        safe_error_message="review task heartbeat expired",
                        updated_at=now.isoformat(),
                    )
                    task.setdefault("audit_events", []).append(
                        self._event(ReviewTaskStatus.failed, "TASK_EXPIRED")
                    )
                    changed += 1
            if changed:
                self._save(tasks)
            return changed

    def _raise_if_cancelled(self, task_id: str) -> None:
        if self._get_raw(task_id)["status"] == ReviewTaskStatus.cancelled.value:
            raise ReviewTaskConflictError("review task cancelled")

    def _get_raw(self, task_id: str) -> dict[str, Any]:
        return self._find(self._load(), task_id)

    def _load(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        return data if isinstance(data, list) else []

    def _save(self, tasks: list[dict[str, Any]]) -> None:
        self.store.write(tasks)

    @contextmanager
    def _serialized_store(self) -> Iterator[None]:
        with self._lock:
            if not self.settings.redis_enabled:
                yield
                return
            owner = secrets.token_urlsafe(24)
            deadline = monotonic() + 5
            while not self.cache.set_if_absent_json(self._store_lock_key, owner, ttl=10):
                if not self.cache.ping():
                    raise ReviewTaskUnavailable("review task state lock unavailable")
                if monotonic() >= deadline:
                    raise ReviewTaskUnavailable("review task state lock timed out")
                sleep(0.02)
            try:
                yield
            finally:
                self.cache.delete_if_json(self._store_lock_key, owner)

    def _find(self, tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
        for task in tasks:
            if task["task_id"] == task_id:
                return task
        raise ReviewTaskPermissionError("review task not found")

    def _find_by_idempotency(
        self, tasks: list[dict[str, Any]], idem: str, actor_id: str
    ) -> dict[str, Any] | None:
        for task in tasks:
            if task["idempotency_key"] == idem and task["requested_by"] == actor_id:
                return task
        return None

    def _to_record(self, task: dict[str, Any]) -> ReviewTaskRecord:
        return ReviewTaskRecord.model_validate(task)

    def _event(self, status: ReviewTaskStatus, message: str) -> dict[str, Any]:
        return {
            "status": status.value,
            "stage": status.value,
            "message": message,
            "created_at": self._now(),
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _parse_dt(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    def _safe_error(self, exc: Exception) -> str:
        text = str(exc) or exc.__class__.__name__
        for secret in ("sk-", "Bearer ", "Authorization", "api_key", "password", "secret"):
            text = text.replace(secret, "[redacted]")
        text = text.replace("\\", "/")
        if "/" in text:
            text = text.rsplit("/", 1)[-1]
        return text[:300]

    def _default_idempotency_key(self, payload: ReviewTaskCreate, actor_id: str) -> str:
        return "|".join(
            [
                actor_id,
                payload.contract_id or "",
                payload.contract_version_id or "",
                payload.file_path or "",
                payload.contract_type,
            ]
        )

    def _validated_file_path(self, file_path: str | None) -> str | None:
        if not file_path:
            return None
        upload_root = self.settings.upload_dir.resolve()
        candidate = Path(file_path).resolve()
        try:
            candidate.relative_to(upload_root)
        except ValueError as exc:
            raise ReviewTaskError("review task file is outside upload directory") from exc
        return str(candidate)
