from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.login_log_path = data_dir / "login_logs.jsonl"
        self.operation_log_path = data_dir / "operation_logs.jsonl"

    def log_login(
        self,
        *,
        user_id: str | None,
        email: str,
        success: bool,
        ip_address: str | None,
        reason: str | None = None,
    ) -> None:
        self._append(
            self.login_log_path,
            {
                "user_id": user_id,
                "email": email,
                "success": success,
                "ip_address": ip_address,
                "reason": reason,
            },
        )

    def log_operation(
        self,
        *,
        actor_id: str | None,
        action: str,
        target: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._append(
            self.operation_log_path,
            {
                "actor_id": actor_id,
                "action": action,
                "target": target,
                "metadata": metadata or {},
            },
        )

    def _append(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"created_at": datetime.now(timezone.utc).isoformat(), **payload}
        with path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
