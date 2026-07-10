from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contract_review.core.config import Settings
from contract_review.core.security import (
    generate_temporary_password,
    hash_password,
    verify_password,
)
from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.auth import UserPublic, UserRole


class UserServiceError(ValueError):
    pass


class UserService:
    _lock = threading.Lock()

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.security_data_dir / "users.json"
        self.store = JsonDocumentStore(self.path, "users")
        self._ensure_bootstrap_admin()

    def create_user(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.employee,
    ) -> UserPublic:
        with self._lock:
            users = self._load()
            normalized_email = email.lower()
            if any(item["email"].lower() == normalized_email for item in users):
                raise UserServiceError("用户邮箱已存在")
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "id": f"user_{uuid4().hex}",
                "email": normalized_email,
                "full_name": full_name,
                "role": role.value,
                "password_hash": hash_password(password),
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "last_login_at": None,
            }
            users.append(record)
            self._save(users)
            return self._to_public(record)

    def authenticate(self, *, email: str, password: str) -> UserPublic | None:
        with self._lock:
            users = self._load()
            for record in users:
                if record["email"].lower() != email.lower():
                    continue
                if not record.get("is_active", True):
                    return None
                if not verify_password(password, record["password_hash"]):
                    return None
                record["last_login_at"] = datetime.now(timezone.utc).isoformat()
                record["updated_at"] = record["last_login_at"]
                self._save(users)
                return self._to_public(record)
        return None

    def get_by_id(self, user_id: str) -> UserPublic | None:
        for record in self._load():
            if record["id"] == user_id:
                return self._to_public(record)
        return None

    def list_users(self) -> list[UserPublic]:
        return [self._to_public(record) for record in self._load()]

    def set_disabled(self, *, user_id: str, disabled: bool) -> UserPublic:
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] == user_id:
                    record["is_active"] = not disabled
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(users)
                    return self._to_public(record)
        raise UserServiceError("用户不存在")

    def set_role(self, *, user_id: str, role: UserRole) -> UserPublic:
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] == user_id:
                    record["role"] = role.value
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(users)
                    return self._to_public(record)
        raise UserServiceError("用户不存在")

    def reset_password(self, *, user_id: str) -> tuple[UserPublic, str]:
        temporary_password = generate_temporary_password()
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] == user_id:
                    record["password_hash"] = hash_password(temporary_password)
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(users)
                    return self._to_public(record), temporary_password
        raise UserServiceError("用户不存在")

    def change_password(self, *, user_id: str, old_password: str, new_password: str) -> None:
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] != user_id:
                    continue
                if not verify_password(old_password, record["password_hash"]):
                    raise UserServiceError("原密码不正确")
                record["password_hash"] = hash_password(new_password)
                record["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(users)
                return
        raise UserServiceError("用户不存在")

    def _ensure_bootstrap_admin(self) -> None:
        with self._lock:
            users = self._load()
            admin_email = self.settings.bootstrap_admin_email.lower()
            if any(item["email"].lower() == admin_email for item in users):
                return
            now = datetime.now(timezone.utc).isoformat()
            users.append(
                {
                    "id": f"user_{uuid4().hex}",
                    "email": admin_email,
                    "full_name": self.settings.bootstrap_admin_name,
                    "role": UserRole.admin.value,
                    "password_hash": hash_password(
                        self.settings.bootstrap_admin_password.get_secret_value()
                    ),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "last_login_at": None,
                }
            )
            self._save(users)

    def _load(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        return data if isinstance(data, list) else []

    def _save(self, users: list[dict[str, Any]]) -> None:
        self.store.write(users)

    def _to_public(self, record: dict[str, Any]) -> UserPublic:
        return UserPublic.model_validate(
            {
                "id": record["id"],
                "email": record["email"],
                "full_name": record["full_name"],
                "role": record["role"],
                "is_active": record.get("is_active", True),
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "last_login_at": record.get("last_login_at"),
            }
        )
