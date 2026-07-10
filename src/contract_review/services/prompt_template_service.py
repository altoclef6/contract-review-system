from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.prompts.compliance import COMPLIANCE_SYSTEM_PROMPT
from contract_review.prompts.extraction import EXTRACTION_SYSTEM_PROMPT
from contract_review.prompts.refinement import REFINEMENT_SYSTEM_PROMPT
from contract_review.schemas.prompt_template import (
    ContractType,
    PromptStage,
    PromptTemplateCreate,
    PromptTemplatePublic,
    PromptTemplateUpdate,
)


class PromptTemplateServiceError(ValueError):
    pass


BUILTIN_PROMPTS = {
    PromptStage.extraction: EXTRACTION_SYSTEM_PROMPT.strip(),
    PromptStage.compliance: COMPLIANCE_SYSTEM_PROMPT.strip(),
    PromptStage.refinement: REFINEMENT_SYSTEM_PROMPT.strip(),
}


class PromptTemplateService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "prompt_templates.json"
        self.store = JsonDocumentStore(self.path, "prompt_templates")

    def list_templates(
        self,
        *,
        contract_type: ContractType | None = None,
        stage: PromptStage | None = None,
    ) -> list[PromptTemplatePublic]:
        records = self._load()
        if contract_type is not None:
            records = [item for item in records if item["contract_type"] == contract_type.value]
        if stage is not None:
            records = [item for item in records if item["stage"] == stage.value]
        return [self._to_public(item) for item in records]

    def create(self, payload: PromptTemplateCreate, actor_id: str) -> PromptTemplatePublic:
        with self._lock:
            records = self._load()
            now = self._now()
            record = {
                "id": f"prompt_{uuid4().hex}",
                **payload.model_dump(mode="json"),
                "is_default": False,
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "created_by": actor_id,
                "updated_by": actor_id,
            }
            records.append(record)
            self._save(records)
            return self._to_public(record)

    def get(self, template_id: str) -> PromptTemplatePublic:
        return self._to_public(self._find(self._load(), template_id))

    def update(
        self, template_id: str, payload: PromptTemplateUpdate, actor_id: str
    ) -> PromptTemplatePublic:
        with self._lock:
            records = self._load()
            record = self._find(records, template_id)
            record.update(payload.model_dump(exclude_unset=True))
            record["version"] = int(record.get("version", 1)) + 1
            record["updated_at"] = self._now()
            record["updated_by"] = actor_id
            self._save(records)
            return self._to_public(record)

    def set_default(self, template_id: str, actor_id: str) -> PromptTemplatePublic:
        with self._lock:
            records = self._load()
            target = self._find(records, template_id)
            if not target.get("is_enabled", True):
                raise PromptTemplateServiceError("停用的模板不能设为默认模板")
            for record in records:
                if (
                    record["contract_type"] == target["contract_type"]
                    and record["stage"] == target["stage"]
                ):
                    record["is_default"] = record["id"] == template_id
            target["updated_at"] = self._now()
            target["updated_by"] = actor_id
            self._save(records)
            return self._to_public(target)

    def delete(self, template_id: str) -> PromptTemplatePublic:
        with self._lock:
            records = self._load()
            target = self._find(records, template_id)
            records = [item for item in records if item["id"] != template_id]
            self._save(records)
            return self._to_public(target)

    def resolve(self, contract_type: str | ContractType) -> dict[str, str]:
        try:
            resolved_type = ContractType(contract_type)
        except ValueError:
            resolved_type = ContractType.general
        result = {stage.value: prompt for stage, prompt in BUILTIN_PROMPTS.items()}
        records = self._load()
        for stage in PromptStage:
            candidates = [
                item
                for item in records
                if item.get("is_enabled", True)
                and item["stage"] == stage.value
                and item["contract_type"] in {resolved_type.value, ContractType.general.value}
            ]
            if not candidates:
                continue
            candidates.sort(
                key=lambda item: (
                    item["contract_type"] == resolved_type.value,
                    item.get("is_default", False),
                    item.get("version", 1),
                ),
                reverse=True,
            )
            result[stage.value] = candidates[0]["system_prompt"]
        return result

    def _load(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        return data if isinstance(data, list) else []

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.store.write(records)

    def _find(self, records: list[dict[str, Any]], template_id: str) -> dict[str, Any]:
        for record in records:
            if record["id"] == template_id:
                return record
        raise PromptTemplateServiceError("Prompt 模板不存在")

    def _to_public(self, record: dict[str, Any]) -> PromptTemplatePublic:
        return PromptTemplatePublic.model_validate(record)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
