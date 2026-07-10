from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from contract_review.core.config import get_settings
from contract_review.services.contract_service import ContractService
from contract_review.services.document_loader import DocumentLoader
from contract_review.services.notification_service import NotificationService
from contract_review.tasks.celery_app import celery_app


@celery_app.task(name="contract_review.ocr_document")
def ocr_document(file_path: str) -> dict[str, str]:
    settings = get_settings()
    text = DocumentLoader(settings).load_text(Path(file_path))
    return {"file_path": file_path, "text": text}


@celery_app.task(name="contract_review.export_report")
def export_report(review_id: str) -> dict[str, str]:
    return {"review_id": review_id, "status": "queued_for_export"}


@celery_app.task(name="contract_review.analyze_contract")
def analyze_contract(contract_id: str, version_id: str | None = None) -> dict[str, str | None]:
    return {"contract_id": contract_id, "version_id": version_id, "status": "queued_for_analysis"}


@celery_app.task(name="contract_review.send_expiration_reminders")
def send_expiration_reminders(days: int = 30) -> dict[str, int]:
    settings = get_settings()
    contracts = ContractService(settings.contract_data_dir).list_expiring(days)
    notifications = NotificationService(settings.notification_data_dir)
    sent = 0
    for contract in contracts:
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
