from __future__ import annotations

import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from time import monotonic, sleep
from typing import Any

from contract_review.core.config import Settings
from contract_review.infrastructure.cache import CacheService
from contract_review.infrastructure.document_store import JsonDocumentStore


class RefreshTokenError(ValueError):
    pass


class RefreshTokenReuseError(RefreshTokenError):
    pass


class RefreshTokenUnavailable(RefreshTokenError):
    pass


class RefreshTokenService:
    """Persist refresh-token families without storing bearer tokens."""

    _lock = threading.Lock()

    _distributed_lock_key = "refresh-token-store:lock"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = CacheService(settings)
        self.store = JsonDocumentStore(
            settings.security_data_dir / "refresh_tokens.json", "refresh_token_families"
        )

    def issue(self, *, user_id: str, token_version: int, expires_at: int) -> tuple[str, str]:
        family_id = secrets.token_urlsafe(24)
        token_id = secrets.token_urlsafe(24)
        with self._serialized():
            records = self._load_active()
            records.append(
                self._record(family_id, token_id, user_id, token_version, expires_at, "active")
            )
            self.store.write(records)
        return family_id, token_id

    def rotate(
        self,
        *,
        user_id: str,
        family_id: str,
        token_id: str,
        token_version: int,
        expires_at: int,
    ) -> str:
        with self._serialized():
            records = self._load_active()
            current = next(
                (
                    item
                    for item in records
                    if item.get("family_id") == family_id and item.get("token_id") == token_id
                ),
                None,
            )
            if current is None or current.get("user_id") != user_id:
                raise RefreshTokenError("refresh token session not found")
            if current.get("status") != "active":
                self._revoke_family(records, family_id)
                self.store.write(records)
                raise RefreshTokenReuseError("refresh token reuse detected")
            if int(current.get("token_version", -1)) != token_version:
                self._revoke_family(records, family_id)
                self.store.write(records)
                raise RefreshTokenError("refresh token version is stale")
            current["status"] = "used"
            current["used_at"] = self._now()
            new_token_id = secrets.token_urlsafe(24)
            records.append(
                self._record(
                    family_id, new_token_id, user_id, token_version, expires_at, "active"
                )
            )
            self.store.write(records)
            return new_token_id

    def revoke_family(self, family_id: str) -> None:
        with self._serialized():
            records = self._load_active()
            self._revoke_family(records, family_id)
            self.store.write(records)

    def revoke_user(self, user_id: str) -> None:
        with self._serialized():
            records = self._load_active()
            for item in records:
                if item.get("user_id") == user_id and item.get("status") == "active":
                    item["status"] = "revoked"
                    item["revoked_at"] = self._now()
            self.store.write(records)

    def _load_active(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        records = data if isinstance(data, list) else []
        now = int(datetime.now(timezone.utc).timestamp())
        return [item for item in records if int(item.get("expires_at", 0)) >= now]

    @contextmanager
    def _serialized(self) -> Iterator[None]:
        with self._lock:
            if not self.settings.redis_enabled:
                yield
                return
            owner = secrets.token_urlsafe(24)
            deadline = monotonic() + 5
            while not self.cache.set_if_absent_json(
                self._distributed_lock_key, owner, ttl=10
            ):
                if not self.cache.ping():
                    raise RefreshTokenUnavailable("refresh token lock storage unavailable")
                if monotonic() >= deadline:
                    raise RefreshTokenUnavailable("refresh token lock acquisition timed out")
                sleep(0.02)
            try:
                yield
            finally:
                self.cache.delete_if_json(self._distributed_lock_key, owner)

    def _revoke_family(self, records: list[dict[str, Any]], family_id: str) -> None:
        for item in records:
            if item.get("family_id") == family_id and item.get("status") == "active":
                item["status"] = "revoked"
                item["revoked_at"] = self._now()

    def _record(
        self,
        family_id: str,
        token_id: str,
        user_id: str,
        token_version: int,
        expires_at: int,
        status: str,
    ) -> dict[str, Any]:
        return {
            "family_id": family_id,
            "token_id": token_id,
            "user_id": user_id,
            "token_version": token_version,
            "expires_at": expires_at,
            "status": status,
            "created_at": self._now(),
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
