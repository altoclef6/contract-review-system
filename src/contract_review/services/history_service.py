from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryService:
    def __init__(self, data_dir: Path) -> None:
        self.history_path = data_dir / "history.json"

    def append(self, item: dict[str, Any]) -> None:
        records = self.list_records()
        records.insert(0, item)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(
            json.dumps(records[:200], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_records(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def get(self, review_id: str) -> dict[str, Any] | None:
        for item in self.list_records():
            if item.get("review_id") == review_id:
                return item
        return None


def build_history_item(
    *,
    review_id: str,
    file_name: str,
    final_report: dict[str, Any] | None,
    report_path: str | None,
    exports: dict[str, str],
) -> dict[str, Any]:
    final_report = final_report or {}
    risk_score = final_report.get("风险评分", {})
    return {
        "review_id": review_id,
        "file_name": file_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_risk_level": final_report.get("总体风险等级"),
        "risk_score": risk_score.get("风险分"),
        "safe_score": risk_score.get("安全分"),
        "ai_status": final_report.get("AI增强"),
        "report_path": report_path,
        "exports": exports,
    }
