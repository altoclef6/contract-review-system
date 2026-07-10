from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from contract_review.schemas.notification import NotificationPublic


class NotificationServiceError(ValueError):
    pass


class NotificationService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "notifications.json"

    def create(
        self,
        *,
        user_id: str,
        type: str,
        title: str,
        content: str,
        payload: dict[str, Any] | None = None,
    ) -> NotificationPublic:
        with self._lock:
            records = self._load()
            record = {
                "id": f"notice_{uuid4().hex}",
                "user_id": user_id,
                "type": type,
                "title": title,
                "content": content,
                "is_read": False,
                "payload": payload or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            records.append(record)
            self._save(records)
            return NotificationPublic.model_validate(record)

    def list_for_user(self, user_id: str) -> list[NotificationPublic]:
        records = [item for item in self._load() if item["user_id"] == user_id]
        records.sort(key=lambda item: item["created_at"], reverse=True)
        return [NotificationPublic.model_validate(item) for item in records]

    def mark_read(self, notification_id: str, user_id: str) -> NotificationPublic:
        with self._lock:
            records = self._load()
            for record in records:
                if record["id"] == notification_id and record["user_id"] == user_id:
                    record["is_read"] = True
                    self._save(records)
                    return NotificationPublic.model_validate(record)
        raise NotificationServiceError("通知不存在")

    def mark_all_read(self, user_id: str) -> int:
        with self._lock:
            records = self._load()
            count = 0
            for record in records:
                if record["user_id"] == user_id and not record.get("is_read"):
                    record["is_read"] = True
                    count += 1
            self._save(records)
            return count

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
