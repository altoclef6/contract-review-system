from __future__ import annotations

import base64
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.model_config import (
    ModelConfigCreate,
    ModelConfigPublic,
    ModelConfigUpdate,
    ModelProvider,
    ModelProviderInfo,
    ModelRuntimeConfig,
)


class ModelConfigServiceError(ValueError):
    pass


PROVIDER_INFOS: list[ModelProviderInfo] = [
    ModelProviderInfo(
        provider=ModelProvider.deepseek,
        label="DeepSeek",
        default_base_url="https://api.deepseek.com/v1",
        default_model_name="deepseek-chat",
        openai_compatible=True,
    ),
    ModelProviderInfo(
        provider=ModelProvider.openai,
        label="OpenAI",
        default_base_url=None,
        default_model_name="gpt-4.1-mini",
        openai_compatible=True,
    ),
    ModelProviderInfo(
        provider=ModelProvider.qwen,
        label="通义千问 Qwen",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model_name="qwen-plus",
        openai_compatible=True,
    ),
    ModelProviderInfo(
        provider=ModelProvider.claude,
        label="Claude",
        default_base_url="https://api.anthropic.com",
        default_model_name="claude-3-5-sonnet-latest",
        openai_compatible=False,
    ),
    ModelProviderInfo(
        provider=ModelProvider.gemini,
        label="Gemini",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model_name="gemini-1.5-pro",
        openai_compatible=True,
    ),
    ModelProviderInfo(
        provider=ModelProvider.openai_compatible,
        label="OpenAI 兼容接口",
        default_base_url=None,
        default_model_name="gpt-4.1-mini",
        openai_compatible=True,
    ),
]


class ModelConfigService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path, secret: str) -> None:
        self.path = data_dir / "model_configs.json"
        self.store = JsonDocumentStore(self.path, "model_configs")
        if not secret:
            raise ModelConfigServiceError("Model credential encryption key is not configured")
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(derived)
        self._legacy_secret = secret

    def list_providers(self) -> list[ModelProviderInfo]:
        return PROVIDER_INFOS

    def create(self, *, payload: ModelConfigCreate, actor_id: str) -> ModelConfigPublic:
        with self._lock:
            records = self._load()
            now = self._now()
            record = {
                "id": f"model_{uuid4().hex}",
                "name": payload.name,
                "provider": payload.provider.value,
                "api_key_cipher": self._encode_secret(payload.api_key.get_secret_value()),
                "base_url": payload.base_url,
                "model_name": payload.model_name,
                "temperature": payload.temperature,
                "max_tokens": payload.max_tokens,
                "description": payload.description,
                "is_active": len(records) == 0,
                "created_at": now,
                "updated_at": now,
                "created_by": actor_id,
                "updated_by": actor_id,
            }
            records.append(record)
            self._save(records)
            return self._to_public(record)

    def list_configs(self) -> list[ModelConfigPublic]:
        return [self._to_public(record) for record in self._load()]

    def get(self, config_id: str) -> ModelConfigPublic:
        return self._to_public(self._find(config_id))

    def update(
        self,
        *,
        config_id: str,
        payload: ModelConfigUpdate,
        actor_id: str,
    ) -> ModelConfigPublic:
        with self._lock:
            records = self._load()
            record = self._find_in_records(records, config_id)
            updates = payload.model_dump(exclude_unset=True)
            if payload.api_key is not None:
                updates["api_key_cipher"] = self._encode_secret(payload.api_key.get_secret_value())
                updates.pop("api_key", None)
            for key, value in updates.items():
                record[key] = value
            record["updated_at"] = self._now()
            record["updated_by"] = actor_id
            self._save(records)
            return self._to_public(record)

    def set_active(self, *, config_id: str, actor_id: str) -> ModelConfigPublic:
        with self._lock:
            records = self._load()
            target = self._find_in_records(records, config_id)
            now = self._now()
            for record in records:
                record["is_active"] = record["id"] == config_id
                if record["id"] == config_id:
                    record["updated_at"] = now
                    record["updated_by"] = actor_id
            self._save(records)
            return self._to_public(target)

    def delete(self, *, config_id: str, actor_id: str) -> ModelConfigPublic:
        _ = actor_id
        with self._lock:
            records = self._load()
            target = self._find_in_records(records, config_id)
            records = [record for record in records if record["id"] != config_id]
            if target.get("is_active") and records:
                records[0]["is_active"] = True
                records[0]["updated_at"] = self._now()
            self._save(records)
            return self._to_public(target)

    def get_active(self) -> ModelConfigPublic | None:
        for record in self._load():
            if record.get("is_active"):
                return self._to_public(record)
        return None

    def resolve_active_runtime_config(self) -> ModelRuntimeConfig | None:
        for record in self._load():
            if record.get("is_active"):
                return ModelRuntimeConfig(
                    provider=record["provider"],
                    api_key=self._decode_secret(record["api_key_cipher"]),
                    base_url=record.get("base_url"),
                    model_name=record["model_name"],
                    temperature=float(record.get("temperature", 0.1)),
                    max_tokens=int(record.get("max_tokens", 4096)),
                )
        return None

    def _find(self, config_id: str) -> dict[str, Any]:
        return self._find_in_records(self._load(), config_id)

    def _find_in_records(self, records: list[dict[str, Any]], config_id: str) -> dict[str, Any]:
        for record in records:
            if record["id"] == config_id:
                return record
        raise ModelConfigServiceError("模型配置不存在")

    def _load(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        records = data if isinstance(data, list) else []
        migrated = False
        for record in records:
            cipher = record.get("api_key_cipher")
            if isinstance(cipher, str) and not cipher.startswith("fernet:"):
                plaintext = self._decode_legacy_secret(cipher)
                record["api_key_cipher"] = self._encode_secret(plaintext)
                migrated = True
        if migrated:
            self._save(records)
        return records

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.store.write(records)

    def _to_public(self, record: dict[str, Any]) -> ModelConfigPublic:
        api_key = self._decode_secret(record["api_key_cipher"])
        return ModelConfigPublic.model_validate(
            {
                **record,
                "api_key_masked": self._mask_key(api_key),
            }
        )

    def _mask_key(self, value: str) -> str:
        if len(value) <= 10:
            return "已配置"
        return f"{value[:4]}...{value[-4:]}"

    def _encode_secret(self, value: str) -> str:
        return "fernet:" + self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def _decode_secret(self, value: str) -> str:
        if not value.startswith("fernet:"):
            return self._decode_legacy_secret(value)
        try:
            return self._fernet.decrypt(value.removeprefix("fernet:").encode("ascii")).decode(
                "utf-8"
            )
        except (InvalidToken, ValueError) as exc:
            raise ModelConfigServiceError("Stored model credential cannot be decrypted") from exc

    def _decode_legacy_secret(self, value: str) -> str:
        key = self._legacy_secret.encode("utf-8")
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii"))
            decoded = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(raw))
            return decoded.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ModelConfigServiceError("Stored legacy credential cannot be migrated") from exc

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
