from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
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


class CompanyModel(Base, TimestampMixin):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("company")
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DepartmentModel(Base, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("company_id", "name"),)
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("department")
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("user"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True, default="employee")
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    department_id: Mapped[str | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    job_title: Mapped[str | None] = mapped_column(String(120))
    token_version: Mapped[int] = mapped_column(Integer, default=0)
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
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    department_id: Mapped[str | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    counterparty: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3), default="CNY")
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
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("contract_versions.id"), index=True
    )
    version_type: Mapped[str] = mapped_column(String(30), default="original", index=True)


class ReviewModel(Base, TimestampMixin):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("review"))
    contract_id: Mapped[str | None] = mapped_column(String(64), index=True)
    contract_version_id: Mapped[str | None] = mapped_column(ForeignKey("contract_versions.id"))
    creator_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
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


class ReviewTaskModel(Base, TimestampMixin):
    __tablename__ = "review_tasks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("task"))
    contract_id: Mapped[str | None] = mapped_column(String(64), index=True)
    contract_version_id: Mapped[str | None] = mapped_column(String(64), index=True)
    requested_by: Mapped[str] = mapped_column(String(64), index=True)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), index=True)
    current_stage: Mapped[str] = mapped_column(String(60), index=True)
    progress: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(160), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(160))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    celery_task_id: Mapped[str | None] = mapped_column(String(160), index=True)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(1000))
    original_file_name: Mapped[str | None] = mapped_column(String(260))
    content_type: Mapped[str | None] = mapped_column(String(120))
    contract_type: Mapped[str] = mapped_column(String(60), default="general")
    review_id: Mapped[str | None] = mapped_column(String(80), index=True)
    audit_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class ModelConfigModel(Base, TimestampMixin):
    __tablename__ = "model_configs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("model"))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
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
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
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
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
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
    company_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), index=True)
    target: Mapped[str | None] = mapped_column(String(255))
    request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    result: Mapped[str] = mapped_column(String(30), default="success", index=True)
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


class RiskFindingModel(Base, TimestampMixin):
    __tablename__ = "risk_findings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("risk"))
    # Compatibility services persist contract aggregate IDs outside the typed SQL tables.
    contract_id: Mapped[str | None] = mapped_column(String(64), index=True)
    company_id: Mapped[str | None] = mapped_column(String(64), index=True)
    contract_version_id: Mapped[str | None] = mapped_column(String(64), index=True)
    review_task_id: Mapped[str] = mapped_column(String(64), index=True)
    source_risk_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    contract_text: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    explanation: Mapped[str] = mapped_column(Text)
    legal_basis: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(Text)
    suggested_revision: Mapped[str | None] = mapped_column(Text)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    agent_name: Mapped[str | None] = mapped_column(String(100))
    rule_id: Mapped[str | None] = mapped_column(String(64), index=True)
    knowledge_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", index=True)
    reviewer_comment: Mapped[str | None] = mapped_column(Text)
    ai_original_recommendation: Mapped[str | None] = mapped_column(Text)
    human_final_opinion: Mapped[str | None] = mapped_column(Text)
    revised_clause: Mapped[str | None] = mapped_column(Text)
    assignee_id: Mapped[str | None] = mapped_column(String(64), index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_by: Mapped[str | None] = mapped_column(String(64), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    state_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    comments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    ai_involved: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeDocumentModel(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(120), index=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(80))
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), index=True)
    article_number: Mapped[str | None] = mapped_column(String(120), index=True)
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    checksum: Mapped[str] = mapped_column(String(64), index=True)


class LegalDocumentModel(Base, TimestampMixin):
    __tablename__ = "legal_document"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("law")
    )
    name: Mapped[str] = mapped_column(String(300), index=True)
    document_type: Mapped[str] = mapped_column(String(80), index=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255))
    document_number: Mapped[str | None] = mapped_column(String(120), index=True)
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    effect_status: Mapped[str] = mapped_column(String(40), index=True)
    version_number: Mapped[str] = mapped_column(String(80))
    official_source_url: Mapped[str | None] = mapped_column(String(1000))
    source_name: Mapped[str] = mapped_column(String(255))
    full_text: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(String(40), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(64), index=True)


