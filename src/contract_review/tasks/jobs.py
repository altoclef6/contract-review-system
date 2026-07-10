from __future__ import annotations

from pathlib import Path

from contract_review.core.config import get_settings
from contract_review.services.document_loader import DocumentLoader
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
