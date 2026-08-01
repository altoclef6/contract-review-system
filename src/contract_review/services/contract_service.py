from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
    VersionCompareRequest,
    VersionComparison,
)
from contract_review.services.version_comparison_service import VersionComparisonService


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
            versions = []
            if payload.file_name or payload.file_hash or payload.text_content:
                versions.append(
                    self._build_version(
                        version_no=1,
                        file_name=payload.file_name or "未上传文件",
                        change_note="初始版本",
                        review_id=None,
                        actor_id=actor_id,
                        created_at=now,
                        file_hash=payload.file_hash,
                        parent_version_id=None,
                        text_content=payload.text_content,
                        version_type="original",
                    )
                )
            record = {
                "id": f"contract_{uuid4().hex}",
                "title": payload.title,
                "category": payload.category.value,
                "tags": self._normalize_tags(payload.tags),
                "counterparty": payload.counterparty,
                "amount": str(payload.amount) if payload.amount is not None else None,
                "currency": payload.currency,
                "file_name": payload.file_name,
                "description": payload.description,
                "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
                "status": ContractStatus.draft.value,
                "is_favorite": False,
                "created_at": now,
                "updated_at": now,
                "created_by": actor_id,
                "updated_by": actor_id,
                "versions": versions,
                "current_version": len(versions),
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
        risk_level: str | None = None,
        review_records: list[dict[str, Any]] | None = None,
        owner_names: dict[str, str] | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ContractListResponse:
        latest_reviews = self._latest_reviews_by_contract(review_records or [])
        records = [
            self._to_record(
                self._enrich_record(record, latest_reviews, owner_names or {})
            )
            for record in self._load()
        ]
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
        if risk_level:
            records = [item for item in records if item.latest_risk_level == risk_level]

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

    def get_contract_enriched(
        self,
        contract_id: str,
        *,
        review_records: list[dict[str, Any]],
        owner_names: dict[str, str],
    ) -> ContractRecord:
        latest_reviews = self._latest_reviews_by_contract(review_records)
        return self._to_record(
            self._enrich_record(self._find(contract_id), latest_reviews, owner_names)
        )

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
                if isinstance(value, Decimal):
                    value = str(value)
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
        file_path: str | None = None,
        content_type: str | None = None,
        file_size: int | None = None,
        parse_status: str = "unavailable",
    ) -> ContractVersion:
        with self._lock:
            records = self._load()
            record = self._find_in_records(records, contract_id)
            versions = record.setdefault("versions", [])
            version = self._build_version(
                version_no=max(
                    (int(item.get("version_no", 0)) for item in versions), default=0
                )
                + 1,
                file_name=payload.file_name,
                change_note=payload.change_note,
                review_id=payload.review_id,
                actor_id=actor_id,
                created_at=self._now(),
                file_hash=payload.file_hash,
                parent_version_id=payload.parent_version_id
                or (versions[-1]["id"] if versions else None),
                text_content=payload.text_content,
                risk_snapshot=payload.risk_snapshot,
                version_type=("original" if not versions else payload.version_type),
                file_path=file_path,
                content_type=content_type,
                file_size=file_size,
                parse_status=parse_status,
            )
            versions.append(version)
            record["file_name"] = payload.file_name
            record["updated_at"] = self._now()
            record["updated_by"] = actor_id
            record["current_version"] = version["version_no"]
            self._save(records)
            return ContractVersion.model_validate(version)

    def set_version_review(
        self,
        *,
        contract_id: str,
        version_id: str,
        review_id: str,
        actor_id: str,
    ) -> ContractVersion:
        with self._lock:
            records = self._load()
            record = self._find_in_records(records, contract_id)
            for version in record.get("versions", []):
                if version.get("id") != version_id:
                    continue
                version["review_id"] = review_id
                version["review_status"] = "completed"
                record["updated_at"] = self._now()
                record["updated_by"] = actor_id
                self._save(records)
                return ContractVersion.model_validate(version)
        raise ContractServiceError("合同版本不存在")

    def get_version(self, contract_id: str, version_id: str) -> ContractVersion:
        record = self._find(contract_id)
        for version in record.get("versions", []):
            if version.get("id") == version_id:
                return ContractVersion.model_validate(version)
        raise ContractServiceError("合同版本不存在")

    def list_versions(self, contract_id: str) -> list[ContractVersion]:
        record = self._find(contract_id)
        return [ContractVersion.model_validate(item) for item in record.get("versions", [])]

    def find_version_by_hash(self, contract_id: str, file_hash: str) -> ContractVersion | None:
        for version in self.list_versions(contract_id):
            if version.file_hash and version.file_hash == file_hash:
                return version
        return None

    def compare_versions(
        self, contract_id: str, payload: VersionCompareRequest
    ) -> VersionComparison:
        record = self._find(contract_id)
        versions = {item["id"]: item for item in record.get("versions", [])}
        try:
            old_version = versions[payload.from_version_id]
            new_version = versions[payload.to_version_id]
        except KeyError as exc:
            raise ContractServiceError("合同版本不存在") from exc
        return VersionComparisonService().compare(
            from_version_id=payload.from_version_id,
            to_version_id=payload.to_version_id,
            old_text=old_version.get("text_content") or "",
            new_text=new_version.get("text_content") or "",
            old_risks=[item.model_dump() for item in payload.old_risks],
        )

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
        file_hash: str | None,
        parent_version_id: str | None,
        text_content: str | None,
        version_type: str,
        risk_snapshot: list[dict[str, Any]] | None = None,
        file_path: str | None = None,
        content_type: str | None = None,
        file_size: int | None = None,
        parse_status: str = "unavailable",
    ) -> dict[str, Any]:
        return {
            "id": f"version_{uuid4().hex}",
            "version_no": version_no,
            "file_name": file_name,
            "change_note": change_note,
            "review_id": review_id,
            "created_at": created_at,
            "created_by": actor_id,
            "file_hash": file_hash,
            "parent_version_id": parent_version_id,
            "text_content": text_content,
            "risk_snapshot": risk_snapshot or [],
            "version_type": version_type,
            "file_path": file_path,
            "content_type": content_type,
            "file_size": file_size,
            "parse_status": parse_status,
            "review_status": None,
            "risk_level": None,
        }

    def _enrich_record(
        self,
        record: dict[str, Any],
        latest_reviews: dict[str, dict[str, Any]],
        owner_names: dict[str, str],
    ) -> dict[str, Any]:
        enriched = dict(record)
        versions = [dict(item) for item in record.get("versions", [])]
        latest = latest_reviews.get(str(record.get("id")))
        if latest:
            enriched["latest_risk_level"] = latest.get("overall_risk_level")
            counts = latest.get("risk_counts")
            numeric_counts: list[int] = []
            if isinstance(counts, dict):
                for value in counts.values():
                    try:
                        numeric_counts.append(int(value))
                    except (TypeError, ValueError):
                        # Some persisted summaries also contain a textual
                        # overall-risk label. It is metadata, not a count.
                        continue
            if numeric_counts:
                largest = max(numeric_counts)
                remaining = sum(numeric_counts) - largest
                # Current summaries contain both a total and the severity
                # buckets; legacy summaries contain only the buckets.
                enriched["risk_count"] = largest if largest == remaining else sum(numeric_counts)
            else:
                enriched["risk_count"] = None
            review_id = latest.get("review_id")
            for version in versions:
                if version.get("id") == latest.get("contract_version_id") or (
                    review_id and version.get("review_id") == review_id
                ):
                    version["review_status"] = "completed"
                    version["risk_level"] = latest.get("overall_risk_level")
        enriched["versions"] = versions
        enriched["current_version"] = int(
            record.get("current_version")
            or max((item.get("version_no", 1) for item in versions), default=0)
        )
        created_by = str(record.get("created_by") or "")
        enriched["owner_name"] = owner_names.get(created_by)
        enriched.setdefault("amount", None)
        enriched.setdefault("currency", "CNY")
        return enriched

    def _latest_reviews_by_contract(
        self, review_records: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for item in sorted(
            review_records,
            key=lambda value: str(value.get("created_at") or ""),
            reverse=True,
        ):
            contract_id = str(item.get("contract_id") or "")
            if contract_id and contract_id not in latest:
                latest[contract_id] = item
        return latest

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        for tag in tags:
            value = tag.strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized[:20]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