class LegalDocumentVersionModel(Base):
    __tablename__ = "legal_document_version"
    __table_args__ = (UniqueConstraint("legal_document_id", "version_number"),)
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("lawver")
    )
    legal_document_id: Mapped[str] = mapped_column(
        ForeignKey("legal_document.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[str] = mapped_column(String(80))
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    effect_status: Mapped[str] = mapped_column(String(40), index=True)
    official_source_url: Mapped[str | None] = mapped_column(String(1000))
    source_name: Mapped[str] = mapped_column(String(255))
    full_text: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(String(40), index=True)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LegalArticleModel(Base, TimestampMixin):
    __tablename__ = "legal_article"
    __table_args__ = (UniqueConstraint("legal_document_version_id", "article_no"),)
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("article")
    )
    legal_document_id: Mapped[str] = mapped_column(
        ForeignKey("legal_document.id", ondelete="CASCADE"), index=True
    )
    legal_document_version_id: Mapped[str] = mapped_column(
        ForeignKey("legal_document_version.id", ondelete="CASCADE"), index=True
    )
    chapter_no: Mapped[str | None] = mapped_column(String(80))
    chapter_name: Mapped[str | None] = mapped_column(String(255))
    article_no: Mapped[str] = mapped_column(String(120), index=True)
    article_no_numeric: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str | None] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    legal_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    contract_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_effective: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    verification_status: Mapped[str] = mapped_column(String(40), index=True)
    created_by: Mapped[str] = mapped_column(String(64), index=True)


class ContractRiskRuleModel(Base, TimestampMixin):
    __tablename__ = "contract_risk_rule"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("legalrule")
    )
    rule_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(255))
    contract_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    clause_type: Mapped[str] = mapped_column(String(120), index=True)
    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    trigger_condition: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_prompt: Mapped[str] = mapped_column(Text, default="")
    risk_description: Mapped[str] = mapped_column(Text)
    possible_consequence: Mapped[str] = mapped_column(Text, default="")
    modification_advice: Mapped[str] = mapped_column(Text)
    recommended_clause: Mapped[str] = mapped_column(Text, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(64), index=True)


class RiskRuleLegalArticleModel(Base):
    __tablename__ = "risk_rule_legal_article"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("rulearticle")
    )
    risk_rule_id: Mapped[str] = mapped_column(
        ForeignKey("contract_risk_rule.id", ondelete="CASCADE"), index=True
    )
    legal_article_id: Mapped[str] = mapped_column(
        ForeignKey("legal_article.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewIssueLegalArticleModel(Base):
    __tablename__ = "review_issue_legal_article"
    __table_args__ = (UniqueConstraint("review_issue_id", "legal_article_id"),)
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("issuearticle")
    )
    review_issue_id: Mapped[str] = mapped_column(
        ForeignKey("risk_findings.id", ondelete="CASCADE"), index=True
    )
    legal_article_id: Mapped[str] = mapped_column(
        ForeignKey("legal_article.id", ondelete="RESTRICT"), index=True
    )
    review_id: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentTaskModel(Base, TimestampMixin):
    __tablename__ = "agent_tasks"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("agent_task")
    )
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(String(64), index=True)
    contract_id: Mapped[str | None] = mapped_column(String(64), index=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="created", index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentStepModel(Base, TimestampMixin):
    __tablename__ = "agent_steps"
    __table_args__ = (UniqueConstraint("task_id", "sequence"),)
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("agent_step")
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentToolCallModel(Base, TimestampMixin):
    __tablename__ = "agent_tool_calls"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("tool_call")
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_steps.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="low", index=True)
    status: Mapped[str] = mapped_column(String(40), default="created", index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confirmed_by: Mapped[str | None] = mapped_column(String(64), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentEventModel(Base):
    __tablename__ = "agent_events"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("agent_event")
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
