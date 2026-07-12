from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.contract_management import (
    ContractCategory,
    ContractCreate,
    ContractListResponse,
    ContractRecord,
    ContractSortBy,
    ContractStatus,
    ContractUpdate,
    ContractVersion,
    ContractVersionCreate,
    SortOrder,
)


class ContractServiceError(ValueError):
    pass


class ContractService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "contracts.json"
        self.store = JsonDocumentStore(self.path, "contracts")

    def create_contract(self, *, payload: ContractCreate, actor_id: str) -> ContractRecord:
        with self._lock:
            records = self._load()
            now = self._now()
            version = self._build_version(
                version_no=1,
                file_name=payload.file_name or "未上传文件",
                change_note="初始版本",
                review_id=None,
                actor_id=actor_id,
                created_at=now,
            )
            record = {
                "id": f"contract_{uuid4().hex}",
                "title": payload.title,
                "category": payload.category.value,
                "tags": self._normalize_tags(payload.tags),
                "counterparty": payload.counterparty,
                "file_name": payload.file_name,
                "description": payload.description,
                "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
                "status": ContractStatus.draft.value,
                "is_favorite": False,
                "created_at": now,
                "updated_at": now,
                "created_by": actor_id,
                "updated_by": actor_id,
                "versions": [version],
            }
            records.append(record)
            self._save(records)
            return self._to_record(record)

    def list_contracts(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        category: ContractCategory | None,
        status: ContractStatus | None,
        tag: str | None,
        sort_by: ContractSortBy,
        sort_order: SortOrder,
        include_deleted: bool,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ContractListResponse:
        records = [self._to_record(record) for record in self._load()]
        if actor_id is not None and actor_role != "admin":
            records = [item for item in records if item.created_by == actor_id]
        if not include_deleted:
            records = [item for item in records if item.status != ContractStatus.deleted]
        if search:
            keyword = search.lower()
            records = [
                item
                for item in records
                if keyword in item.title.lower()
                or keyword in (item.counterparty or "").lower()
                or keyword in (item.description or "").lower()
            ]
        if category:
            records = [item for item in records if item.category == category]
        if status:
            records = [item for item in records if item.status == status]
        if tag:
            records = [item for item in records if tag in item.tags]

        reverse = sort_order == "desc"
        records.sort(key=lambda item: getattr(item, sort_by), reverse=reverse)
        total = len(records)
        start = (page - 1) * page_size
        return ContractListResponse(
            items=records[start : start + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_contract(self, contract_id: str) -> ContractRecord:
        return self._to_record(self._find(contract_id))

    def require_access(self, contract_id: str, *, actor_id: str, actor_role: str) -> None:
        record = self._find(contract_id)
        if actor_role != "admin" and record.get("created_by") != actor_id:
            raise ContractServiceError("合同不可访问")

    def update_contract(
        self,
        *,
        contract_id: str,
        payload: ContractUpdate,
        actor_id: str,
    ) -> ContractRecord:
        with self._lock:
            records = self._load()
            record = self._find_in_records(records, contract_id)
            updates = payload.model_dump(exclude_unset=True)
            if "tags" in updates and updates["tags"] is not None:
                updates["tags"] = self._normalize_tags(updates["tags"])
            for key, value in updates.items():
                if hasattr(value, "value"):
                    value = value.value
                if isinstance(value, datetime):
                    value = value.isoformat()
                record[key] = value
            record["updated_at"] = self._now()
            record["updated_by"] = actor_id
            self._save(records)
            return self._to_record(record)

    def set_favorite(self, *, contract_id: str, favorite: bool, actor_id: str) -> ContractRecord:
        return self._set_fields(
            contract_id=contract_id,
            actor_id=actor_id,
            fields={"is_favorite": favorite},
        )

    def archive(self, *, contract_id: str, actor_id: str) -> ContractRecord:
        return self._set_fields(
            contract_id=contract_id,
            actor_id=actor_id,
            fields={"status": ContractStatus.archived.value},
        )

    def delete(self, *, contract_id: str, actor_id: str) -> ContractRecord:
        return self._set_fields(
            contract_id=contract_id,
            actor_id=actor_id,
            fields={"status": ContractStatus.deleted.value},
        )

    def restore(self, *, contract_id: str, actor_id: str) -> ContractRecord:
        return self._set_fields(
            contract_id=contract_id,
            actor_id=actor_id,
            fields={"status": ContractStatus.draft.value},
        )

    def add_version(
        self,
        *,
        contract_id: str,
        payload: ContractVersionCreate,
        actor_id: str,
    ) -> ContractVersion:
        with self._lock:
            records = self._load()
            record = self._find_in_records(records, contract_id)
            versions = record.setdefault("versions", [])
            version = self._build_version(
                version_no=len(versions) + 1,
                file_name=payload.file_name,
                change_note=payload.change_note,
                review_id=payload.review_id,
                actor_id=actor_id,
                created_at=self._now(),
            )
            versions.append(version)
            record["file_name"] = payload.file_name
            record["updated_at"] = self._now()
            record["updated_by"] = actor_id
            self._save(records)
            return ContractVersion.model_validate(version)

    def list_versions(self, contract_id: str) -> list[ContractVersion]:
        record = self._find(contract_id)
        return [ContractVersion.model_validate(item) for item in record.get("versions", [])]

    def _set_fields(
        self,
        *,
        contract_id: str,
        actor_id: str,
        fields: dict[str, Any],
    ) -> ContractRecord:
        with self._lock:
            records = self._load()
            record = self._find_in_records(records, contract_id)
            record.update(fields)
            record["updated_at"] = self._now()
            record["updated_by"] = actor_id
            self._save(records)
            return self._to_record(record)

    def _find(self, contract_id: str) -> dict[str, Any]:
        return self._find_in_records(self._load(), contract_id)

    def _find_in_records(self, records: list[dict[str, Any]], contract_id: str) -> dict[str, Any]:
        for record in records:
            if record["id"] == contract_id:
                return record
        raise ContractServiceError("合同不存在")

    def list_expiring(self, days: int = 30) -> list[ContractRecord]:
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=days)
        result = []
        for record in self._load():
            value = record.get("expires_at")
            if not value or record.get("status") in {"archived", "deleted"}:
                continue
            expires_at = datetime.fromisoformat(value)
            if now <= expires_at <= deadline:
                result.append(self._to_record(record))
        return result

    def _load(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        return data if isinstance(data, list) else []

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.store.write(records)

    def _to_record(self, record: dict[str, Any]) -> ContractRecord:
        return ContractRecord.model_validate(record)

    def _build_version(
        self,
        *,
        version_no: int,
        file_name: str,
        change_note: str | None,
        review_id: str | None,
        actor_id: str,
        created_at: str,
    ) -> dict[str, Any]:
        return {
            "id": f"version_{uuid4().hex}",
            "version_no": version_no,
            "file_name": file_name,
            "change_note": change_note,
            "review_id": review_id,
            "created_at": created_at,
            "created_by": actor_id,
        }

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        for tag in tags:
            value = tag.strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized[:20]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
