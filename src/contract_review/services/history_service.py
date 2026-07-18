from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contract_review.infrastructure.document_store import JsonDocumentStore


class HistoryService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path) -> None:
        self.history_path = data_dir / "history.json"
        self.store = JsonDocumentStore(self.history_path, "analysis_history")

    def append(self, item: dict[str, Any]) -> None:
        with self._lock:
            records = self.list_records()
            records.insert(0, item)
            self.store.write(records[:2000])

    def list_records(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        return data if isinstance(data, list) else []

    def get(self, review_id: str) -> dict[str, Any] | None:
        for item in self.list_records():
            if item.get("review_id") == review_id:
                return item
        return None

    def search(
        self,
        *,
        keyword: str | None = None,
        risk_level: str | None = None,
        contract_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        records = self.list_records()
        if keyword:
            normalized = keyword.casefold()
            records = [
                item
                for item in records
                if normalized in str(item.get("file_name", "")).casefold()
                or normalized in str(item.get("review_id", "")).casefold()
            ]
        if risk_level:
            records = [item for item in records if item.get("overall_risk_level") == risk_level]
        if contract_type:
            records = [item for item in records if item.get("contract_type") == contract_type]
        total = len(records)
        start = (page - 1) * page_size
        return records[start : start + page_size], total

    def statistics(self) -> dict[str, Any]:
        records = self.list_records()
        risk_scores = [
            float(item["risk_score"]) for item in records if item.get("risk_score") is not None
        ]
        durations = [
            float(item["duration_ms"]) for item in records if item.get("duration_ms") is not None
        ]

        def count_by(key: str, fallback: str = "未知") -> dict[str, int]:
            result: dict[str, int] = {}
            for item in records:
                value = str(item.get(key) or fallback)
                result[value] = result.get(value, 0) + 1
            return result

        return {
            "total_reviews": len(records),
            "average_risk_score": round(sum(risk_scores) / len(risk_scores), 2)
            if risk_scores
            else 0,
            "average_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "risk_levels": count_by("overall_risk_level"),
            "contract_types": count_by("contract_type", "general"),
            "models": count_by("model_name", "规则引擎"),
        }


def build_history_item(
    *,
    review_id: str,
    file_name: str,
    final_report: dict[str, Any] | None,
    report_path: str | None,
    exports: dict[str, str],
    contract_type: str = "general",
    duration_ms: int | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    prompt_snapshot: dict[str, str] | None = None,
    token_usage: int | None = None,
    source_file_path: str | None = None,
    created_by: str | None = None,
    contract_id: str | None = None,
    contract_version_id: str | None = None,
    contract_text_path: str | None = None,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    final_report = final_report or {}
    risk_score = final_report.get("风险评分", {})
    findings = final_report.get("风险点")
    rule_counts: dict[str, dict[str, Any]] = {}
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            rule_id = str(finding.get("rule_id") or "").strip()
            if not rule_id:
                continue
            current = rule_counts.setdefault(
                rule_id,
                {
                    "rule_id": rule_id,
                    "title": str(finding.get("风险标题") or rule_id),
                    "count": 0,
                },
            )
            current["count"] += 1
    return {
        "review_id": review_id,
        "file_name": file_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract_type": contract_type,
        "duration_ms": duration_ms,
        "model_provider": model_provider,
        "model_name": model_name,
        "prompt_snapshot": prompt_snapshot or {},
        "token_usage": token_usage,
        "source_file_path": source_file_path,
        "created_by": created_by,
        "contract_id": contract_id,
        "contract_version_id": contract_version_id,
        "contract_text_path": contract_text_path,
        "classification": classification or {},
        "overall_risk_level": final_report.get("总体风险等级"),
        "risk_score": risk_score.get("风险分"),
        "safe_score": risk_score.get("安全分"),
        "risk_counts": final_report.get("风险统计", {}),
        "rule_counts": list(rule_counts.values()),
        "rule_counts_complete": isinstance(findings, list),
        "ai_status": final_report.get("AI增强"),
        "report_path": report_path,
        "exports": exports,
    }
