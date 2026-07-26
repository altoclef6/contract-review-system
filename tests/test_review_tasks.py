from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from contract_review.core.config import Settings
from contract_review.infrastructure.cache import CacheService
from contract_review.schemas.review_task import ReviewTaskCreate, ReviewTaskStatus
from contract_review.services.review_task_service import (
    ReviewTaskConflictError,
    ReviewTaskError,
    ReviewTaskPermissionError,
    ReviewTaskService,
    ReviewTaskUnavailable,
)


def _docx(path: Path, text: str) -> Path:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    document.save(path)
    return path


class FakeGraph:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("provider credential must not leak")
        return {
            "extracted_fields": {"name": state["file_name"]},
            "compliance_findings": [
                {
                    "风险等级": "高",
                    "风险类别": "付款",
                    "风险描述": "付款期限过长",
                    "相关条款": "付款期限为一年",
                }
            ],
            "revision_suggestions": [],
            "final_report": {"椋庨櫓鐐?": []},
            "agent_trace": [],
            "errors": [],
        }


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        jwt_secret_key="test-secret-key-with-enough-length",
        bootstrap_admin_password="Admin12345!",
        upload_dir=tmp_path / "uploads",
        report_dir=tmp_path / "reports",
        review_task_data_dir=tmp_path / "tasks",
        prompt_template_data_dir=tmp_path / "prompts",
        model_config_data_dir=tmp_path / "models",
        redis_enabled=False,
        database_enabled=False,
        review_task_timeout_seconds=1,
        review_task_max_retries=2,
    )


def _payload(file_path: Path, idem: str = "idem-1") -> ReviewTaskCreate:
    return ReviewTaskCreate(
        file_path=str(file_path),
        original_file_name="contract.txt",
        content_type="text/plain",
        contract_type="service",
        idempotency_key=idem,
    )


def test_review_task_completes_and_is_idempotent(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.upload_dir.mkdir(parents=True)
    file_path = _docx(settings.upload_dir / "contract.docx", "付款期限为一年")
    service = ReviewTaskService(settings, graph=FakeGraph())

    first = service.create_task(_payload(file_path), actor_id="user_1")
    duplicate = service.create_task(_payload(file_path), actor_id="user_1")

    assert duplicate.task_id == first.task_id
    completed = service.enqueue_or_run(first.task_id)
    assert completed.status == ReviewTaskStatus.completed
    assert completed.current_stage == ReviewTaskStatus.completed
    assert completed.result_summary["risk_count"] == 1
    assert completed.result_summary["review_id"]


def test_model_failure_degrades_without_leaking_secret(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.upload_dir.mkdir(parents=True)
    file_path = _docx(settings.upload_dir / "contract.docx", "合同正文")
    service = ReviewTaskService(settings, graph=FakeGraph(fail=True))
    task = service.create_task(_payload(file_path), actor_id="user_1")

    completed = service.enqueue_or_run(task.task_id)

    assert completed.status == ReviewTaskStatus.completed
    assert completed.result_summary["risk_count"] >= 0
    assert completed.result_summary["ai_executed"] is False


def test_parse_failure_is_safe_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.upload_dir.mkdir(parents=True)
    service = ReviewTaskService(settings, graph=FakeGraph())
    task = service.create_task(_payload(settings.upload_dir / "missing.txt"), actor_id="user_1")

    failed = service.enqueue_or_run(task.task_id)

    assert failed.status == ReviewTaskStatus.failed
    assert failed.error_code == "TASK_FAILED"
    assert "Unsupported contract file type" in (failed.safe_error_message or "")
    assert str(tmp_path) not in (failed.safe_error_message or "")


def test_task_file_must_stay_inside_upload_dir(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    service = ReviewTaskService(settings, graph=FakeGraph())

    with pytest.raises(ReviewTaskError, match="outside upload directory"):
        service.create_task(_payload(tmp_path / "outside.docx"), actor_id="user_1")


def test_distributed_task_locks_fail_closed_when_redis_is_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _settings(tmp_path)
    settings.upload_dir.mkdir(parents=True)
    file_path = _docx(settings.upload_dir / "contract.docx", "测试合同")
    service = ReviewTaskService(settings, graph=FakeGraph())
    task = service.create_task(_payload(file_path), actor_id="user_1")
    service.settings.redis_enabled = True
    monkeypatch.setattr(CacheService, "set_if_absent_json", lambda self, key, value, ttl: False)
    monkeypatch.setattr(CacheService, "ping", lambda self: False)

    with pytest.raises(ReviewTaskUnavailable):
        service.create_task(_payload(file_path, "idem-redis"), actor_id="user_1")
    with pytest.raises(ConnectionError, match="backend unavailable"):
        asyncio.run(service.execute_task(task.task_id))


def test_cancel_retry_idor_and_expiration(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.upload_dir.mkdir(parents=True)
    file_path = _docx(settings.upload_dir / "contract.docx", "合同正文")
    service = ReviewTaskService(settings, graph=FakeGraph())
    task = service.create_task(_payload(file_path), actor_id="user_1")

    with pytest.raises(ReviewTaskPermissionError):
        service.get_task(task.task_id, actor_id="user_2")

    cancelled = service.cancel_task(task.task_id, actor_id="user_1")
    assert cancelled.status == ReviewTaskStatus.cancelled
    with pytest.raises(ReviewTaskConflictError, match="cancelled"):
        service.complete_task(task.task_id, {}, "review_should_not_win")
    service.fail_task(task.task_id, "LATE_FAILURE", "late worker failure")
    assert service.get_task(task.task_id, actor_id="user_1").status == ReviewTaskStatus.cancelled
    with pytest.raises(ReviewTaskConflictError):
        service.retry_task(task.task_id, actor_id="user_1", as_admin=False)

    failed = service.create_task(
        _payload(settings.upload_dir / "missing.txt", "idem-2"), actor_id="user_1"
    )
    failed = service.enqueue_or_run(failed.task_id)
    retried = service.retry_task(failed.task_id, actor_id="user_1", as_admin=False)
    assert retried.retry_count == 1

    running = service.create_task(_payload(file_path, "idem-3"), actor_id="user_1")
    service.update_stage(running.task_id, ReviewTaskStatus.llm_review)
    saved = service._load()
    raw = next(item for item in saved if item["task_id"] == running.task_id)
    raw["heartbeat_at"] = "2000-01-01T00:00:00+00:00"
    service._save(saved)
    assert service.mark_expired_tasks() == 1
    assert service.get_task(running.task_id, actor_id="user_1").status == ReviewTaskStatus.failed

    pending = service.create_task(_payload(file_path, "idem-pending"), actor_id="user_1")
    saved = service._load()
    raw = next(item for item in saved if item["task_id"] == pending.task_id)
    raw["created_at"] = "2000-01-01T00:00:00+00:00"
    service._save(saved)
    assert service.mark_expired_tasks() == 1
    assert service.get_task(pending.task_id, actor_id="user_1").status == ReviewTaskStatus.failed
