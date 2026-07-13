
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.version_comparison import (
    FeedbackStatistics,
    FeedbackType,
    RiskFeedbackCreate,
    RiskFeedbackRecord,
)


class RiskFeedbackError(ValueError):
    pass


class RiskFeedbackService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path) -> None:
        self.store = JsonDocumentStore(data_dir / "feedback.json", "risk_feedback")

    def list_records(self, contract_id: str | None = None) -> list[RiskFeedbackRecord]:
        data = self.store.read([])
        records = data if isinstance(data, list) else []
        if contract_id:
            records = [item for item in records if item["contract_id"] == contract_id]
        records.sort(key=lambda item: item["created_at"], reverse=True)
        return [RiskFeedbackRecord.model_validate(item) for item in records]

    def create(self, payload: RiskFeedbackCreate, actor_id: str) -> RiskFeedbackRecord:
        if (
            payload.feedback_type == FeedbackType.inaccurate_severity
            and not payload.suggested_severity
        ):
            raise RiskFeedbackError("风险等级不准确反馈必须提供建议等级")
        with self._lock:
            records = [item.model_dump(mode="json") for item in self.list_records()]
            duplicate = any(
                item["actor_id"] == actor_id
                and item["contract_version_id"] == payload.contract_version_id
                and item["risk_id"] == payload.risk_id
                and item["feedback_type"] == payload.feedback_type.value
                for item in records
            )
            if duplicate:
                raise RiskFeedbackError("相同反馈已经提交")
            record = {
                "id": f"feedback_{uuid4().hex}",
                **payload.model_dump(mode="json"),
                "actor_id": actor_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            records.append(record)
            self.store.write(records)
        return RiskFeedbackRecord.model_validate(record)

    def statistics(self) -> FeedbackStatistics:
        records = self.list_records()
        confirmed = sum(item.feedback_type == FeedbackType.confirmed_risk for item in records)
        rejected = sum(item.feedback_type == FeedbackType.not_a_risk for item in records)
        decided = confirmed + rejected
        by_contract_type: dict[str, int] = {}
        by_rule: dict[str, dict[str, int | float | None]] = {}
        by_date: dict[str, int] = {}
        for item in records:
            contract_type = item.contract_type or "unknown"
            by_contract_type[contract_type] = by_contract_type.get(contract_type, 0) + 1
            date_key = item.created_at.date().isoformat()
            by_date[date_key] = by_date.get(date_key, 0) + 1
            if item.rule_id:
                stats = by_rule.setdefault(
                    item.rule_id,
                    {"total": 0, "confirmed": 0, "rejected": 0, "confirmation_rate": None},
                )
                stats["total"] = int(stats["total"] or 0) + 1
                if item.feedback_type == FeedbackType.confirmed_risk:
                    stats["confirmed"] = int(stats["confirmed"] or 0) + 1
                if item.feedback_type == FeedbackType.not_a_risk:
                    stats["rejected"] = int(stats["rejected"] or 0) + 1
                rule_decided = int(stats["confirmed"] or 0) + int(stats["rejected"] or 0)
                stats["confirmation_rate"] = (
                    round(int(stats["confirmed"] or 0) / rule_decided * 100, 2)
                    if rule_decided
                    else None
                )
        return FeedbackStatistics(
            total=len(records),
            confirmed_count=confirmed,
            rejected_count=rejected,
            confirmation_rate=round(confirmed / decided * 100, 2) if decided else None,
            rejection_rate=round(rejected / decided * 100, 2) if decided else None,
            severity_adjustment_count=sum(
                item.feedback_type == FeedbackType.inaccurate_severity for item in records
            ),
            unusable_suggestion_count=sum(
                item.feedback_type == FeedbackType.unusable_suggestion for item in records
            ),
            by_contract_type=by_contract_type,
            by_rule=by_rule,
            by_date=by_date,
            recent_feedback=records[:20],
        )
