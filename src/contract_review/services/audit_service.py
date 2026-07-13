from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from contract_review.core.config import get_settings
from contract_review.database.models import AuditLogModel
from contract_review.database.session import get_session_factory


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

    def list_operations(self, *, target: str, limit: int = 50) -> list[dict[str, Any]]:
        if get_settings().database_enabled:
            with get_session_factory()() as session:
                rows = session.scalars(
                    select(AuditLogModel)
                    .where(AuditLogModel.target == target)
                    .order_by(AuditLogModel.created_at.desc())
                    .limit(limit)
                ).all()
                return [
                    {
                        "actor_id": row.actor_id,
                        "action": row.action,
                        "target": row.target,
                        "metadata": row.details.get("metadata", {}),
                        "created_at": row.created_at,
                    }
                    for row in rows
                ]
        if not self.operation_log_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.operation_log_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("target") == target:
                records.append(item)
        return sorted(
            records,
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )[:limit]

    def _append(self, path: Path, payload: dict[str, Any]) -> None:
        record = {"created_at": datetime.now(timezone.utc).isoformat(), **payload}
        if get_settings().database_enabled:
            with get_session_factory()() as session:
                session.add(
                    AuditLogModel(
                        actor_id=payload.get("actor_id") or payload.get("user_id"),
                        action=str(payload.get("action") or "auth.login"),
                        target=payload.get("target") or payload.get("email"),
                        details=record,
                    )
                )
                session.commit()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
