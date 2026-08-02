from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select

from contract_review.core.config import Settings
from contract_review.core.security import (
    generate_temporary_password,
    hash_password,
    verify_password,
)
from contract_review.database.models import CompanyModel, UserModel
from contract_review.database.session import get_session_factory
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
        company_id: str | None = None,
        department_id: str | None = None,
        job_title: str | None = None,
    ) -> UserPublic:
        if self.settings.database_enabled:
            with self._lock, get_session_factory()() as session:
                normalized_email = email.lower()
                existing = session.scalar(
                    select(UserModel).where(UserModel.email == normalized_email)
                )
                if existing is not None:
                    raise UserServiceError("用户邮箱已存在")
                if company_id is None:
                    company_id = self._default_company_id(session)
                model = UserModel(
                    email=normalized_email,
                    full_name=full_name,
                    role=role.value,
                    password_hash=hash_password(password),
                    company_id=company_id,
                    department_id=department_id,
                    job_title=job_title,
                )
                session.add(model)
                session.commit()
                session.refresh(model)
                return self._model_to_public(model)
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
                "token_version": 0,
                "company_id": company_id,
                "department_id": department_id,
                "job_title": job_title,
            }
            users.append(record)
            self._save(users)
            return self._to_public(record)

    def authenticate(self, *, email: str, password: str) -> UserPublic | None:
        if self.settings.database_enabled:
            with self._lock, get_session_factory()() as session:
                model = session.scalar(select(UserModel).where(UserModel.email == email.lower()))
                if (
                    model is None
                    or not model.is_active
                    or not verify_password(password, model.password_hash)
                ):
                    return None
                model.last_login_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(model)
                return self._model_to_public(model)
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
        if self.settings.database_enabled:
            with get_session_factory()() as session:
                model = session.get(UserModel, user_id)
                return self._model_to_public(model) if model else None
        for record in self._load():
            if record["id"] == user_id:
                return self._to_public(record)
        return None

    def list_users(self) -> list[UserPublic]:
        if self.settings.database_enabled:
            with get_session_factory()() as session:
                models = session.scalars(
                    select(UserModel).order_by(UserModel.created_at.desc())
                ).all()
                return [self._model_to_public(model) for model in models]
        return [self._to_public(record) for record in self._load()]

    def set_disabled(self, *, user_id: str, disabled: bool) -> UserPublic:
        if self.settings.database_enabled:
            def update_disabled(model: UserModel) -> None:
                model.is_active = not disabled
                if disabled:
                    model.token_version += 1

            return self._update_database_user(user_id, update_disabled)
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] == user_id:
                    record["is_active"] = not disabled
                    if disabled:
                        record["token_version"] = int(record.get("token_version", 0)) + 1
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(users)
                    return self._to_public(record)
        raise UserServiceError("用户不存在")

    def set_role(self, *, user_id: str, role: UserRole) -> UserPublic:
        if self.settings.database_enabled:
            def update_role(model: UserModel) -> None:
                model.role = role.value
                model.token_version += 1

            return self._update_database_user(user_id, update_role)
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] == user_id:
                    record["role"] = role.value
                    record["token_version"] = int(record.get("token_version", 0)) + 1
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(users)
                    return self._to_public(record)
        raise UserServiceError("用户不存在")

    def reset_password(self, *, user_id: str) -> tuple[UserPublic, str]:
        temporary_password = generate_temporary_password()
        if self.settings.database_enabled:
            def update_password(model: UserModel) -> None:
                model.password_hash = hash_password(temporary_password)
                model.token_version += 1

            user = self._update_database_user(user_id, update_password)
            return user, temporary_password
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] == user_id:
                    record["password_hash"] = hash_password(temporary_password)
                    record["token_version"] = int(record.get("token_version", 0)) + 1
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(users)
                    return self._to_public(record), temporary_password
        raise UserServiceError("用户不存在")

    def change_password(self, *, user_id: str, old_password: str, new_password: str) -> None:
        if self.settings.database_enabled:
            with self._lock, get_session_factory()() as session:
                model = session.get(UserModel, user_id)
                if model is None:
                    raise UserServiceError("用户不存在")
                if not verify_password(old_password, model.password_hash):
                    raise UserServiceError("原密码不正确")
                model.password_hash = hash_password(new_password)
                model.token_version += 1
                session.commit()
                return
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] != user_id:
                    continue
                if not verify_password(old_password, record["password_hash"]):
                    raise UserServiceError("原密码不正确")
                record["password_hash"] = hash_password(new_password)
                record["token_version"] = int(record.get("token_version", 0)) + 1
                record["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(users)
                return
        raise UserServiceError("用户不存在")

    def revoke_sessions(self, user_id: str) -> UserPublic:
        if self.settings.database_enabled:
            return self._update_database_user(
                user_id,
                lambda model: setattr(model, "token_version", model.token_version + 1),
            )
        with self._lock:
            users = self._load()
            for record in users:
                if record["id"] == user_id:
                    record["token_version"] = int(record.get("token_version", 0)) + 1
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(users)
                    return self._to_public(record)
        raise UserServiceError("用户不存在")

    def _ensure_bootstrap_admin(self) -> None:
        if self.settings.database_enabled:
            with self._lock, get_session_factory()() as session:
                company_id = self._default_company_id(session)
                admin_email = self.settings.bootstrap_admin_email.lower()
                existing = session.scalar(select(UserModel).where(UserModel.email == admin_email))
                if existing is not None:
                    if existing.company_id is None:
                        existing.company_id = company_id
                        session.commit()
                    return
                session.add(
                    UserModel(
                        email=admin_email,
                        full_name=self.settings.bootstrap_admin_name,
                        role=UserRole.admin.value,
                        password_hash=hash_password(
                            self.settings.bootstrap_admin_password.get_secret_value()
                        ),
                        company_id=company_id,
                    )
                )
                session.commit()
                return
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
                    "token_version": 0,
                    "company_id": None,
                    "department_id": None,
                    "job_title": None,
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
                "token_version": int(record.get("token_version", 0)),
                "company_id": record.get("company_id"),
                "department_id": record.get("department_id"),
                "job_title": record.get("job_title"),
            }
        )

    @staticmethod
    def _default_company_id(session: Any) -> str:
        company = session.scalar(select(CompanyModel).order_by(CompanyModel.created_at))
        if company is None:
            company = CompanyModel(name="默认企业", code="default")
            session.add(company)
            session.flush()
        return cast(str, company.id)

    def _update_database_user(
        self, user_id: str, update: Callable[[UserModel], None]
    ) -> UserPublic:
        with self._lock, get_session_factory()() as session:
            model = session.get(UserModel, user_id)
            if model is None:
                raise UserServiceError("用户不存在")
            update(model)
            session.commit()
            session.refresh(model)
            return self._model_to_public(model)

    @staticmethod
    def _model_to_public(model: UserModel) -> UserPublic:
        return UserPublic.model_validate(
            {
                "id": model.id,
                "email": model.email,
                "full_name": model.full_name,
                "role": model.role,
                "is_active": model.is_active,
                "company_id": model.company_id,
                "department_id": model.department_id,
                "job_title": model.job_title,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
                "last_login_at": model.last_login_at,
                "token_version": model.token_version,
            }
        )
