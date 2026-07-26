
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.knowledge_center import (
    KnowledgeCreate,
    KnowledgeRecord,
    KnowledgeStatus,
    KnowledgeUpdate,
    KnowledgeWrite,
)


class KnowledgeCenterError(ValueError):
    pass


class KnowledgeCenterService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path, legacy_dir: Path | None = None) -> None:
        self.store = JsonDocumentStore(data_dir / "entries.json", "knowledge_center_entries")
        self.legacy_dir = legacy_dir

    def _records(self) -> list[dict[str, Any]]:
        records = self.store.read([])
        if not isinstance(records, list):
            records = []
        if not records and self.legacy_dir:
            records = self._legacy_seed()
        return [dict(item) for item in records if isinstance(item, dict)]

    def _legacy_seed(self) -> list[dict[str, Any]]:
        legacy_dir = self.legacy_dir
        if legacy_dir is None:
            return []
        now = datetime.now(timezone.utc).isoformat()
        records: list[dict[str, Any]] = []
        mapping = {
            "enterprise_controls.md": ("企业合同内控审查指引", "internal_policy"),
            "laws_cn.md": ("合同审查参考资料（需人工核验）", "review_guidance"),
        }
        for file_name, (title, source_type) in mapping.items():
            path = legacy_dir / file_name
            if not path.exists():
                continue
            records.append(
                {
                    "id": f"knowledge_{uuid4().hex}",
                    "document_id": f"legacy-{path.stem}",
                    "title": title,
                    "article_number": None,
                    "content": path.read_text(encoding="utf-8", errors="ignore"),
                    "source_type": source_type,
                    "status": "effective",
                    "issuing_authority": "项目内置参考资料",
                    "effective_date": None,
                    "expiry_date": None,
                    "version": 1,
                    "source_url": None,
                    "contract_types": [],
                    "related_rule_ids": [],
                    "supersedes_id": None,
                    "created_by": "system",
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if records:
            self.store.write(records)
        return records

    def list_entries(
        self,
        *,
        status: KnowledgeStatus | None = None,
        source_type: str | None = None,
        include_history: bool = False,
    ) -> list[KnowledgeRecord]:
        records = self._records()
        if not include_history:
            latest: dict[str, dict[str, Any]] = {}
            for item in records:
                if (
                    item["document_id"] not in latest
                    or item["version"] > latest[item["document_id"]]["version"]
                ):
                    latest[item["document_id"]] = item
            records = list(latest.values())
        if status:
            records = [item for item in records if item["status"] == status.value]
        if source_type:
            records = [item for item in records if item["source_type"] == source_type]
        records.sort(key=lambda item: item["updated_at"], reverse=True)
        return [KnowledgeRecord.model_validate(item) for item in records]

    def get(self, entry_id: str) -> KnowledgeRecord:
        item = next((item for item in self._records() if item["id"] == entry_id), None)
        if item is None:
            raise KnowledgeCenterError("知识条目不存在")
        return KnowledgeRecord.model_validate(item)

    def history(self, document_id: str) -> list[KnowledgeRecord]:
        return [
            KnowledgeRecord.model_validate(item)
            for item in sorted(
                (item for item in self._records() if item["document_id"] == document_id),
                key=lambda item: item["version"],
                reverse=True,
            )
        ]

    def create(self, payload: KnowledgeCreate, actor_id: str) -> KnowledgeRecord:
        with self._lock:
            records = self._records()
            if any(item["document_id"] == payload.document_id for item in records):
                raise KnowledgeCenterError("document_id 已存在，请创建新版本")
            record = self._build(payload.document_id, payload, actor_id, 1, None)
            records.append(record)
            self.store.write(records)
        return KnowledgeRecord.model_validate(record)

    def update(self, entry_id: str, payload: KnowledgeUpdate, actor_id: str) -> KnowledgeRecord:
        current = self.get(entry_id)
        data = current.model_dump(
            exclude={
                "id",
                "document_id",
                "version",
                "supersedes_id",
                "created_by",
                "created_at",
                "updated_at",
            }
        )
        data.update(payload.model_dump(exclude_unset=True))
        write = KnowledgeWrite.model_validate(data)
        with self._lock:
            records = self._records()
            record = self._build(
                current.document_id, write, actor_id, current.version + 1, current.id
            )
            records.append(record)
            self.store.write(records)
        return KnowledgeRecord.model_validate(record)

    def _build(
        self,
        document_id: str,
        payload: KnowledgeWrite,
        actor_id: str,
        version: int,
        supersedes_id: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        data = payload.model_dump(mode="json")
        return {
            "id": f"knowledge_{uuid4().hex}",
            "document_id": document_id,
            **data,
            "version": version,
            "source_url": str(payload.source_url) if payload.source_url else None,
            "supersedes_id": supersedes_id,
            "created_by": actor_id,
            "created_at": now,
            "updated_at": now,
        }

    def retrieve(self, keywords: set[str], limit: int = 6) -> list[KnowledgeRecord]:
        today = datetime.now(timezone.utc).date()
        scored: list[tuple[int, KnowledgeRecord]] = []
        for item in self.list_entries(status=KnowledgeStatus.effective):
            if item.expiry_date and item.expiry_date < today:
                continue
            score = sum(1 for keyword in keywords if keyword and keyword in item.content)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda value: value[0], reverse=True)
        return [item for _, item in scored[:limit]]
