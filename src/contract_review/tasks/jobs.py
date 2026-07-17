from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contract_review.core.config import get_settings
from contract_review.graph.graph_builder import build_contract_review_graph
from contract_review.services.contract_service import ContractService
from contract_review.services.document_loader import DocumentLoader
from contract_review.services.notification_service import NotificationService
from contract_review.services.review_task_service import ReviewTaskService, ReviewTaskUnavailable
from contract_review.tasks.celery_app import celery_app


@celery_app.task(name="contract_review.ocr_document")
def ocr_document(file_path: str) -> dict[str, str]:
    settings = get_settings()
    text = DocumentLoader(settings).load_text(Path(file_path))
    return {"file_path": file_path, "text": text}


@celery_app.task(name="contract_review.export_report")
def export_report(review_id: str) -> dict[str, str]:
    return {"review_id": review_id, "status": "queued_for_export"}


@celery_app.task(
    bind=True,
    name="contract_review.run_review_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
    soft_time_limit=840,
    time_limit=900,
)
def run_review_task(self: Any, task_id: str) -> dict[str, str | None]:
    service = ReviewTaskService(get_settings(), graph=build_contract_review_graph())
    try:
        service.set_celery_task_id(task_id, str(self.request.id))
    except ReviewTaskUnavailable as exc:
        raise ConnectionError("review task state backend unavailable") from exc
    task = asyncio.run(service.execute_task(task_id))
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "review_id": task.result_summary.get("review_id"),
    }


@celery_app.task(name="contract_review.analyze_contract")
def analyze_contract(contract_id: str, version_id: str | None = None) -> dict[str, str | None]:
    return {"contract_id": contract_id, "version_id": version_id, "status": "use_review_tasks_api"}


@celery_app.task(name="contract_review.send_expiration_reminders")
def send_expiration_reminders(days: int = 30) -> dict[str, int]:
    settings = get_settings()
    contracts = ContractService(settings.contract_data_dir).list_expiring(days)
    notifications = NotificationService(settings.notification_data_dir)
    sent = 0
    for contract in contracts:
        if contract.expires_at is None:
            continue
        today = datetime.now(timezone.utc).date()
        already_sent = any(
            item.type == "contract_expiring"
            and item.payload.get("contract_id") == contract.id
            and item.created_at.date() == today
            for item in notifications.list_for_user(contract.created_by)
        )
        if already_sent:
            continue
        notifications.create(
            user_id=contract.created_by,
            type="contract_expiring",
            title="合同即将到期",
            content=f"合同《{contract.title}》将在 {contract.expires_at:%Y-%m-%d} 到期，请及时处理。",
            payload={"contract_id": contract.id, "expires_at": contract.expires_at.isoformat()},
        )
        sent += 1
    return {"sent": sent}
