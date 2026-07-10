from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from contract_review.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("user"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True, default="employee")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContractModel(Base, TimestampMixin):
    __tablename__ = "contracts"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("contract")
    )
    title: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="draft")
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContractVersionModel(Base, TimestampMixin):
    __tablename__ = "contract_versions"
    __table_args__ = (UniqueConstraint("contract_id", "version"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("version"))
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1000))
    content_type: Mapped[str | None] = mapped_column(String(120))
    file_size: Mapped[int | None] = mapped_column(Integer)
    text_content: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class ReviewModel(Base, TimestampMixin):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("review"))
    contract_id: Mapped[str | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    contract_version_id: Mapped[str | None] = mapped_column(ForeignKey("contract_versions.id"))
    creator_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="pending")
    model_provider: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(120))
    prompt_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    token_usage: Mapped[int | None] = mapped_column(Integer)
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str | None] = mapped_column(String(30), index=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)


class ModelConfigModel(Base, TimestampMixin):
    __tablename__ = "model_configs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("model"))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    provider: Mapped[str] = mapped_column(String(50))
    api_key_cipher: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str | None] = mapped_column(String(500))
    model_name: Mapped[str] = mapped_column(String(120))
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class PromptTemplateModel(Base, TimestampMixin):
    __tablename__ = "prompt_templates"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("prompt"))
    name: Mapped[str] = mapped_column(String(120))
    contract_type: Mapped[str] = mapped_column(String(30), index=True)
    stage: Mapped[str] = mapped_column(String(30), index=True)
    system_prompt: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkflowModel(Base, TimestampMixin):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("workflow")
    )
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    current_step: Mapped[str] = mapped_column(String(30), index=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    legal_reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    manager_reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class NotificationModel(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("notice"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("audit"))
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class AppStateModel(Base):
    __tablename__ = "app_state"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
